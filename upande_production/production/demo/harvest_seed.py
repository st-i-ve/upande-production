"""Idempotent demo data for harvesting (crates -> Harvest Batch -> Harvesting stock entry).

bench --site mutara.local execute upande_production.production.demo.harvest_seed.run

Sets up the harvest warehouse, the crate crops' average crate weights, 400 numbered crates
(C-0001..C-0400, the QR ids), two harvest teams (leaders from the Production Supervisors, pickers from
the Value Adders), then scans and closes a few batches today: PH1-B1 (two batches, one
crate load still open) and two fruit & vegetable blocks. Closing a batch posts its Harvesting stock
entry, Production Harvest, picker work drafts and, on PH1-B1, an Avocado Harvest Log row. Run after
avocado_seed (all.py does).
"""

import frappe
from frappe.utils import today

from upande_production.mobile import harvest as api
from upande_production.production.demo.config import DEMO as BASE
from upande_production.production.logic import harvest as H

CRATES = 400
PREFIX = "C"
# crop key -> kg in a full crate (Production Crop default)
CROP_KG = {"avocado": 18, "fruits-vegetables": 20}
# Fruit & vegetable items whose crate weighs differently from the crop default.
ITEM_KG = {"Potatoes": 25, "Cabbage": 18, "Onion": 22, "Passion Fruit": 10, "Maize": 25}
# Book receipts at this share of the demo selling price (an assumed cost, not a market quote).
VALUATION_SHARE = 0.6
TEAMS = [
	# number, leader index (supervisors), pickers (value adders slice), usual block
	("1", 0, slice(0, 6), "PH1-B1"),
	("2", 1, slice(6, 12), "P2-B2"),
]
# team number, block, [crates per scan call] -> closed after scanning; the last entry may stay open
BATCHES = [
	("1", "PH1-B1", 30, True),
	("1", "PH1-B1", 22, True),
	("2", "P2-B2", 18, True),
	("2", "P1-B4", 14, True),
	("1", "PH1-B1", 6, False),  # scanned, not yet closed: shows as in the field
]


def setup_masters():
	company = BASE["company"]
	H.ensure_stock_entry_type()
	H.ensure_harvest_warehouse("Mutara Harvest Store", company)
	for key, kg in CROP_KG.items():
		name = frappe.db.get_value("Production Crop", {"crop_key": key})
		if name:
			frappe.db.set_value("Production Crop", name, {"harvests_in_crates": 1, "avg_kg_per_crate": kg})
	for item, kg in ITEM_KG.items():
		if frappe.db.exists("Item", item):
			frappe.db.set_value("Item", item, "production_avg_kg_per_crate", kg)
	for item, price in BASE["prices"].items():
		if frappe.db.exists("Item", item) and not frappe.db.get_value("Item", item, "valuation_rate"):
			frappe.db.set_value("Item", item, "valuation_rate", round(price * VALUATION_SHARE, 2))
	for crop in ("Avocado", "Fruits & Vegetables"):
		if frappe.db.exists("Production Crop", crop):
			H.harvest_operation(crop)


def seed_crates() -> int:
	have = set(frappe.get_all("Harvest Crate", pluck="name", limit_page_length=0))
	farm = BASE["farm"]["name"]
	made = 0
	for i in range(1, CRATES + 1):
		cid = f"{PREFIX}-{i:04d}"
		if cid in have:
			continue
		frappe.get_doc({"doctype": "Harvest Crate", "crate_id": cid, "serial_no": i, "status": "Active",
			"farm": farm}).insert(ignore_permissions=True)
		made += 1
	return made


def seed_teams() -> dict:
	company = BASE["company"]
	leaders = frappe.get_all("Employee", filters={"designation": "Production Supervisor", "company": company, "status": "Active"},
		pluck="name", order_by="first_name, last_name")
	pickers = frappe.get_all("Employee", filters={"designation": "Value Adder", "company": company, "status": "Active"},
		pluck="name", order_by="first_name, last_name")
	out = {}
	for number, li, ps, unit in TEAMS:
		name = frappe.db.get_value("Harvest Team", {"team_number": number})
		if name:
			out[number] = name
			# a team an earlier run put on a demo block that is retired now moves to its real block
			cur = frappe.db.get_value("Harvest Team", name, "unit")
			if cur != unit and frappe.db.exists("Production Unit", unit) and (
					not cur or frappe.db.get_value("Production Unit", cur, "status") == "Retired"):
				frappe.db.set_value("Harvest Team", name, "unit", unit, update_modified=False)
			continue
		if li >= len(leaders):
			continue
		doc = frappe.get_doc({"doctype": "Harvest Team", "team_number": number, "team_leader": leaders[li],
			"farm": BASE["farm"]["name"], "unit": unit if frappe.db.exists("Production Unit", unit) else None,
			"harvestors": [{"employee": e} for e in pickers[ps]]})
		doc.insert(ignore_permissions=True)
		out[number] = doc.name
	return out


def _free_crates(n: int) -> list[str]:
	used = set(frappe.get_all("Harvest Crate Scan", filters={"status": ("in", ("Filling", "Full"))}, pluck="crate_id"))
	batched_today = set(frappe.get_all("Harvest Crate Scan", filters={"creation": (">=", f"{today()} 00:00:00")}, pluck="crate_id"))
	out = []
	for cid in frappe.get_all("Harvest Crate", filters={"status": "Active"}, pluck="name", order_by="serial_no asc", limit_page_length=0):
		if cid not in used and cid not in batched_today:
			out.append(cid)
			if len(out) == n:
				break
	return out


def seed_batches(teams: dict) -> int:
	"""Scan crates picker by picker, then close each batch. Skipped once the seeded batches exist (on
	any day: the batch date is today, so a date key would add a new set of batches every day)."""
	made = 0
	if frappe.db.exists("Harvest Batch", {"team": ("in", list(teams.values())), "docstatus": 1}):
		return 0
	for number, unit, crates, close in BATCHES:
		team = teams.get(number)
		if not team or not frappe.db.exists("Production Unit", unit):
			continue
		members = frappe.get_all("Harvest Team Member", filters={"parent": team}, pluck="employee", order_by="idx asc")
		ids = _free_crates(crates)
		for i, emp in enumerate(members):
			chunk = ids[i::len(members)]
			if chunk:
				res = api.scan_crates_bulk(crate_ids=chunk, team_id=number, block=unit, harvestor=emp)
				assert not res.get("error") and not res["fail_count"], res
		if close:
			res = api.mark_ready_for_collection(block=unit, team_id=number)
			assert not res.get("error"), res
			made += 1
	return made


def run():
	setup_masters()
	crates = seed_crates()
	teams = seed_teams()
	batches = seed_batches(teams)
	frappe.db.commit()
	print(f"[harvest_seed] crates +{crates}, teams {len(teams)}, batches +{batches}")
