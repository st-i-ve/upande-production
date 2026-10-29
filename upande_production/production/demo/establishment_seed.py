"""Idempotent demo data for establishment costs, opening balances, protocol buffers and dry matter tests.

bench --site mutara.local execute upande_production.production.demo.establishment_seed.run

Runs after the varieties and rules seeds (it needs their protocols, cycles and the activity lists).
Establishment costs are keyed on their `reference`; opening balances on the block; the protocol rows on
(activity, week) / activity; dry matter tests on the demo potato blocks, whose tests are replaced because
their dates are relative to today. Every invented figure is in DEMO.
"""

import random

import frappe
from frappe.utils import add_days, flt, getdate, nowdate

from upande_production.production.logic import cycle_chain, stages

PHI_BY_PRODUCT = "phi_days"

DEMO = {
	"seed": 20261028,
	# KES per ha, by crop; applied to each set of blocks below.
	"per_ha": {
		"Avocado": [("Bush clearing", 25000), ("Single ripping", 18000), ("Cross ripping", 15000),
			("Marking of ridges", 4000), ("Fertiliser application (basal)", 30000), ("Planting material", 120000),
			("Windbreak planting", 8000)],
		"Fruits & Vegetables": [("Bush clearing", 25000), ("Single ripping", 18000), ("Cross ripping", 15000),
			("Disc harrowing", 9000), ("Marking of ridges", 4000), ("Ridge-line ripping", 12000), ("Ridging", 10000),
			("Fertiliser application (basal)", 30000), ("Planting material", 90000), ("Windbreak planting", 8000)],
	},
	# sets of blocks costed together (one cost per activity, split by area): (crop, label, date, units)
	"sets": [
		("Avocado", "avocado", "2023-03-15", ["Avocado Block A", "Avocado Block B"]),
		("Fruits & Vegetables", "pivot-1", "2026-02-20", ["Pivot 1"]),
		("Fruits & Vegetables", "pivot-2", "2026-02-27", ["Pivot 2"]),
		("Fruits & Vegetables", "pivot-3", "2026-03-06", ["Pivot 3"]),
		("Fruits & Vegetables", "pivot-4", "2026-02-10", ["Pivot 4"]),
	],
	# explicit costs: (crop, label, operation, date, amount, units, split method)
	"fixed": [
		("Fruits & Vegetables", "irrigation", "Irrigation system installation", "2026-01-20", 2400000,
			["Pivot 1", "Pivot 2", "Pivot 3", "Pivot 4"], "By area"),
		("Aquaculture", "ponds", "Pond excavation", "2025-11-10", 720000, ["Pond 1", "Pond 2", "Pond 3", "Pond 4"], "By area"),
		("Aquaculture", "ponds", "Pond liner", "2025-11-25", 380000, ["Pond 1", "Pond 2", "Pond 3", "Pond 4"], "By area"),
		("Aquaculture", "ponds", "Inlet and outlet works", "2025-12-05", 160000, ["Pond 1", "Pond 2", "Pond 3", "Pond 4"], "By area"),
		("Aquaculture", "ponds", "Aerator installation", "2025-12-18", 260000, ["Pond 1", "Pond 2", "Pond 3", "Pond 4"], "By area"),
		("Apiary", "hives", "Hive stands", "2025-09-12", 90000, ["Hive Group North", "Hive Group South"], "Manual"),
		("Apiary", "hives", "Hives", "2025-09-20", 420000, ["Hive Group North", "Hive Group South"], "Manual"),
		("Apiary", "hives", "Apiary fencing", "2025-10-02", 70000, ["Hive Group North", "Hive Group South"], "Manual"),
	],
	# mature blocks: setup cost = their establishment costs, plus history to the as-of date
	"opening_balances": {
		"Avocado Block A": {"as_of_date": "2026-01-01", "planted_on": "2023-04-10", "running_costs_to_date": 1850000,
			"value_recovered_to_date": 2600000, "note": "Opened from the paper records before the system went live."},
		"Avocado Block B": {"as_of_date": "2026-01-01", "planted_on": "2023-05-02", "running_costs_to_date": 1480000,
			"value_recovered_to_date": 1900000, "note": "Opened from the paper records before the system went live."},
	},
	# Active protocols by item (variety items map to their product): buffers and extra activities.
	# phi days: avocado 21; potatoes, cabbage, onion 14; passion fruit 7. establishment weeks for spraying 2.
	"phi_days": {"Hass Avocado": 21, "Fuerte Avocado": 21, "Potatoes": 14, "Cabbage": 14, "Onion": 14, "Passion Fruit": 7},
	"spray_establishment_weeks": 2,
	# product -> key rows (operation, week, repeats, description)
	"key": {
		"Hass Avocado": [("Bending", 7, "Every cycle", "Bend the young shoots to set the canopy")],
		"Fuerte Avocado": [("Bending", 7, "Every cycle", "Bend the young shoots to set the canopy")],
		"Potatoes": [("Gap filling", 2, "First cycle only", "Replace missed seed tubers"),
			("Earthing Up", 4, "Every cycle", None)],
		"Cabbage": [("Gap filling", 2, "First cycle only", "Replace dead transplants")],
		"Onion": [("Gap filling", 2, "First cycle only", "Replace dead transplants")],
		"Passion Fruit": [("Gap filling", 2, "First cycle only", "Replace dead seedlings"),
			("Seedling support (staking)", 3, "First cycle only", "Stake and tie the young vines")],
	},
	# product -> cultural rows (operation, schedule, interval weeks, establishment weeks, description)
	"cultural": {
		"Hass Avocado": [("Spraying", "Interval", 2, 2, None), ("Weeding", "Interval", 3, 0, None),
			("Mulching", "As needed", None, 0, None), ("Pest management", "As needed", None, 0, None)],
		"Fuerte Avocado": [("Spraying", "Interval", 2, 2, None), ("Weeding", "Interval", 3, 0, None),
			("Mulching", "As needed", None, 0, None), ("Pest management", "As needed", None, 0, None)],
		"Potatoes": [("Spraying", "Interval", 2, 2, None), ("Weeding", "Interval", 3, 0, None),
			("Irrigating", "Interval", 1, 0, None), ("Mulching", "As needed", None, 0, None),
			("Pest management", "As needed", None, 0, None)],
		"Cabbage": [("Spraying", "Interval", 2, 2, None), ("Weeding", "Interval", 3, 0, None),
			("Irrigating", "Interval", 1, 0, None), ("Pest management", "As needed", None, 0, None)],
		"Onion": [("Spraying", "Interval", 2, 2, None), ("Weeding", "Interval", 3, 0, None),
			("Irrigating", "Interval", 1, 0, None), ("Pest management", "As needed", None, 0, None)],
		"Passion Fruit": [("Spraying", "Interval", 2, 2, None), ("Weeding", "Interval", 3, 0, None),
			("Irrigating", "Interval", 1, 0, None), ("Mulching", "As needed", None, 0, None),
			("Pest management", "As needed", None, 0, None)],
	},
	# capital rows of a protocol: crop -> [(operation, budget per ha)]; planting material by product
	"capital": {
		"Avocado": [("Bush clearing", 25000), ("Single ripping", 18000), ("Cross ripping", 15000),
			("Marking of ridges", 4000), ("Fertiliser application (basal)", 30000), ("Windbreak planting", 8000)],
		"Fruits & Vegetables": [("Bush clearing", 25000), ("Single ripping", 18000), ("Cross ripping", 15000),
			("Disc harrowing", 9000), ("Marking of ridges", 4000), ("Ridge-line ripping", 12000), ("Ridging", 10000),
			("Fertiliser application (basal)", 30000), ("Windbreak planting", 8000)],
		"Apiary": [("Hive stands", None), ("Hives", None), ("Apiary fencing", None)],
		"Aquaculture": [("Pond excavation", 1800000), ("Pond liner", 950000), ("Inlet and outlet works", 400000),
			("Aerator installation", 650000)],
	},
	"planting_material": {"Hass Avocado": 120000, "Fuerte Avocado": 120000, "Potatoes": 90000, "Cabbage": 60000,
		"Onion": 80000, "Passion Fruit": 110000},
	# potato blocks tested over the last 3 weeks: unit -> (dry matter % 3 weeks ago, gain per week).
	# The older blocks reach the 20% target, the young ones are still rising.
	"dry_matter": {"P2-B3": (17.8, 1.3), "P1-B2": (15.2, 0.9), "P1-B1": (13.9, 0.8), "P2-B4": (13.1, 0.7)},
	"dm_visits": 3,
	"dm_samples": 5,
	# Actual flowering as weeks after the expected date. Block A is three weeks late (the plan's case; an
	# avocado first cycle is anchored on flowering, so it has no flowering flag of its own); the passion
	# blocks are recorded too (P4-B1 three weeks late: one manager flag), so only that one is off protocol.
	"flowering_actuals": {"Avocado Block A": 3, "Avocado Block B": 0, "P4-B1": 3, "P4-B2": 0, "P4-B3": -1, "P4-B4": 1},
}


def _op(crop, name):
	return frappe.db.get_value("Production Operation", {"crop": crop, "operation_name": name}, "name")


# ------------------------------------------------------------------ establishment costs

def _make_cost(ref, crop, op, date, amount, units, method):
	if frappe.db.exists("Block Establishment Cost", {"reference": ref, "docstatus": ("!=", 2)}):
		return False
	operation = _op(crop, op)
	if not operation:
		return False
	doc = frappe.get_doc({"doctype": "Block Establishment Cost", "crop": crop, "posting_date": date,
		"operation": operation, "amount": amount, "reference": ref, "split_method": method,
		"paid_to": "Demo contractor", "blocks": [{"unit": u, "share_pct": 100 / len(units)} for u in units]})
	doc.farm = frappe.db.get_value("Production Unit", units[0], "farm")
	doc.insert(ignore_permissions=True)
	doc.submit()
	return True


def seed_costs():
	made = 0
	for crop, label, date, units in DEMO["sets"]:
		if not all(frappe.db.exists("Production Unit", u) for u in units):
			continue
		area = sum(flt(frappe.db.get_value("Production Unit", u, "area_ha")) for u in units)
		for op, per_ha in DEMO["per_ha"][crop]:
			made += _make_cost(f"demo-estab-{label}-{op}", crop, op, date, round(per_ha * area, 2), units, "By area")
	for crop, label, op, date, amount, units, method in DEMO["fixed"]:
		if all(frappe.db.exists("Production Unit", u) for u in units):
			made += _make_cost(f"demo-estab-{label}-{op}", crop, op, date, amount, units, method)
	return made


def seed_opening_balances():
	from upande_production.production.logic import establishment

	made = 0
	for unit, vals in DEMO["opening_balances"].items():
		if not frappe.db.exists("Production Unit", unit):
			continue
		setup = sum(establishment.cost_by_unit([unit]).values())
		data = {**vals, "setup_cost": round(setup, 2),
			"crop": frappe.db.get_value("Production Unit", unit, "crop")}
		if frappe.db.exists("Block Opening Balance", unit):
			doc = frappe.get_doc("Block Opening Balance", unit)
			doc.update(data)
			doc.save(ignore_permissions=True)
		else:
			frappe.get_doc({"doctype": "Block Opening Balance", "unit": unit, **data}).insert(ignore_permissions=True)
			made += 1
	return made


# ------------------------------------------------------------------ protocols

def _product(item):
	return stages.product_item(item)


def extend_protocols():
	"""Add the buffers, key and cultural rows and capital budgets to every Active protocol."""
	touched = 0
	for name in frappe.get_all("Production Protocol", filters={"version_status": "Active"}, pluck="name"):
		doc = frappe.get_doc("Production Protocol", name)
		product = _product(doc.item) if doc.item else None
		crop = doc.crop
		changed = False

		have_cap = {r.operation: r for r in doc.get("capital_activities") or []}
		caps = list(DEMO["capital"].get(crop, []))
		if product in DEMO["planting_material"] and crop in ("Avocado", "Fruits & Vegetables"):
			caps.append(("Planting material", DEMO["planting_material"][product]))
		for opname, budget in caps:
			op = _op(crop, opname)
			if not op:
				continue
			row = have_cap.get(op)
			if row is None:
				doc.append("capital_activities", {"operation": op, "budget_per_ha": budget})
				changed = True
			elif budget and flt(row.budget_per_ha) != budget:
				row.budget_per_ha = budget
				changed = True

		keys = {(r.operation, ): r for r in doc.get("key_activities") or []}
		for opname, week, repeats, desc in DEMO["key"].get(product, []):
			op = _op(crop, opname)
			if op and (op,) not in keys:
				doc.append("key_activities", {"operation": op, "week": week, "repeats": repeats,
					"description": desc, "planned_qty": None})
				changed = True
		if changed or doc.get("key_activities"):
			ordered = sorted(doc.key_activities, key=lambda r: (r.week or 0))
			if [r.name for r in ordered] != [r.name for r in doc.key_activities] or any(not r.name for r in ordered):
				rows = [r.as_dict() for r in ordered]
				for i, r in enumerate(rows, 1):
					r.pop("name", None)
					r["idx"] = i
				doc.set("key_activities", rows)
				changed = True

		phi = DEMO["phi_days"].get(product)
		cult = {r.operation: r for r in doc.get("cultural_activities") or []}
		for opname, sched, interval, estab, desc in DEMO["cultural"].get(product, []):
			op = _op(crop, opname)
			if not op:
				continue
			row = cult.get(op)
			if row is None:
				row = doc.append("cultural_activities", {"operation": op, "schedule": sched,
					"interval_weeks": interval, "description": desc})
				cult[op] = row
				changed = True
			if opname == "Spraying":
				want = {"establishment_period_weeks": estab, "pre_harvest_interval_days": phi}
			else:
				want = {"establishment_period_weeks": estab if not row.establishment_period_weeks else row.establishment_period_weeks}
			for k, v in want.items():
				if v is not None and (row.get(k) or 0) != v:
					row.set(k, v)
					changed = True
		if changed:
			doc.flags.protocol_transition = True
			doc.save(ignore_permissions=True)
			touched += 1
	return touched


# ------------------------------------------------------------------ dry matter tests

def seed_dry_matter_tests():
	"""Potato slice tests, weekly, rising to target. The tests of the demo potato blocks are replaced
	on every run: their dates are relative to today."""
	crop = "Fruits & Vegetables"
	if not frappe.db.get_value("Production Crop", crop, "dry_matter_testing"):
		return 0
	units = [u for u in DEMO["dry_matter"] if frappe.db.exists("Production Unit", u)]
	for n in frappe.get_all("Dry Matter Test", filters={"unit": ("in", units)}, pluck="name", limit_page_length=0):
		frappe.delete_doc("Dry Matter Test", n, force=True, ignore_permissions=True)
	made = 0
	today = getdate(nowdate())
	for unit in units:
		start, gain = DEMO["dry_matter"][unit]
		cycle = frappe.db.get_value("Production Crop Cycle", {"unit": unit, "status": ("in", ["Active", "Harvesting"])},
			["name", "variety"], as_dict=True)
		rng = random.Random(f"{DEMO['seed']}:dm:{unit}")
		for i in range(DEMO["dm_visits"]):
			mean = start + gain * i
			samples = [{"sample_no": k + 1, "dry_matter_pct": round(mean + rng.uniform(-0.6, 0.6), 1)}
				for k in range(DEMO["dm_samples"])]
			frappe.get_doc({"doctype": "Dry Matter Test", "unit": unit, "cycle": cycle.name if cycle else None,
				"variety": cycle.variety if cycle else None, "crop": crop,
				"test_date": add_days(today, -7 * (DEMO["dm_visits"] - 1 - i)), "samples": samples,
			}).insert(ignore_permissions=True)
			made += 1
	return made


# ------------------------------------------------------------------ cycles and flags

def _first_pick(cycle):
	return frappe.db.sql("""select min(harvest_date) from `tabProduction Harvest`
		where cycle = %s or (unit = %s and ifnull(cycle, '') = '')""", (cycle.name, cycle.unit))[0][0]


def align_cycles():
	"""Make the open cycles agree with their own picks and variety timeline, so the only manager flags
	left are the deliberate ones. A cycle that is picking gets the start date at which its variety's
	harvest stage falls on the first recorded pick; an avocado season (anchored on flowering) starts at
	the flowering of the season its picks belong to, and records the flowering `late_weeks` after that."""
	changed = 0
	for cy in frappe.get_all("Production Crop Cycle", filters={"status": "Harvesting", "variety": ("is", "set")},
			fields=["name", "unit", "variety"]):
		first = _first_pick(cy)
		spec = next((v for v in __import__("upande_production.production.demo.varieties_seed",
			fromlist=["DEMO"]).DEMO["varieties"] if v["name"] == cy.variety), None)
		hs = next((st for st in (spec or {}).get("stages", []) if len(st) > 3 and st[3]), None)
		if not (first and hs):
			continue
		anchored = spec["anchor"] == "Flowering"
		late = DEMO["flowering_actuals"].get(cy.unit, 0)  # later stages move with the flowering actual
		start = add_days(getdate(first), -hs[1] - late * 7)
		doc = frappe.get_doc("Production Crop Cycle", cy.name)
		dirty = getdate(doc.start_date) != start
		if dirty:
			doc.start_date = start
		if anchored:
			want = add_days(start, late * 7)
			if doc.flowering_season and doc.expected_flowering_date:  # seasonal: late against its season start
				want = add_days(getdate(doc.expected_flowering_date), late * 7)
			if getdate(doc.actual_flowering_date or "1900-01-01") != want:
				doc.actual_flowering_date = want
				dirty = True
		exp = add_days(getdate(first), 0)
		if not doc.expected_harvest_start or getdate(doc.expected_harvest_start) != exp:
			doc.expected_harvest_start = exp
			doc.expected_harvest_end = add_days(exp, hs[2])
			dirty = True
		if dirty:
			doc.save(ignore_permissions=True)
			changed += 1
			print("  aligned", cy.unit)
	return changed


def seed_flags():
	"""Record the actual flowering of the non-anchored blocks (expected + weeks), then refresh flags."""
	for unit, weeks in DEMO["flowering_actuals"].items():
		name = frappe.db.get_value("Production Crop Cycle", {"unit": unit, "status": ("in", ["Active", "Harvesting"])})
		if not name:
			continue
		doc = frappe.get_doc("Production Crop Cycle", name)
		v = frappe.db.get_value("Production Variety", doc.variety, "stage_anchor")
		if v == "Flowering" or not doc.expected_flowering_date:
			continue
		want = add_days(getdate(doc.expected_flowering_date), weeks * 7)
		if getdate(doc.actual_flowering_date or "1900-01-01") != want:
			doc.actual_flowering_date = want
			doc.save(ignore_permissions=True)
	return cycle_chain.refresh_flags_all()


def run(commit=True):
	frappe.flags.in_demo_seed = True
	frappe.flags.skip_activity_rules = True
	try:
		out = {"protocols_extended": extend_protocols()}
		out["establishment_costs_created"] = seed_costs()
		out["opening_balances_created"] = seed_opening_balances()
		out["dry_matter_tests_created"] = seed_dry_matter_tests()
		out["cycles_aligned"] = align_cycles()
		out["cycles_flagged"] = seed_flags()
	finally:
		frappe.flags.in_demo_seed = False
		frappe.flags.skip_activity_rules = False
	if commit:
		frappe.db.commit()
	print(f"establishment seed: {out}")
	return out
