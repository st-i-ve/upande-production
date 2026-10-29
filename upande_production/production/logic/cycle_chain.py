"""Flowering cycle chain: actual dates on the stage timeline, next-cycle proposal, manager flags.

Stages (`stages.py`) stay the single timeline. `actual_flowering_date` / `actual_harvest_start` are written
as stage actuals; the expected dates are the planned starts with those two actuals left out, so a late
flowering shows as a flag while still shifting every later stage.
"""

import calendar

import frappe
from frappe.utils import add_days, cint, getdate, today

from upande_production.production.logic import stages
from upande_production.production.logic.units import unit_filter

CYCLE_DT = "Production Crop Cycle"
FLAG_STATUSES = ("Active", "Harvesting")
MONTHS = [m for m in calendar.month_name if m]


def _variety(doc):
	v = frappe.db.get_value("Production Variety", doc.get("variety"), [
		"is_flowering", "harvest_pattern", "lifespan_years", "weeks_flowering_to_harvest",
		"weeks_to_reflower_after_harvest", "harvest_window_days", "stage_anchor", "weeks_to_maturity",
		"flowering_pattern", "flowering_interval_weeks"], as_dict=True) if doc.get("variety") else None
	if v:
		v.seasons = _seasons(doc.get("variety")) if v.flowering_pattern == "Seasonal" else []
	return v


def _seasons(variety) -> list:
	return frappe.get_all("Production Variety Flowering Season", filters={"parent": variety, "parenttype": "Production Variety"},
		fields=["season_name", "start_month", "weeks_flowering_to_harvest", "crop_share_pct"], order_by="idx asc")


def _month_no(row) -> int:
	return MONTHS.index(row["start_month"]) + 1


def _is_seasonal(v) -> bool:
	return bool(v and cint(v.is_flowering) and v.flowering_pattern == "Seasonal" and v.seasons)


def next_season(variety, after) -> tuple:
	"""(season row, flowering date) of the first season start strictly after `after` (a season starts on
	the 1st of its start month). `variety` is a name or the dict from `_variety`."""
	seasons = variety.seasons if hasattr(variety, "seasons") else _seasons(variety)
	after = getdate(after)
	best = None
	for r in seasons:
		for year in (after.year, after.year + 1):
			d = getdate(f"{year}-{_month_no(r):02d}-01")
			if d > after and (best is None or d < best[1]):
				best = (r, d)
				break
	return best


def _season_on_or_after(variety, on) -> tuple:
	"""Like next_season, but a season starting on `on` itself counts."""
	return next_season(variety, add_days(getdate(on), -1))


def first_season_date(planted_on, variety):
	"""First season start on or after planting + weeks to maturity."""
	hit = first_season(planted_on, variety)
	return hit[1] if hit else None


def first_season(planted_on, variety) -> tuple:
	v = variety if hasattr(variety, "seasons") else _variety(frappe._dict(variety=variety))
	if not v or not v.seasons:
		return None
	return _season_on_or_after(v, add_days(getdate(planted_on), cint(v.weeks_to_maturity) * 7))


def _season_row(v, name=None, near=None):
	"""The season row by name, else the one starting closest (by month) to the date `near`."""
	if name:
		row = next((r for r in v.seasons if r["season_name"] == name), None)
		if row:
			return row
	if near and v.seasons:
		near = getdate(near)
		return min(v.seasons, key=lambda r: min((_month_no(r) - near.month) % 12, (near.month - _month_no(r)) % 12))
	return None


def _weeks_f2h(doc, v) -> int:
	"""Weeks from flowering to harvest for the cycle: its season's, else the variety's."""
	if _is_seasonal(v):
		row = _season_row(v, doc.get("flowering_season"), doc.get("actual_flowering_date") or doc.get("expected_flowering_date"))
		if row:
			return cint(row["weeks_flowering_to_harvest"])
	return cint(v.weeks_flowering_to_harvest) if v else 0


def planted_on(doc):
	"""Planting date of the cycle's block: the opening balance's planted_on, else the first cycle's start."""
	unit = doc.get("unit")
	if unit:
		d = frappe.db.get_value("Block Opening Balance", {"unit": unit}, "planted_on")
		if d:
			return getdate(d)
	return _root_start(doc)


def is_juvenile(doc) -> bool:
	"""Expected harvest start is before the block's planting date plus the variety's weeks to maturity."""
	v = _variety(doc)
	if not v or not cint(v.weeks_to_maturity) or not doc.get("expected_harvest_start") or doc.get("actual_harvest_start"):
		return False  # a cycle that is already being picked is not waiting for maturity
	planted = planted_on(doc)
	if not planted:
		return False
	return getdate(doc.expected_harvest_start) < add_days(planted, cint(v.weeks_to_maturity) * 7)


def expected_flowering(doc, v=None):
	"""Expected flowering date of the cycle under its variety's pattern, or None when the pattern gives
	no answer (the stage timeline then decides). Seasonal: the cycle's season start (kept once set);
	a first cycle takes the first season after maturity, a later one the next season after the previous
	flowering. Interval: previous flowering + the interval."""
	v = v or _variety(doc)
	if not v or not cint(v.is_flowering):
		return None
	if _is_seasonal(v):
		if doc.get("flowering_season") and doc.get("expected_flowering_date"):
			return getdate(doc.expected_flowering_date)
		prev = doc.get("previous_cycle")
		if prev:
			p = frappe.db.get_value(CYCLE_DT, prev, ["actual_flowering_date", "expected_flowering_date"], as_dict=True)
			ref = p and (p.actual_flowering_date or p.expected_flowering_date)
			hit = next_season(v, ref) if ref else None
			if hit and doc.get("start_date") and hit[1] < getdate(doc.start_date):
				hit = _season_on_or_after(v, doc.start_date)
			return hit[1] if hit else None
		if not callable(getattr(doc, "is_new", None)) or doc.is_new():
			planted = planted_on(doc) or (getdate(doc.start_date) if doc.get("start_date") else None)
			hit = first_season(planted, v) if planted else None
			if doc.get("start_date"):  # an established block: never a season already past at the cycle's start
				on_start = _season_on_or_after(v, doc.start_date)
				if on_start and (not hit or on_start[1] > hit[1]):
					hit = on_start
			return hit[1] if hit else None
		return None
	if v.flowering_pattern == "Interval" and cint(v.flowering_interval_weeks) and doc.get("previous_cycle"):
		p = frappe.db.get_value(CYCLE_DT, doc.get("previous_cycle"), ["actual_flowering_date", "expected_flowering_date"], as_dict=True)
		ref = p and (p.actual_flowering_date or p.expected_flowering_date)
		if ref:
			d = add_days(getdate(ref), cint(v.flowering_interval_weeks) * 7)
			if doc.get("start_date"):
				while d < getdate(doc.start_date):
					d = add_days(d, cint(v.flowering_interval_weeks) * 7)
			return d
	return None


def _season_on_or_before(v, on) -> tuple:
	"""(season row, date) of the latest season start on or before `on`."""
	on = getdate(on)
	best = None
	for r in v.seasons:
		for year in (on.year, on.year - 1):
			d = getdate(f"{year}-{_month_no(r):02d}-01")
			if d <= on:
				if best is None or d > best[1]:
					best = (r, d)
				break
	return best


def backfill_season(doc, v) -> bool:
	"""An open, already-saved cycle of a Seasonal variety without a season takes the season whose start
	is nearest on or before its actual / expected flowering date (else its start date); its expected
	flowering follows. True when a season was assigned."""
	if doc.is_new() or doc.get("flowering_season") or doc.get("status") in ("Closed", "Cancelled") or not _is_seasonal(v):
		return False
	ref = doc.get("actual_flowering_date") or doc.get("expected_flowering_date") or doc.get("start_date")
	hit = _season_on_or_before(v, ref) if ref else None
	if not hit:
		return False
	doc.flowering_season = hit[0]["season_name"]
	doc.expected_flowering_date = hit[1]
	doc.flags.season_backfilled = True
	return True


def cycle_number(doc) -> int:
	"""1 without a previous cycle or for a Once variety; otherwise the previous cycle's number + 1."""
	if not doc.get("previous_cycle"):
		return 1
	v = _variety(doc)
	if not v or (v.harvest_pattern or "Once") == "Once":
		return 1
	prev = frappe.db.get_value(CYCLE_DT, doc.get("previous_cycle"), "cycle_no")
	return cint(prev or 1) + 1


def first_pick_date(doc):
	if not doc.get("name") or doc.is_new():
		return None
	return frappe.db.get_all("Production Harvest", filters={"cycle": doc.name, "docstatus": ("<", 2)},
		fields=[{"MIN": "harvest_date", "as": "d"}])[0].d


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
	if harvest and not doc.get("actual_harvest_start"):
		first = first_pick_date(doc)
		if first:
			doc.actual_harvest_start = first
			_upsert(doc, harvest, first)
	v = _variety(doc)
	patterned = False
	if flower:
		backfill_season(doc, v)
		ef = expected_flowering(doc, v)
		if ef:
			doc.expected_flowering_date = ef
			patterned = True
			if _is_seasonal(v) and not doc.get("flowering_season"):
				doc.flowering_season = _season_row(v, near=ef)["season_name"]
		elif cint(doc.get("cycle_no")) > 1 and v and cint(v.weeks_to_reflower_after_harvest):
			doc.expected_flowering_date = add_days(doc.start_date, cint(v.weeks_to_reflower_after_harvest) * 7)
		else:
			tl = _planned(doc, {flower})
			st = next((s["start"] for s in tl if s["stage"] == flower), None)
			if st:
				doc.expected_flowering_date = st
	_sync_expected_harvest(doc, v, patterned)
	doc.juvenile = 1 if is_juvenile(doc) else 0


def _sync_expected_harvest(doc, v, patterned=False):
	"""Expected harvest follows the flowering date (actual wins) for flowering varieties: a hand-made
	later cycle gets it filled in; a newly recorded actual flowering moves it unless the user set
	expected_harvest_start in the same save."""
	weeks = _weeks_f2h(doc, v) if v else 0
	if not v or not cint(v.is_flowering) or not weeks:
		return
	if doc.is_new():
		go = not doc.get("expected_harvest_start") and (cint(doc.get("cycle_no")) > 1 or doc.get("actual_flowering_date")
			or (patterned and doc.get("flowering_season")))
	else:
		go = doc.flags.get("season_backfilled") or (doc.get("actual_flowering_date")
			and doc.has_value_changed("actual_flowering_date") and not doc.has_value_changed("expected_harvest_start"))
	f = doc.get("actual_flowering_date") or doc.get("expected_flowering_date")
	if not go or not f:
		return
	doc.expected_harvest_start = add_days(getdate(f), weeks * 7)
	if cint(v.harvest_window_days):
		doc.expected_harvest_end = add_days(doc.expected_harvest_start, cint(v.harvest_window_days))


def _expected_harvest(doc):
	v = _variety(doc)
	_, harvest = _stage_names(doc)
	weeks = _weeks_f2h(doc, v) if v else 0
	if (cint(doc.get("cycle_no")) > 1 or (_is_seasonal(v) and doc.get("flowering_season"))) and weeks:
		f = doc.get("actual_flowering_date") or doc.get("expected_flowering_date")
		if f:
			return add_days(getdate(f), weeks * 7)
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


def _next_flowering(doc, v) -> tuple:
	"""(flowering date, season row) of the successor cycle, or (None, None) when the variety's pattern
	gives none. Seasonal: the very next season by calendar after this cycle's season start (never
	skipped, whatever the harvest does); Interval: this cycle's flowering + the interval."""
	if not cint(v.is_flowering):
		return None, None
	if _is_seasonal(v):
		ref = doc.get("expected_flowering_date") if doc.get("flowering_season") else None
		ref = ref or doc.get("actual_flowering_date") or doc.get("expected_flowering_date")
		hit = next_season(v, ref) if ref else None
		return (hit[1], hit[0]) if hit else (None, None)
	if v.flowering_pattern == "Interval" and cint(v.flowering_interval_weeks):
		ref = doc.get("actual_flowering_date") or doc.get("expected_flowering_date")
		if ref:
			return add_days(getdate(ref), cint(v.flowering_interval_weeks) * 7), None
	return None, None


def propose_next(doc) -> str | None:
	"""A cycle of a repeat-harvest variety proposes its successor once, when it flowers or closes (first
	wins); lifespan reached marks a closed cycle due for uprooting instead."""
	if (doc.get("status") not in ("Active", "Harvesting", "Closed") or doc.get("proposed_next_cycle")
			or not doc.get("variety")):
		return None
	if doc.get("status") != "Closed" and not doc.get("actual_flowering_date"):
		return None
	v = _variety(doc)
	if not v or (v.harvest_pattern or "Once") == "Once":
		return None
	existing = frappe.db.get_value(CYCLE_DT, {"previous_cycle": doc.name}, "name")
	if existing:
		doc.proposed_next_cycle = existing
		frappe.db.set_value(CYCLE_DT, doc.name, "proposed_next_cycle", existing, update_modified=False)
		return None
	flowering, season = _next_flowering(doc, v)
	nxt = flowering or getdate(doc.get("actual_harvest_end") or today())
	first = _root_start(doc)
	if v.lifespan_years and first and add_days(first, int(v.lifespan_years * 365)) <= nxt:
		if doc.get("status") == "Closed":
			doc.due_for_uprooting = 1
			frappe.db.set_value(CYCLE_DT, doc.name, "due_for_uprooting", 1, update_modified=False)
		return None
	if flowering and frappe.db.exists(CYCLE_DT, {"unit": doc.unit, "variety": doc.variety, "name": ("!=", doc.name),
			"expected_flowering_date": flowering, "status": ("!=", "Cancelled")}):
		return None  # that flowering already has a cycle
	vals = {"doctype": CYCLE_DT, "unit": doc.unit, "crop": doc.crop, "variety": doc.variety, "item": doc.item,
		"cycle_type": doc.cycle_type, "area_ha": doc.area_ha, "plant_count": doc.plant_count, "status": "Planned",
		"previous_cycle": doc.name, "cycle_no": cint(doc.get("cycle_no") or 1) + 1, "start_date": nxt,
		"protocol": stages.variety_protocol(doc.variety)}
	if cint(v.is_flowering):
		ef, weeks = flowering, cint(v.weeks_flowering_to_harvest)
		if season:
			vals["flowering_season"] = season["season_name"]
			weeks = cint(season["weeks_flowering_to_harvest"])
		elif not ef:
			ef = add_days(nxt, cint(v.weeks_to_reflower_after_harvest) * 7)
		vals["expected_flowering_date"] = ef
		vals["expected_harvest_start"] = add_days(ef, weeks * 7)
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
		v = _variety(doc)
		anchored = v and v.stage_anchor == "Flowering" and cint(doc.get("cycle_no") or 1) <= 1 and not _is_seasonal(v)
		if flower and not anchored:  # a flowering-anchored first cycle starts at flowering (not so for seasons)
			out.append(_compare("flowering", unit, doc.get("expected_flowering_date"), doc.get("actual_flowering_date"),
				tol, now, "flowered", "flowering due"))
		if harvest:
			# a juvenile block cannot be picked yet: no "harvest due ... nothing recorded" for it
			juvenile = not doc.get("actual_harvest_start") and (cint(doc.get("juvenile")) or is_juvenile(doc))
			if not juvenile:
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
	rows = frappe.get_all(CYCLE_DT, filters=unit_filter({"crop": crop, "status": ("in", FLAG_STATUSES), "flag_count": (">", 0)}),
		fields=["name", "unit", "variety", "protocol_flags"], order_by="start_date desc")
	return [{"cycle": r.name, "unit": r.unit, "variety": r.variety,
		"flags": [f for f in (r.protocol_flags or "").split("\n") if f]} for r in rows]
