"""Idempotent demo data for establishment costs, opening balances, protocol buffers and dry matter tests.

bench --site mutara.local execute upande_production.production.demo.establishment_seed.run

Runs after the varieties and rules seeds (it needs their protocols, cycles and the activity lists).
Establishment costs are keyed on their `reference`; opening balances on the block; the protocol rows on
(activity, week) / activity; dry matter tests on the demo potato blocks, whose tests are replaced because
their dates are relative to today. Every invented figure is in DEMO.
"""

import random

import frappe
from frappe.utils import add_days, cint, flt, getdate, nowdate

from upande_production.production.demo import real_blocks
from upande_production.production.logic import cycle_chain, stages
from upande_production.production.logic.units import unit_filter

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
		("Avocado", "phase-1-2018", "2018-03-15", "PH1_OLD"),
		("Avocado", "phase-1-2023", "2023-03-20", "PH1_NEW"),
		("Avocado", "phase-2-2020", "2020-03-10", "PH2_OLD"),
		("Avocado", "phase-2-2024", "2024-03-18", "PH2_NEW"),
		("Fruits & Vegetables", "pivot-1", "2026-02-20", ["Pivot 1"]),
		("Fruits & Vegetables", "pivot-2", "2026-02-27", ["Pivot 2"]),
	],
	# explicit costs: (crop, label, operation, date, amount, units, split method)
	"fixed": [
		("Fruits & Vegetables", "irrigation", "Irrigation system installation", "2026-01-20", 2400000,
			["Pivot 1", "Pivot 2"], "By area"),
		("Aquaculture", "ponds", "Pond excavation", "2025-11-10", 720000, ["Pond 1", "Pond 2", "Pond 3", "Pond 4"], "By area"),
		("Aquaculture", "ponds", "Pond liner", "2025-11-25", 380000, ["Pond 1", "Pond 2", "Pond 3", "Pond 4"], "By area"),
		("Aquaculture", "ponds", "Inlet and outlet works", "2025-12-05", 160000, ["Pond 1", "Pond 2", "Pond 3", "Pond 4"], "By area"),
		("Aquaculture", "ponds", "Aerator installation", "2025-12-18", 260000, ["Pond 1", "Pond 2", "Pond 3", "Pond 4"], "By area"),
		("Apiary", "hives", "Hive stands", "2025-09-12", 90000, ["Hive Group North", "Hive Group South"], "Manual"),
		("Apiary", "hives", "Hives", "2025-09-20", 420000, ["Hive Group North", "Hive Group South"], "Manual"),
		("Apiary", "hives", "Apiary fencing", "2025-10-02", 70000, ["Hive Group North", "Hive Group South"], "Manual"),
	],
	# mature blocks: setup cost = their establishment costs, plus history to the as-of date
	# (the opening balances are derived from the bearing avocado blocks: see seed_opening_balances)
	"old_planting_to": 2021,  # avocado planted up to this year is the old cohort of its phase
	"opening": {"as_of_date": "2026-01-01", "running_cost_per_ha": (190000, 230000), "value_per_ha": (260000, 320000),
		"planted_offset_days": (10, 40), "note": "Opened from the paper records before the system went live."},
	# Active protocols by item (variety items map to their product): buffers and extra activities.
	# phi days: avocado 21; potatoes, cabbage, onion 14; passion fruit 7. establishment weeks for spraying 2.
	"phi_days": {"Hass Avocado": 21, "Fuerte Avocado": 21, "Potatoes": 14, "Cabbage": 14, "Onion": 14, "Passion Fruit": 7, "Maize": 14},
	"spray_establishment_weeks": 2,
	# product -> key rows (operation, week, repeats, description)
	"key": {
		"Hass Avocado": [("Bending", 7, "Every cycle", "Bend the young shoots to set the canopy")],
		"Fuerte Avocado": [("Bending", 7, "Every cycle", "Bend the young shoots to set the canopy")],
		"Potatoes": [("Gap filling", 2, "First cycle only", "Replace missed seed tubers"),
			("Earthing Up", 4, "Every cycle", None)],
		"Cabbage": [("Gap filling", 2, "First cycle only", "Replace dead transplants")],
		"Onion": [("Gap filling", 2, "First cycle only", "Replace dead transplants")],
		"Maize": [("Gap filling", 2, "First cycle only", "Replace missed seed")],
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
		"Maize": [("Spraying", "Interval", 2, 2, None), ("Weeding", "Interval", 3, 0, None),
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
		"Onion": 80000, "Passion Fruit": 110000, "Maize": 30000},
	# dry matter by product: (start % low, start % high, gain per week low, gain per week high). The variety's
	# own settings (test?, part, target, sampling stage) decide which blocks are tested at all.
	"dm_visits": 3,
	"dm_samples": 5,
	"dm_ranges": {"Potatoes": (13.0, 18.5, 0.7, 1.3), "Onion": (7.0, 10.0, 0.4, 0.7), "Cabbage": (5.0, 7.0, 0.3, 0.5)},
	# Actual flowering as weeks after the expected date, for the non-anchored blocks (passion fruit): one
	# block three weeks late gives the manager one flag. An avocado first cycle is anchored on flowering, so
	# it has no flowering flag of its own; the first active avocado block is three weeks late (the plan's case).
	"flowering_actuals": {"P1-B11": 3, "P2-B8": 0, "P2-B11": -1},
	"avocado_flowering_late": {"PH1-B1": 3},
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


def _set_units(units):
	"""A set's units: a list of unit names, or one of the avocado cohort keys (phase + planting-year group)."""
	if isinstance(units, str):
		phase, which = units.split("_")
		phase_name = f"Phase {phase[2]}"
		old = DEMO["old_planting_to"]
		return [b["name"] for b in real_blocks.avocado_blocks()
			if b["phase"] == phase_name and (b["planting_year"] <= old) == (which == "OLD")]
	return units


def seed_costs():
	made = 0
	for crop, label, date, units in DEMO["sets"]:
		units = _set_units(units)
		if not units or not all(frappe.db.exists("Production Unit", u) for u in units):
			continue
		area = sum(flt(frappe.db.get_value("Production Unit", u, "area_ha")) for u in units)
		for op, per_ha in DEMO["per_ha"][crop]:
			made += _make_cost(f"demo-estab-{label}-{op}", crop, op, date, round(per_ha * area, 2), units, "By area")
	for crop, label, op, date, amount, units, method in DEMO["fixed"]:
		if all(frappe.db.exists("Production Unit", u) for u in units):
			made += _make_cost(f"demo-estab-{label}-{op}", crop, op, date, amount, units, method)
	return made


def seed_opening_balances():
	"""Mature (bearing, picking) avocado blocks open with paper-record history; figures are per ha of the
	block's survey area, a stable pick per block."""
	from upande_production.production.logic import establishment

	cfg = DEMO["opening"]
	made = 0
	for b in real_blocks.active_avocado():
		unit = b["name"]
		if not frappe.db.exists("Production Unit", unit):
			continue
		r = random.Random(f"{DEMO['seed']}:open:{unit}")
		setup = sum(establishment.cost_by_unit([unit]).values())
		planted = add_days(getdate(f"{b['planting_year']}-04-01"), r.randint(*cfg["planted_offset_days"]))
		data = {"as_of_date": cfg["as_of_date"], "planted_on": planted,
			"running_costs_to_date": round(b["area"] * r.uniform(*cfg["running_cost_per_ha"]), -3),
			"value_recovered_to_date": round(b["area"] * r.uniform(*cfg["value_per_ha"]), -3), "note": cfg["note"],
			"setup_cost": round(setup, 2), "crop": frappe.db.get_value("Production Unit", unit, "crop")}
		if frappe.db.exists("Block Opening Balance", unit):
			doc = frappe.get_doc("Block Opening Balance", unit)
			if str(doc.as_of_date) == cfg["as_of_date"] and doc.running_costs_to_date:
				continue  # already opened: the seed leaves a block's balance alone
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
	"""Tests on the blocks whose variety is tested and whose cycle has reached the sampling stage: weekly,
	rising toward the variety's target. Every fifth such block has never been sampled and every third was
	last sampled a week ago, so the Dry Matter pages show blocks that are due. Test dates are relative to
	today: the seed's tests on these blocks that fall on other dates are replaced; a second run on the
	same day changes nothing."""
	from upande_production.production.logic import drymatter

	crop = "Fruits & Vegetables"
	rows = [r for r in drymatter.due_rows(crop)["rows"] if r["state"] != "not_yet"]
	rows.sort(key=lambda r: r["unit"])
	today = getdate(nowdate())
	wanted = {}
	for i, r in enumerate(rows):
		if i % 5 == 4:
			continue  # never sampled
		product = stages.product_item(frappe.db.get_value("Production Crop Cycle", r["cycle"], "item"))
		rng = random.Random(f"{DEMO['seed']}:dm:{r['unit']}")
		lo, hi, glo, ghi = DEMO["dm_ranges"][product]
		start, gain = rng.uniform(lo, hi), rng.uniform(glo, ghi)
		shift = 7 if i % 3 == 0 else 0
		for v in range(DEMO["dm_visits"]):
			mean = start + gain * v
			samples = [round(mean + rng.uniform(-0.6, 0.6), 1) for _ in range(DEMO["dm_samples"])]
			wanted[(r["unit"], str(add_days(today, -7 * (DEMO["dm_visits"] - 1 - v) - shift)))] = (r, samples)
	units = {r["unit"] for r in rows}
	for t in frappe.get_all("Dry Matter Test", filters={"unit": ("in", list(units) or [""])},
			fields=["name", "unit", "test_date"], limit_page_length=0):
		if (t.unit, str(t.test_date)) not in wanted:
			frappe.delete_doc("Dry Matter Test", t.name, force=True, ignore_permissions=True)
	made = 0
	for (unit, date), (r, samples) in wanted.items():
		if frappe.db.exists("Dry Matter Test", {"unit": unit, "test_date": date}):
			continue
		frappe.get_doc({"doctype": "Dry Matter Test", "unit": unit, "cycle": r["cycle"], "variety": r["variety"],
			"crop": crop, "test_date": date,
			"samples": [{"sample_no": k + 1, "dry_matter_pct": v} for k, v in enumerate(samples)],
		}).insert(ignore_permissions=True)
		made += 1
	return made


# ------------------------------------------------------------------ cycles and flags

def _first_pick(cycle):
	return frappe.db.sql("""select min(harvest_date) from `tabProduction Harvest`
		where cycle = %s or (unit = %s and ifnull(cycle, '') = '')""", (cycle.name, cycle.unit))[0][0]


def _fit_season(doc, first, late) -> bool:
	"""A seasonal cycle takes the season whose flowering (+ the late weeks) plus its weeks to harvest lands
	closest to the first recorded pick, so a demo harvest is never flagged late for the wrong season. A
	changed season drops the unused Planned successor proposed from the old one."""
	v = cycle_chain._variety(doc)
	if not cycle_chain._is_seasonal(v):
		return False
	first = getdate(first)
	best = None
	for r in v.seasons:
		for year in (first.year - 2, first.year - 1, first.year):
			d = getdate(f"{year}-{cycle_chain._month_no(r):02d}-01")
			miss = abs((add_days(d, (cint(r["weeks_flowering_to_harvest"]) + late) * 7) - first).days)
			if best is None or miss < best[0]:
				best = (miss, r, d)
	_miss, row, d = best
	if doc.flowering_season == row["season_name"] and getdate(doc.expected_flowering_date) == d:
		return False
	nxt = doc.proposed_next_cycle
	if nxt and frappe.db.get_value("Production Crop Cycle", nxt, "status") == "Planned":
		doc.proposed_next_cycle = None
		frappe.db.set_value("Production Crop Cycle", doc.name, "proposed_next_cycle", None, update_modified=False)
		frappe.delete_doc("Production Crop Cycle", nxt, force=1, ignore_permissions=True)
	doc.flowering_season, doc.expected_flowering_date = row["season_name"], d
	doc.actual_flowering_date = None
	return True


def align_cycles():
	"""Make the open cycles agree with their own picks and variety timeline, so the only manager flags
	left are the deliberate ones. A cycle that is picking gets the start date at which its variety's
	harvest stage falls on the first recorded pick; an avocado season (anchored on flowering) starts at
	the flowering of the season its picks belong to, and records the flowering `late_weeks` after that."""
	changed = 0
	for cy in frappe.get_all("Production Crop Cycle", filters=unit_filter({"status": "Harvesting", "variety": ("is", "set")}),
			fields=["name", "unit", "variety"]):
		first = _first_pick(cy)
		spec = next((v for v in __import__("upande_production.production.demo.varieties_seed",
			fromlist=["DEMO"]).DEMO["varieties"] if v["name"] == cy.variety), None)
		hs = next((st for st in (spec or {}).get("stages", []) if len(st) > 3 and st[3]), None)
		if not (first and hs):
			continue
		anchored = spec["anchor"] == "Flowering"
		late = {**DEMO["flowering_actuals"], **DEMO["avocado_flowering_late"]}.get(cy.unit, 0)  # later stages move with the flowering actual
		start = add_days(getdate(first), -hs[1] - late * 7)
		doc = frappe.get_doc("Production Crop Cycle", cy.name)
		dirty = getdate(doc.start_date) != start
		if dirty:
			doc.start_date = start
		if anchored:
			want = add_days(start, late * 7)
			if doc.flowering_season and doc.expected_flowering_date:  # seasonal: late against its season start
				if _fit_season(doc, first, late):
					dirty = True
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
