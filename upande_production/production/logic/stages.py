"""Growth stages of a variety / strain, laid over a cycle (or a pond stocking) on the calendar.

A Production Variety lists stages as (start_day, length_days) from an anchor (`stage_anchor`:
Planting / Flowering / Stocking). For a Production Crop Cycle the anchor is `start_date`; for a Pond
Stocking it is `stocking_date` and the variety is the stocking's `strain`.

Stage actuals (Production Cycle Stage Actual rows on the cycle) record the date a stage really began:
that stage, and every later stage, moves by the same delta. An actual on the first stage (day 0)
re-anchors the whole timeline (e.g. the avocado flowering date, which precedes the cycle record).

Dates: a stage covers `start` <= d < `end`, where `end` (exclusive) is the day the next stage would
begin; `last_day` is the inclusive last day.
"""

import frappe
from frappe.utils import add_days, cint, getdate, today

from upande_production.production.logic.units import unit_filter

CYCLE_DT = "Production Crop Cycle"
STOCKING_DT = "Pond Stocking"
OPEN_CYCLE_STATUSES = ("Planned", "Active", "Harvesting")


def _doc(obj, doctype=CYCLE_DT):
	"""A document for a name, dict or document. A dict row that carries a name is loaded (and kept)."""
	if isinstance(obj, str):
		return frappe.get_doc(doctype, obj)
	if getattr(obj, "doctype", None):
		return obj
	cached = obj.get("_doc") if hasattr(obj, "get") else None
	if cached is not None:
		return cached
	name = obj.get("name")
	doc = frappe.get_doc(doctype, name) if name else frappe._dict(obj)
	try:
		obj["_doc"] = doc
	except TypeError:
		pass
	return doc


def _is_stocking(doc) -> bool:
	return getattr(doc, "doctype", None) == STOCKING_DT or bool(doc.get("stocking_date") and not doc.get("start_date"))


def variety_of(doc):
	return doc.get("strain") if _is_stocking(doc) else doc.get("variety")


def stages_for(variety) -> list[dict]:
	"""[{stage, start_day, length_days, end_day, is_harvest, description}] of a variety, in idx order."""
	if not variety:
		return []
	rows = frappe.get_all(
		"Production Variety Stage", filters={"parent": variety, "parenttype": "Production Variety"},
		fields=["stage", "start_day", "length_days", "is_harvest", "description"], order_by="idx asc",
	)
	for r in rows:
		r["start_day"] = cint(r.start_day)
		r["length_days"] = cint(r.length_days)
		r["end_day"] = r["start_day"] + r["length_days"]
		r["is_harvest"] = cint(r.is_harvest)
	return rows


def _base_date(doc):
	d = doc.get("stocking_date") if _is_stocking(doc) else doc.get("start_date")
	return getdate(d) if d else None


def _day0(doc):
	"""Day 0 of the stages: the start date, except for a later cycle (cycle_no > 1) of a Flowering-anchored
	variety, where the start is the previous harvest end and day 0 is the expected flowering date."""
	base = _base_date(doc)
	if _is_stocking(doc) or not base or cint(doc.get("cycle_no")) <= 1 or not doc.get("expected_flowering_date"):
		return base
	if frappe.db.get_value("Production Variety", doc.get("variety"), "stage_anchor") == "Flowering":
		return getdate(doc.get("expected_flowering_date"))
	return base


def _actuals(doc) -> dict:
	out = {}
	for r in doc.get("stage_actuals") or []:
		if r.get("stage") and r.get("actual_date"):
			out[r.stage] = getdate(r.actual_date)
	return out


def timeline(cycle) -> list[dict]:
	"""Every stage of the cycle's variety with real dates: [{stage, start, end, last_day, is_harvest,
	start_day, actual}] honouring stage actuals. Empty without a variety or a start date."""
	doc = _doc(cycle, STOCKING_DT if _is_stocking_obj(cycle) else CYCLE_DT)
	stages = stages_for(variety_of(doc))
	base = _day0(doc)
	if not stages or not base:
		return []
	actuals = _actuals(doc)
	first = stages[0]
	if first["start_day"] == 0 and first["stage"] in actuals:
		base = actuals[first["stage"]]  # re-anchored on the recorded first stage
	shift, out = 0, []
	for i, st in enumerate(stages):
		planned = add_days(base, st["start_day"] + shift)
		actual = actuals.get(st["stage"]) if i or first["stage"] not in actuals else None
		if actual is not None:
			shift += (actual - planned).days
			start = actual
		else:
			start = planned
		end = add_days(start, st["length_days"])
		out.append({"stage": st["stage"], "start": start, "end": end, "last_day": add_days(end, -1),
			"is_harvest": st["is_harvest"], "start_day": st["start_day"], "actual": actual is not None
			or (i == 0 and first["stage"] in actuals)})
	return out


def _is_stocking_obj(obj) -> bool:
	if getattr(obj, "doctype", None):
		return obj.doctype == STOCKING_DT
	if isinstance(obj, str):
		return obj.startswith("PST-")
	return _is_stocking(obj)


def anchor_date(cycle):
	"""The date day 0 of the variety's stages falls on: the cycle start (or stocking date), or the
	recorded date of the first stage when that is an actual (avocado flowering)."""
	doc = _doc(cycle, STOCKING_DT if _is_stocking_obj(cycle) else CYCLE_DT)
	base = _day0(doc)
	stages = stages_for(variety_of(doc))
	if stages and stages[0]["start_day"] == 0:
		a = _actuals(doc).get(stages[0]["stage"])
		if a:
			return a
	return base


def stage_on(cycle, on_date=None) -> dict:
	"""{stage, start, end, last_day, day, is_harvest} on a date. `day` counts from the anchor. Before the
	first stage `stage` is None; after the last stage's end the last stage is returned."""
	on = getdate(on_date or today())
	tl = timeline(cycle)
	anchor = anchor_date(cycle)
	day = (on - anchor).days if anchor else None
	if not tl:
		return {"stage": None, "start": None, "end": None, "last_day": None, "day": day, "is_harvest": 0}
	hit = next((s for s in tl if s["start"] <= on < s["end"]), None)
	if hit is None and on >= tl[-1]["end"]:
		hit = tl[-1]
	if hit is None and on < tl[0]["start"]:
		return {"stage": None, "start": None, "end": tl[0]["start"], "last_day": None, "day": day, "is_harvest": 0}
	if hit is None:  # a gap between stages: the stage that just ended
		hit = [s for s in tl if s["end"] <= on][-1]
	return {"stage": hit["stage"], "start": hit["start"], "end": hit["end"], "last_day": hit["last_day"],
		"day": day, "is_harvest": hit["is_harvest"]}


def stage_start(cycle, stage):
	"""The start date of a named stage of the cycle's variety, or None."""
	return next((s["start"] for s in timeline(cycle) if s["stage"] == stage), None)


def harvest_start(cycle):
	"""expected_harvest_start, else the start of the variety's harvest stage, else None."""
	doc = _doc(cycle, STOCKING_DT if _is_stocking_obj(cycle) else CYCLE_DT)
	explicit = doc.get("target_harvest_date") if _is_stocking(doc) else doc.get("expected_harvest_start")
	if explicit:
		return getdate(explicit)
	return next((s["start"] for s in timeline(doc) if s["is_harvest"]), None)


def step_due_date(cycle, step, k=0):
	"""Due date of repeat `k` of a protocol step: day_offset counts from the start of the step's
	anchor_stage (for the cycle's variety) when set and known, otherwise from the cycle start."""
	doc = _doc(cycle)
	base = None
	if step.get("anchor_stage"):
		base = stage_start(doc, step.get("anchor_stage"))
	if base is None:
		base = getdate(doc.get("start_date"))
	return add_days(base, cint(step.get("day_offset")) + cint(k) * cint(step.get("repeat_every_days")))


def current_stage_name(cycle, on_date=None):
	doc = _doc(cycle, STOCKING_DT if _is_stocking_obj(cycle) else CYCLE_DT)
	if doc.get("status") == "Closed" or doc.get("status") == "Harvested":
		return None
	return stage_on(doc, on_date)["stage"]


def refresh_current_stage(cycle) -> str | None:
	"""Recompute and store `current_stage` (cycles only; a stocking shows its stage on demand)."""
	doc = _doc(cycle) if not getattr(cycle, "doctype", None) else cycle
	name = current_stage_name(doc)
	if (doc.get("current_stage") or None) != name and doc.get("name"):
		frappe.db.set_value(doc.doctype, doc.name, "current_stage", name, update_modified=False)
		doc.current_stage = name
	return name


def refresh_all_open():
	"""Scheduler (daily): refresh current_stage of every open cycle."""
	n = 0
	for name in frappe.get_all(CYCLE_DT, filters=unit_filter({"status": ("in", OPEN_CYCLE_STATUSES), "variety": ("is", "set")}),
			pluck="name"):
		refresh_current_stage(frappe.get_doc(CYCLE_DT, name))
		n += 1
	# cycles that have closed: clear a stale stage
	frappe.db.sql(
		"update `tabProduction Crop Cycle` set current_stage = NULL where status = 'Closed' and current_stage is not null")
	return n


def stocking_stage(stocking, on_date=None) -> dict:
	"""stage_on for a Pond Stocking (anchor = stocking date, stages of its strain)."""
	return stage_on(frappe.get_doc(STOCKING_DT, stocking) if isinstance(stocking, str) else stocking, on_date)


# ------------------------------------------------------------------ cycle defaults

def active_protocol_of_family(protocol):
	"""The Active version of a protocol's family (the protocol itself when already Active)."""
	if not protocol:
		return None
	fam = frappe.db.get_value("Production Protocol", protocol, "protocol_family") or protocol
	return frappe.db.get_value("Production Protocol", {"protocol_family": fam, "version_status": "Active"}, "name",
		order_by="version desc")


def variety_protocol(variety):
	"""The protocol a new cycle of the variety should use: default_protocol family's Active version, else
	any Active protocol of the variety, else the Active product-level protocol (no variety)."""
	if not variety:
		return None
	v = frappe.db.get_value("Production Variety", variety, ["default_protocol", "crop", "product"], as_dict=True)
	if not v:
		return None
	name = active_protocol_of_family(v.default_protocol)
	if name:
		return name
	name = frappe.db.get_value("Production Protocol", {"variety": variety, "version_status": "Active"}, "name",
		order_by="version desc")
	if name:
		return name
	if v.product:
		return frappe.db.get_value("Production Protocol",
			{"crop": v.crop, "item": v.product, "version_status": "Active", "variety": ("in", ["", None])}, "name",
			order_by="version desc")
	return None


def apply_variety_defaults(cycle):
	"""Called from Production Crop Cycle.validate: item and protocol follow the variety, a protocol of
	another variety is refused, expected harvest dates default from the variety, current stage is set."""
	from frappe import _

	if cycle.protocol and not cycle.variety:
		pv = frappe.db.get_value("Production Protocol", cycle.protocol, "variety")
		if pv:
			cycle.variety = pv
	if cycle.variety:
		v = frappe.db.get_value("Production Variety", cycle.variety,
			["crop", "item", "days_to_first_harvest", "harvest_window_days"], as_dict=True)
		if not v:
			frappe.throw(_("Variety {0} not found").format(cycle.variety), frappe.ValidationError)
		if cycle.crop and v.crop != cycle.crop:
			frappe.throw(_("Variety {0} belongs to {1}, not {2}").format(cycle.variety, v.crop, cycle.crop),
				frappe.ValidationError)
		if v.item:
			cycle.item = v.item
		if not cycle.protocol:
			cycle.protocol = variety_protocol(cycle.variety)
		if cycle.protocol:
			pv = frappe.db.get_value("Production Protocol", cycle.protocol, "variety")
			if pv and pv != cycle.variety:
				frappe.throw(_("Protocol {0} belongs to variety {1}; this cycle is {2}").format(
					cycle.protocol, pv, cycle.variety), frappe.ValidationError)
		if cycle.start_date and cint(v.days_to_first_harvest) and not cycle.expected_harvest_start:
			cycle.expected_harvest_start = add_days(anchor_date(cycle) or cycle.start_date, cint(v.days_to_first_harvest))
			if cint(v.harvest_window_days) and not cycle.expected_harvest_end:
				cycle.expected_harvest_end = add_days(cycle.expected_harvest_start, cint(v.harvest_window_days))
	cycle.current_stage = current_stage_name(cycle)


def product_item(item):
	"""The product item a variety item belongs to ("Potatoes - Shangi" -> "Potatoes"); any other item is
	returned as it is (avocado variety items have no separate product)."""
	if not item:
		return item
	return frappe.db.get_value("Production Variety", {"item": item}, "product") or item
