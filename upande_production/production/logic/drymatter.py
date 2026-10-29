"""Dry matter sampling per variety and stage.

Whether a crop's produce is tested for dry matter, on which part, to what target and from which growth
stage sampling is due are settings of the *variety*; the crop holds the default a variety inherits when it
says nothing. A block is due for sampling when its open cycle is in or past the variety's sampling stage
and nothing has been tested on it in the last `dry_matter_retest_days` (Production Settings).
"""

import frappe
from frappe.utils import add_days, cint, flt, getdate, today

from upande_production.production.logic import stages
from upande_production.production.logic.units import retired_units

PARTS = ("Fruit", "Tuber", "Bulb", "Head", "Leaf")
DEFAULT_RETEST_DAYS = 7


def retest_days() -> int:
	val = frappe.db.get_single_value("Production Settings", "dry_matter_retest_days")
	return cint(val) or DEFAULT_RETEST_DAYS


def rules_for(variety, crop) -> dict:
	"""{testing, on, target, from_stage} for a variety under its crop: the variety's own setting, else the crop's."""
	c = frappe.db.get_value("Production Crop", crop, ["dry_matter_testing", "dry_matter_on", "dry_matter_target_pct"],
		as_dict=True) or frappe._dict()
	v = (frappe.db.get_value("Production Variety", variety,
		["dry_matter_testing", "dry_matter_on", "dry_matter_target_pct", "dry_matter_from_stage"], as_dict=True)
		if variety else None) or frappe._dict()
	testing = {"Yes": 1, "No": 0}.get(v.get("dry_matter_testing"), cint(c.get("dry_matter_testing")))
	return {
		"testing": int(testing),
		"on": v.get("dry_matter_on") or c.get("dry_matter_on") or None,
		"target": flt(v.get("dry_matter_target_pct")) or flt(c.get("dry_matter_target_pct")) or None,
		"from_stage": v.get("dry_matter_from_stage") or None,
	}


def crop_tests_dry_matter(crop) -> bool:
	"""True when the crop's default is on or any of its enabled varieties says Yes (what the page gate asks)."""
	if cint(frappe.db.get_value("Production Crop", crop, "dry_matter_testing")):
		return True
	return bool(frappe.db.exists("Production Variety", {"crop": crop, "enabled": 1, "dry_matter_testing": "Yes"}))


def cycle_on(unit, on_date=None):
	"""The unit's cycle running on a date: the latest one started on or before it (any status)."""
	return frappe.db.get_value("Production Crop Cycle", {"unit": unit, "start_date": ("<=", getdate(on_date or today()))},
		"name", order_by="start_date desc, creation desc")


def stage_of_cycle(cycle, on_date=None):
	"""The cycle's stage name on a date; None without a cycle or a variety timeline."""
	if not cycle:
		return None
	try:
		return stages.stage_on(cycle, on_date)["stage"]
	except Exception:
		return None


def stage_index(variety, stage):
	"""Position of a stage in the variety's timeline (None when unknown)."""
	names = [r.stage for r in frappe.get_all("Production Variety Stage", filters={"parent": variety, "parenttype": "Production Variety"},
		fields=["stage"], order_by="idx asc")]
	return names.index(stage) if stage in names else None


def reached(variety, stage, from_stage) -> bool:
	"""Is `stage` the sampling stage or a later one? No sampling stage set means always; an unknown stage means no."""
	if not from_stage:
		return True
	if not stage:
		return False
	a, b = stage_index(variety, stage), stage_index(variety, from_stage)
	return a is not None and b is not None and a >= b


def last_tests(units, dt="Dry Matter Test", unit_field="unit", date_field="test_date") -> dict:
	"""{unit: (date, name)} of each unit's most recent test."""
	out = {}
	for r in frappe.get_all(dt, filters={unit_field: ("in", list(units) or [""])}, fields=["name", unit_field, date_field],
			order_by=f"{date_field} asc, creation asc", limit_page_length=0):
		out[r[unit_field]] = (getdate(r[date_field]), r.name)
	return out


def due_rows(crop, on_date=None) -> dict:
	"""Every block of the crop whose open cycle's variety is tested: where it stands against the sampling stage.

	state: due (in or past the stage, no test in the retest window), recent (tested inside it),
	not_yet (still before the sampling stage). Sorted: due first, longest untested first."""
	on = getdate(on_date or today())
	days = retest_days()
	gone = retired_units()
	cycles = frappe.get_all("Production Crop Cycle", filters={"crop": crop, "status": ("in", ["Active", "Harvesting"])},
		fields=["name", "unit", "variety", "start_date"], order_by="start_date asc", limit_page_length=0)
	by_unit = {c.unit: c for c in cycles if c.unit not in gone}
	areas = {u.name: u for u in frappe.get_all("Production Unit", filters={"name": ("in", list(by_unit) or [""]), "is_group": 0},
		fields=["name", "area_ha"], limit_page_length=0)}
	last = last_tests(by_unit)
	latest_pct = {}
	for r in frappe.get_all("Dry Matter Test", filters={"unit": ("in", list(by_unit) or [""])}, fields=["unit", "avg_pct", "test_date"],
			order_by="test_date asc, creation asc", limit_page_length=0):
		latest_pct[r.unit] = r.avg_pct
	rows = []
	for unit, cy in by_unit.items():
		if unit not in areas:
			continue
		rule = rules_for(cy.variety, crop)
		if not rule["testing"]:
			continue
		stage = stage_of_cycle(cy.name, on)
		ok = reached(cy.variety, stage, rule["from_stage"])
		seen = last.get(unit)
		since = (on - seen[0]).days if seen else None
		if not ok:
			state = "not_yet"
		elif seen is None or since >= days:
			state = "due"
		else:
			state = "recent"
		rows.append({
			"unit": unit, "cycle": cy.name, "variety": cy.variety, "stage": stage, "from_stage": rule["from_stage"],
			"on": rule["on"], "target_pct": rule["target"], "state": state,
			"last_test": str(seen[0]) if seen else None, "days_since": since,
			"last_pct": latest_pct.get(unit), "next_due": str(add_days(seen[0], days)) if seen else None,
		})
	order = {"due": 0, "recent": 1, "not_yet": 2}
	rows.sort(key=lambda r: (order[r["state"]], -(r["days_since"] if r["days_since"] is not None else 10**6), r["unit"]))
	return {"rows": rows, "retest_days": days,
		"counts": {k: sum(1 for r in rows if r["state"] == k) for k in order}}


def block_status(code, variety_text, last_test, on_date=None) -> dict:
	"""Sampling state of one avocado block (the avocado pages key blocks by their block code and keep the
	variety as text, possibly "Fuerte, Hass"): {stage, from_stage, state, days_since, testing}. `last_test` is the date
	of the block's latest maturity test or None."""
	on = getdate(on_date or today())
	out = {"stage": None, "from_stage": None, "state": None, "days_since": None, "testing": False, "variety": None}
	unit = frappe.db.get_value("Production Unit", {"avocado_block_code": code, "status": ("!=", "Retired")})
	cycle = frappe.db.get_value("Production Crop Cycle", {"unit": unit, "status": ("in", ["Active", "Harvesting"])},
		["name", "variety", "crop"], as_dict=True, order_by="start_date desc") if unit else None
	names = [v.strip() for v in (variety_text or "").split(",") if v.strip()]
	variety = (cycle.variety if cycle and cycle.variety else None) or next(
		(n for n in names if frappe.db.exists("Production Variety", n)), None)
	crop = (cycle.crop if cycle else None) or (frappe.db.get_value("Production Variety", variety, "crop") if variety else None)
	if not crop:
		return out
	rule = rules_for(variety, crop)
	out.update(variety=variety, from_stage=rule["from_stage"], testing=bool(rule["testing"]))
	out["stage"] = stage_of_cycle(cycle.name, on) if cycle else None
	if not rule["testing"]:
		return out
	since = (on - getdate(last_test)).days if last_test else None
	out["days_since"] = since
	if not cycle:
		out["state"] = "no_cycle"
	elif not reached(variety, out["stage"], rule["from_stage"]):
		out["state"] = "not_yet"
	elif since is None or since >= retest_days():
		out["state"] = "due"
	else:
		out["state"] = "recent"
	return out
