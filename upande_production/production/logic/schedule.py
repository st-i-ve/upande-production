"""Scheduling engine: what a protocol plans for a cycle between two dates.

Week N of a cycle covers days [(N-1)*7, N*7) from the cycle start. Key activities fall in one week;
cultural Interval activities repeat every `interval_weeks` after their establishment period and are
left out when they would fall inside the pre-harvest interval (PHI, days before the next harvest).
As needed and capital rows are never scheduled. Pure over plain objects (dicts or documents).
"""

from frappe.utils import add_days, cint, getdate


def _g(obj, key, default=None):
	v = obj.get(key) if hasattr(obj, "get") else getattr(obj, key, default)
	return default if v is None else v


def cycle_start(cycle_doc):
	return getdate(_g(cycle_doc, "start_date"))


def week_start(start, week):
	return getdate(add_days(getdate(start), (cint(week) - 1) * 7))


def next_pick(on, harvest_start, picks=(), harvest_interval_weeks=None):
	"""The first expected pick on or after `on`; None without a harvest start (or when a single harvest is past)."""
	if not harvest_start:
		return None
	on, hs = getdate(on), getdate(harvest_start)
	if on <= hs:
		return hs
	step = cint(harvest_interval_weeks) * 7
	past = [getdate(p) for p in picks or [] if getdate(p) <= on]
	last = max(past) if past else hs
	if last == on:
		return on
	if step < 1:
		return None
	days = (on - last).days
	k = -(-days // step)  # ceil
	return getdate(add_days(last, k * step))


def due_items(cycle_doc, protocol_doc, frm, to, harvest_start=None, picks=(), harvest_interval_weeks=None):
	"""Every planned occurrence in [frm, to], sorted by date."""
	frm, to = getdate(frm), getdate(to)
	start = cycle_start(cycle_doc)
	cycle = _g(cycle_doc, "name")
	cycle_no = cint(_g(cycle_doc, "cycle_no", 1)) or 1
	out = []
	for row in protocol_doc.get("key_activities") or []:
		if _g(row, "repeats") == "First cycle only" and cycle_no > 1:
			continue
		due = week_start(start, cint(_g(row, "week")))
		if frm <= due <= to:
			out.append({"ref": f"{cycle}:{_g(row, 'name')}:k", "kind": "key", "operation": _g(row, "operation"),
				"due_date": due, "planned_qty": _g(row, "planned_qty", None), "note": _g(row, "description", None),
				"row": _g(row, "name")})
	for row in protocol_doc.get("cultural_activities") or []:
		interval = cint(_g(row, "interval_weeks"))
		if _g(row, "schedule") != "Interval" or interval < 1:
			continue
		first = week_start(start, cint(_g(row, "establishment_period_weeks")) + 1)
		phi = cint(_g(row, "pre_harvest_interval_days"))
		k = 0
		while True:
			due = getdate(add_days(first, k * interval * 7))
			if due > to:
				break
			if due >= frm:
				inside = False
				if phi > 0:
					nh = next_pick(due, harvest_start, picks, harvest_interval_weeks)
					inside = nh is not None and 0 <= (nh - due).days < phi
				if not inside:
					out.append({"ref": f"{cycle}:{_g(row, 'name')}:{k}", "kind": "cultural",
						"operation": _g(row, "operation"), "due_date": due, "planned_qty": _g(row, "planned_qty", None),
						"note": _g(row, "description", None), "row": _g(row, "name")})
			k += 1
	out.sort(key=lambda r: (r["due_date"], r["ref"]))
	return out


def rows_for_check(protocol_doc, operation):
	"""Cultural rows of an operation (for the buffer rules)."""
	return [r for r in protocol_doc.get("cultural_activities") or [] if _g(r, "operation") == operation]


def harvest_context(cycle) -> dict:
	"""{"harvest_start", "picks", "harvest_interval_weeks"} of a cycle from the database: the expected harvest
	start (stages.harvest_start), the distinct dates of its Production Harvests and its variety's interval."""
	import frappe

	from upande_production.production.logic import stages

	name = cycle if isinstance(cycle, str) else cycle.get("name")
	try:
		hs = stages.harvest_start(name)
	except Exception:
		hs = None
	picks = sorted({getdate(d) for d in frappe.get_all("Production Harvest", filters={"cycle": name},
		pluck="harvest_date") if d})
	variety = frappe.db.get_value("Production Crop Cycle", name, "variety")
	interval = None
	if variety:
		interval = cint(frappe.db.get_value("Production Variety", variety, "harvest_interval_weeks")) or None
	return {"harvest_start": hs, "picks": picks, "harvest_interval_weeks": interval}


def due_for_cycle(cycle_doc, protocol_doc, frm, to) -> list:
	"""due_items with the cycle's harvest context filled in from the database."""
	return due_items(cycle_doc, protocol_doc, frm, to, **harvest_context(cycle_doc))
