"""Flowering cycle chain: actual dates on the stage timeline, next-cycle proposal, manager flags.

Stages (`stages.py`) stay the single timeline. `actual_flowering_date` / `actual_harvest_start` are written
as stage actuals; the expected dates are the planned starts with those two actuals left out, so a late
flowering shows as a flag while still shifting every later stage.
"""

import frappe
from frappe.utils import add_days, cint, getdate, today

from upande_production.production.logic import stages

CYCLE_DT = "Production Crop Cycle"
FLAG_STATUSES = ("Active", "Harvesting")


def _variety(doc):
	return frappe.db.get_value("Production Variety", doc.get("variety"), [
		"is_flowering", "harvest_pattern", "lifespan_years", "weeks_flowering_to_harvest",
		"weeks_to_reflower_after_harvest", "harvest_window_days"], as_dict=True) if doc.get("variety") else None


def _stage_names(doc):
	"""(flowering stage name, harvest stage name) of the cycle's variety."""
	rows = stages.stages_for(doc.get("variety"))
	flower = next((r["stage"] for r in rows if (r["stage"] or "").lower().startswith("flower")), None)
	harvest = next((r["stage"] for r in rows if r["is_harvest"]), None)
	return flower, harvest


def _planned(doc, skip):
	"""Timeline of the cycle with the actuals of the `skip` stages ignored."""
	rows = [frappe._dict(stage=r.stage, actual_date=r.actual_date) for r in doc.get("stage_actuals") or []
		if r.stage not in skip]
	probe = frappe._dict(start_date=doc.get("start_date"), variety=doc.get("variety"), stage_actuals=rows)
	return stages.timeline(probe)


def _upsert(doc, stage, value):
	row = next((r for r in doc.get("stage_actuals") or [] if r.stage == stage), None)
	if value:
		if row:
			row.actual_date = value
		else:
			doc.append("stage_actuals", {"stage": stage, "actual_date": value})
	elif row:
		doc.remove(row)


def sync_actuals(doc) -> None:
	"""Actual flowering / harvest start dates <-> stage actuals; sets expected_flowering_date."""
	if not doc.get("variety") or not doc.get("start_date"):
		return
	flower, harvest = _stage_names(doc)
	have = {r.stage: r.actual_date for r in doc.get("stage_actuals") or [] if r.get("actual_date")}
	for field, stage in (("actual_flowering_date", flower), ("actual_harvest_start", harvest)):
		if not stage:
			continue
		if doc.get(field):
			_upsert(doc, stage, doc.get(field))
		elif stage in have and not doc.is_new():
			if doc.has_value_changed(field):  # cleared on purpose
				_upsert(doc, stage, None)
			else:
				doc.set(field, have[stage])
		elif stage in have:
			doc.set(field, have[stage])
	v = _variety(doc)
	if flower:
		if cint(doc.get("cycle_no")) > 1 and v and cint(v.weeks_to_reflower_after_harvest):
			doc.expected_flowering_date = add_days(doc.start_date, cint(v.weeks_to_reflower_after_harvest) * 7)
		else:
			tl = _planned(doc, {flower})
			st = next((s["start"] for s in tl if s["stage"] == flower), None)
			if st:
				doc.expected_flowering_date = st


def _expected_harvest(doc):
	v = _variety(doc)
	_, harvest = _stage_names(doc)
	if cint(doc.get("cycle_no")) > 1 and v and cint(v.weeks_flowering_to_harvest):
		f = doc.get("actual_flowering_date") or doc.get("expected_flowering_date")
		if f:
			return add_days(getdate(f), cint(v.weeks_flowering_to_harvest) * 7)
	if harvest:
		st = next((s["start"] for s in _planned(doc, {harvest}) if s["stage"] == harvest), None)
		if st:
			return st
	return getdate(doc.expected_harvest_start) if doc.get("expected_harvest_start") else None


def _root_start(doc):
	seen, d = set(), doc
	while d.get("previous_cycle") and d.get("previous_cycle") not in seen:
		seen.add(d.get("previous_cycle"))
		prev = frappe.db.get_value(CYCLE_DT, d.get("previous_cycle"), ["start_date", "previous_cycle"], as_dict=True)
		if not prev:
			break
		d = prev
	return getdate(d.get("start_date")) if d.get("start_date") else None


def propose_next(doc) -> str | None:
	"""A Closed cycle of a repeat-harvest variety proposes its successor once; lifespan reached marks
	it due for uprooting instead."""
	if doc.get("status") != "Closed" or doc.get("proposed_next_cycle") or not doc.get("variety"):
		return None
	v = _variety(doc)
	if not v or (v.harvest_pattern or "Once") == "Once":
		return None
	existing = frappe.db.get_value(CYCLE_DT, {"previous_cycle": doc.name}, "name")
	if existing:
		doc.proposed_next_cycle = existing
		frappe.db.set_value(CYCLE_DT, doc.name, "proposed_next_cycle", existing, update_modified=False)
		return None
	nxt = getdate(doc.get("actual_harvest_end") or today())
	first = _root_start(doc)
	if v.lifespan_years and first and add_days(first, int(v.lifespan_years * 365)) <= nxt:
		doc.due_for_uprooting = 1
		frappe.db.set_value(CYCLE_DT, doc.name, "due_for_uprooting", 1, update_modified=False)
		return None
	vals = {"doctype": CYCLE_DT, "unit": doc.unit, "crop": doc.crop, "variety": doc.variety, "item": doc.item,
		"cycle_type": doc.cycle_type, "area_ha": doc.area_ha, "plant_count": doc.plant_count, "status": "Planned",
		"previous_cycle": doc.name, "cycle_no": cint(doc.get("cycle_no") or 1) + 1, "start_date": nxt,
		"protocol": stages.variety_protocol(doc.variety)}
	if cint(v.is_flowering):
		ef = add_days(nxt, cint(v.weeks_to_reflower_after_harvest) * 7)
		vals["expected_flowering_date"] = ef
		vals["expected_harvest_start"] = add_days(ef, cint(v.weeks_flowering_to_harvest) * 7)
		if cint(v.harvest_window_days):
			vals["expected_harvest_end"] = add_days(vals["expected_harvest_start"], cint(v.harvest_window_days))
	new = frappe.get_doc(vals)
	new.insert(ignore_permissions=True)
	doc.proposed_next_cycle = new.name
	frappe.db.set_value(CYCLE_DT, doc.name, "proposed_next_cycle", new.name, update_modified=False)
	return new.name


def _tolerance_weeks() -> int:
	v = frappe.db.get_single_value("Production Settings", "cycle_flag_tolerance_weeks")
	return cint(v) if cint(v) > 0 else 2


def _compare(label, unit, expected, actual, tol, now, verb_late, due_text):
	if not expected:
		return None
	expected = getdate(expected)
	if actual:
		days = (getdate(actual) - expected).days
		if abs(days) > tol * 7:
			w = round(abs(days) / 7)
			return f"{unit} {verb_late} {w} week{'s' if w != 1 else ''} {'late' if days > 0 else 'early'}"
		return None
	days = (now - expected).days
	if days > tol * 7:
		w = days // 7
		return f"{unit} {due_text} {w} week{'s' if w != 1 else ''} ago, nothing recorded"
	return None


def flags(doc, today_=None) -> list[str]:
	"""Manager flags for one Active / Harvesting cycle. Never raises."""
	try:
		if doc.get("status") not in FLAG_STATUSES or not doc.get("variety"):
			return []
		now, tol, unit = getdate(today_ or today()), _tolerance_weeks(), doc.get("unit")
		flower, harvest = _stage_names(doc)
		out = []
		if flower:
			out.append(_compare("flowering", unit, doc.get("expected_flowering_date"), doc.get("actual_flowering_date"),
				tol, now, "flowered", "flowering due"))
		if harvest:
			out.append(_compare("harvest", unit, _expected_harvest(doc), doc.get("actual_harvest_start"), tol, now,
				"harvest started", "harvest due"))
		if doc.get("actual_harvest_end") and doc.get("expected_harvest_end"):
			out.append(_compare("end", unit, doc.expected_harvest_end, doc.actual_harvest_end, tol, now,
				"harvest ended", ""))
		return [f for f in out if f]
	except Exception:
		frappe.log_error(title="cycle_chain.flags")
		return []


def set_flags(doc) -> list[str]:
	fl = flags(doc)
	doc.protocol_flags = "\n".join(fl)
	doc.flag_count = len(fl)
	return fl


def refresh_flags(cycle) -> int:
	try:
		doc = frappe.get_doc(CYCLE_DT, cycle) if isinstance(cycle, str) else cycle
		fl = flags(doc)
		frappe.db.set_value(CYCLE_DT, doc.name, {"protocol_flags": "\n".join(fl), "flag_count": len(fl)},
			update_modified=False)
		return len(fl)
	except Exception:
		frappe.log_error(title="cycle_chain.refresh_flags")
		return 0


def refresh_flags_all() -> int:
	"""Scheduler (daily): recompute flags of every open cycle; returns cycles flagged."""
	n = 0
	for name in frappe.get_all(CYCLE_DT, filters={"status": ("in", FLAG_STATUSES)}, pluck="name"):
		if refresh_flags(name):
			n += 1
	return n


def flag_rows(crop) -> list[dict]:
	rows = frappe.get_all(CYCLE_DT, filters={"crop": crop, "status": ("in", FLAG_STATUSES), "flag_count": (">", 0)},
		fields=["name", "unit", "variety", "protocol_flags"], order_by="start_date desc")
	return [{"cycle": r.name, "unit": r.unit, "variety": r.variety,
		"flags": [f for f in (r.protocol_flags or "").split("\n") if f]} for r in rows]
