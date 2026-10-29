"""Coverage map endpoint: what is left to do this week, block by block."""

import json

import frappe
from frappe.utils import flt, getdate, today

from upande_production.api.envelope import run
from upande_production.production.logic import analytics
from upande_production.production.logic.units import retired_sql
from upande_production.production.logic.weeks import iso_week_bounds

STATES = ("done", "partial", "not_started", "late", "pending_approval", "no_work")
CLOSED = ("Done", "Skipped")


def _has_pending_qty():
	return frappe.get_meta("Production Plan Task").has_field("pending_qty")


def _task_rows(crop, year, week, farm):
	extra = ", t.pending_qty" if _has_pending_qty() else ""
	farm_sql = "and p.farm = %(farm)s" if farm else ""
	return frappe.db.sql(
		f"""select t.unit, t.operation, t.operation_name, t.planned_qty, t.done_qty, t.uom, t.status,
		t.due_date{extra}
		from `tabProduction Plan Task` t join `tabProduction Work Plan` p on p.name = t.parent
		where p.crop = %(crop)s and p.plan_year = %(year)s and p.plan_week = %(week)s {farm_sql}
		order by t.idx""",
		{"crop": crop, "year": int(year), "week": int(week), "farm": farm},
		as_dict=True,
	)


def _work_rows(crop, start, end, farm):
	"""Value Adder Work (approved or pending) in the week, newest first."""
	return frappe.db.sql(
		"""select w.unit, w.operation, o.operation_name, o.color from `tabValue Adder Work` w
		join `tabProduction Operation` o on o.name = w.operation
		where w.crop = %(crop)s and w.docstatus < 2 and w.approval_status in ('Approved', 'Pending')
		and w.work_date between %(s)s and %(e)s and w.unit not in %(retired)s
		order by w.work_date desc, w.creation desc""",
		{"crop": crop, "s": start, "e": end, "retired": retired_sql()},
		as_dict=True,
	)


def unit_activity(work, tasks, colors):
	"""The activity a unit is going through: latest work this week, else the first In Progress task,
	else the first Open task. `work` newest first; `tasks` shaped tasks."""
	if work:
		return {"operation": work[0].operation_name or work[0].operation, "color": work[0].color}
	for status in ("In Progress", "Open"):
		for t in tasks:
			if t["status"] == status:
				return {"operation": t["operation_name"], "color": colors.get(t["operation"])}
	return None


def _shape_task(r, week_end, ref_day):
	planned = flt(r.planned_qty)
	done = flt(r.done_qty)
	pending = flt(r.get("pending_qty"))
	skipped = r.status == "Skipped"
	remaining = 0.0 if skipped else max(planned - done, 0.0)
	outstanding = max(remaining - pending, 0.0)
	due = getdate(r.due_date) if r.due_date else week_end
	return {
		"operation": r.operation,
		"operation_name": r.operation_name or r.operation,
		"planned_qty": planned,
		"done_qty": done,
		"pending_qty": pending if _has_pending_qty() else None,
		"remaining_qty": remaining,
		"uom": r.uom,
		"status": r.status,
		"due_date": str(due),
		"late": bool(not skipped and outstanding > 0 and due < ref_day),
	}


def unit_state(tasks):
	"""Map-colour state from shaped tasks (see _shape_task). Skipped tasks do not count."""
	live = [t for t in tasks if t["status"] != "Skipped"]
	if not live:
		return "no_work"
	if all(t["remaining_qty"] <= 0 for t in live):
		return "done"
	if any(t["late"] for t in live):
		return "late"
	if any((t["pending_qty"] or 0) > 0 for t in live):
		return "pending_approval"
	if any(t["done_qty"] > 0 or t["status"] in ("In Progress", "Partly Done") for t in live):
		return "partial"
	return "not_started"


def progress_pct(tasks):
	"""Mean of each task's completion (capped at 100%). Quantities in different UOMs are not summed."""
	live = [t for t in tasks if t["status"] != "Skipped" and t["planned_qty"] > 0]
	if not live:
		return 0.0
	return round(100.0 * sum(min(t["done_qty"] / t["planned_qty"], 1.0) for t in live) / len(live), 1)


def _coords(node):
	if isinstance(node, (list, tuple)):
		if node and isinstance(node[0], (int, float)):
			yield node
		else:
			for n in node:
				yield from _coords(n)


def _geo(raw):
	if not raw:
		return None
	try:
		return json.loads(raw)
	except Exception:
		return None


def _geometry(gj):
	if not gj:
		return None
	if gj.get("type") == "Feature":
		return gj.get("geometry")
	if gj.get("type") == "FeatureCollection" and gj.get("features"):
		return gj["features"][0].get("geometry")
	return gj


def _bounds(geos):
	pts = [p for g in geos for p in _coords((_geometry(g) or {}).get("coordinates"))]
	if not pts:
		return None, None
	lngs, lats = [p[0] for p in pts], [p[1] for p in pts]
	b = [[min(lngs), min(lats)], [max(lngs), max(lats)]]
	return [round((b[0][0] + b[1][0]) / 2, 6), round((b[0][1] + b[1][1]) / 2, 6)], b


def _add(d, uom, qty):
	d[uom] = round(d.get(uom, 0.0) + qty, 3)


@frappe.whitelist(methods=["POST"])
@run
def coverage_map(crop, year, week, farm=None, operation=None, status=None):
	"""Week coverage for a crop's units.

	Returns {week_start, week_end, units, outlines, totals, operations, center, bounds}.
	`operation` limits the tasks counted; `status` (one of STATES) keeps only units in that state.
	Units are the leaf units (blocks, slices, ponds); group units (pivots) come back as `outlines`.
	"""
	frappe.has_permission("Production Work Plan", "read", throw=True)
	frappe.has_permission("Production Unit", "read", throw=True)
	if status and status not in STATES:
		frappe.throw(f"Unknown status {status}", frappe.ValidationError)
	start, end = iso_week_bounds(int(year), int(week))
	ref_day = getdate(today())

	filters = {"crop": crop, "status": ("!=", "Retired")}
	if farm:
		filters["farm"] = farm
	rows = frappe.get_all(
		"Production Unit",
		filters=filters,
		fields=["name", "parent_production_unit as parent", "unit_type", "is_group", "area_ha", "geojson", "status"],
		order_by="lft asc",
	)
	cycles = analytics.current_cycles(crop)
	task_rows = _task_rows(crop, year, week, farm or None)

	colors = dict(frappe.get_all("Production Operation", filters={"crop": crop}, fields=["name", "color"], as_list=True))
	work_by_unit = {}
	for w in _work_rows(crop, start, end, farm or None):
		work_by_unit.setdefault(w.unit, []).append(w)
	legend = {}
	ops, by_unit = {}, {}
	for r in task_rows:
		ops.setdefault(r.operation, {"operation": r.operation, "operation_name": r.operation_name or r.operation, "uom": r.uom})
		if operation and r.operation != operation:
			continue
		by_unit.setdefault(r.unit, []).append(_shape_task(r, end, ref_day))

	units, outlines = [], []
	totals = {"blocks": 0, "planned": {}, "done": {}, "remaining": {}, "pending": {}, "late": 0,
		"by_state": {s: 0 for s in STATES}, "tasks": 0}
	for u in rows:
		gj = _geo(u.geojson)
		if u.is_group:
			outlines.append({"name": u.name, "unit_type": u.unit_type, "area_ha": flt(u.area_ha), "geojson": gj})
			continue
		tasks = by_unit.get(u.name, [])
		state = unit_state(tasks)
		if status and state != status:
			continue
		cy = cycles.get(u.name)
		activity = unit_activity(work_by_unit.get(u.name, []), tasks, colors)
		if activity:
			legend.setdefault(activity["operation"], activity["color"])
		remaining = {}
		for t in tasks:
			if t["status"] == "Skipped":
				continue
			_add(totals["planned"], t["uom"], t["planned_qty"])
			_add(totals["done"], t["uom"], t["done_qty"])
			_add(totals["remaining"], t["uom"], t["remaining_qty"])
			_add(totals["pending"], t["uom"], t["pending_qty"] or 0.0)
			if t["remaining_qty"] > 0:
				_add(remaining, t["uom"], t["remaining_qty"])
		totals["blocks"] += 1
		totals["by_state"][state] += 1
		totals["late"] += state == "late"
		totals["tasks"] += len(tasks)
		units.append({
			"name": u.name,
			"parent": u.parent,
			"unit_type": u.unit_type,
			"area_ha": flt(u.area_ha),
			"geojson": gj,
			"cycle": cy.name if cy else None,
			"item": cy.item if cy else None,
			"variety": cy.variety if cy else None,
			"current_stage": cy.current_stage if cy else None,
			"tasks": tasks,
			"progress_pct": progress_pct(tasks),
			"remaining_qty": remaining,
			"state": state,
			"activity": activity,
		})

	center, bounds = _bounds([u["geojson"] for u in units] + [o["geojson"] for o in outlines])
	return {
		"week_start": str(start),
		"week_end": str(end),
		"units": units,
		"outlines": outlines,
		"totals": totals,
		"legend": [{"operation": o, "color": c} for o, c in sorted(legend.items())],
		"operations": sorted(ops.values(), key=lambda o: o["operation_name"]),
		"center": center,
		"bounds": bounds,
	}
