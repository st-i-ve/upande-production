"""Extra figures for the Overview page: weekly trends, this week by operation,
upcoming work, recent deviations and per-block activity. Envelope pattern as in
api/production.py; pay figures are None unless the caller may see pay."""

from datetime import timedelta

import frappe
from frappe.utils import getdate, today

from upande_production.api.envelope import run
from upande_production.production.logic import analytics
from upande_production.production.logic.approvals import approval_counts
from upande_production.production.logic.settings import can_see_pay
from upande_production.production.logic.units import retired_sql, unit_filter
from upande_production.production.logic.weeks import iso_of

TREND_WEEKS = 8
DEVIATION_KINDS = ("Late", "Partial", "Skipped")


def _week_label(monday):
	y, w = iso_of(monday)
	return f"{y}-W{w:02d}"


def _trend(crop, names, pay):
	"""Oldest-first weekly series for the last TREND_WEEKS ISO weeks, this one included."""
	this_monday = analytics._monday(getdate(today()))
	out = []
	for i in range(TREND_WEEKS - 1, -1, -1):
		monday = this_monday - timedelta(days=7 * i)
		sunday = monday + timedelta(days=6)
		y, w = iso_of(monday)
		tasks = analytics._week_tasks(crop, y, w)
		done = sum(1 for k in tasks if k.status == "Done")
		labour = sum(analytics._labour_by_unit(names, monday, sunday).values())
		harvest = sum(analytics._harvest_by_unit(names, monday, sunday)[0].values())
		out.append({
			"week": _week_label(monday),
			"week_start": str(monday),
			"tasks": len(tasks),
			"done": done,
			"done_pct": round(done / len(tasks) * 100, 1) if tasks else 0,
			"deviations": sum(1 for k in tasks if k.deviation in DEVIATION_KINDS),
			"labour": round(labour, 2) if pay else None,
			"harvest": round(harvest, 2),
		})
	return out


def _forecast_weeks(crop):
	start = analytics._monday(getdate(today()))
	out = []
	for i in range(4):
		monday = start + timedelta(days=7 * i)
		sunday = monday + timedelta(days=6)
		fc = frappe.db.sql(
			"""select sum(w.expected_qty) from `tabProduction Forecast Week` w
			join `tabProduction Forecast` f on f.name = w.parent
			where f.crop = %s and w.week_start between %s and %s and f.unit not in %s""",
			(crop, monday, sunday, retired_sql()),
		)[0][0]
		cm = frappe.db.sql(
			"""select sum(committed_qty) from `tabBuyer Commitment`
			where crop = %s and status != 'Cancelled' and week_start between %s and %s""",
			(crop, monday, sunday),
		)[0][0]
		out.append({"week": _week_label(monday), "week_start": str(monday), "forecast": float(fc or 0), "committed": float(cm or 0)})
	return out


def _operations(crop):
	y, w = iso_of(getdate(today()))
	plans = frappe.get_all("Production Work Plan", filters={"crop": crop, "plan_year": y, "plan_week": w}, pluck="name")
	if not plans:
		return []
	rows = frappe.get_all(
		"Production Plan Task",
		filters=unit_filter({"parenttype": "Production Work Plan", "parent": ("in", plans)}),
		fields=["operation_name", "uom", "planned_qty", "done_qty", "pending_qty", "status"],
	)
	agg = {}
	for k in rows:
		a = agg.setdefault(k.operation_name, {
			"operation_name": k.operation_name, "uom": k.uom, "planned": 0, "done": 0, "pending": 0,
			"tasks": 0, "tasks_done": 0,
		})
		a["planned"] += k.planned_qty or 0
		a["done"] += k.done_qty or 0
		a["pending"] += k.pending_qty or 0
		a["tasks"] += 1
		a["tasks_done"] += 1 if k.status == "Done" else 0
	return sorted(agg.values(), key=lambda a: -a["planned"])


def _upcoming(crop):
	plans = frappe.get_all("Production Work Plan", filters={"crop": crop}, pluck="name")
	if not plans:
		return []
	return frappe.get_all(
		"Production Plan Task",
		filters=unit_filter({
			"parenttype": "Production Work Plan", "parent": ("in", plans),
			"status": ("in", ["Open", "In Progress"]), "due_date": (">=", getdate(today())),
		}),
		fields=["unit", "operation_name", "due_date", "status", "planned_qty", "done_qty", "uom"],
		order_by="due_date asc",
		limit=8,
	)


def _recent_deviations(crop):
	t = getdate(today())
	rows = analytics.deviations(crop, t - timedelta(days=28), t)["rows"]
	rows.sort(key=lambda r: str(r.get("due_date") or ""), reverse=True)
	return [
		{k: (str(v) if k == "due_date" and v else v) for k, v in r.items()} for r in rows[:8]
	]


def _block_activity(names, pay):
	"""unit -> last work date and 30-day hours/crew, own units only (not rolled up)."""
	if not names:
		return {}
	t = getdate(today())
	rows = frappe.db.sql(
		"""select unit, max(work_date), sum(case when work_date >= %(since)s then hours else 0 end),
		count(distinct case when work_date >= %(since)s then employee end)
		from `tabValue Adder Work` where docstatus = 1 and unit in %(u)s group by unit""",
		{"u": tuple(names), "since": t - timedelta(days=30)},
	)
	harvest = frappe.db.sql(
		"""select unit, max(harvest_date) from `tabProduction Harvest` where unit in %(u)s group by unit""",
		{"u": tuple(names)},
	)
	last_h = {r[0]: r[1] for r in harvest}
	out = {}
	for unit, last, hours, crew in rows:
		out[unit] = {"last_work": last, "hours_30d": float(hours or 0), "crew_30d": int(crew or 0)}
	for unit, last in last_h.items():
		out.setdefault(unit, {"last_work": None, "hours_30d": 0, "crew_30d": 0})["last_harvest"] = last
	return out


def get_extras(crop, pay):
	units = analytics.crop_units(crop)
	names = [u.name for u in units]
	cycles = analytics.current_cycles(crop)
	activity = _block_activity(names, pay)
	t = getdate(today())
	blocks = []
	for u in units:
		cyc = cycles.get(u.name)
		act = activity.get(u.name, {})
		last = max([d for d in (act.get("last_work"), act.get("last_harvest")) if d], default=None)
		blocks.append({
			"unit": u.name,
			"stage": frappe.db.get_value("Production Crop Cycle", cyc.name, "status") if cyc else None,
			"cycle_day": (t - getdate(cyc.start_date)).days if cyc and cyc.start_date else None,
			"last_activity": str(last) if last else None,
			"hours_30d": act.get("hours_30d", 0),
			"crew_30d": act.get("crew_30d", 0),
		})
	# Submissions (the cards on the Approvals page), not entries: the same count the sidebar badge shows.
	pending = next((c["pending"] for c in approval_counts()["crops"] if c["crop"] == crop), 0)
	return {
		"trend": _trend(crop, names, pay),
		"forecast_weeks": _forecast_weeks(crop),
		"operations": _operations(crop),
		"upcoming": [{k: (str(v) if k == "due_date" else v) for k, v in r.items()} for r in _upcoming(crop)],
		"recent_deviations": _recent_deviations(crop),
		"blocks": blocks,
		"pending_approvals": pending,
	}


@frappe.whitelist(methods=["POST"])
@run
def get_overview_extras(crop):
	frappe.has_permission("Production Unit", "read", throw=True)
	return get_extras(crop, can_see_pay())


def _breakdown(crop, employee, frm, to, key, pay):
	data = frappe.db.sql(
		f"""select {key}, uom, sum(qty), sum(hours), sum(pay_value), count(*)
		from `tabValue Adder Work`
		where docstatus = 1 and crop = %s and employee = %s and work_date between %s and %s and unit not in %s
		group by {key}, uom order by {key}""",
		(crop, employee, frm, to, retired_sql()),
	)
	grouped = {}
	for k, uom, qty, hours, pv, n in data:
		g = grouped.setdefault(str(k), {"uoms": [], "hours": 0.0, "pay": 0.0, "entries": 0})
		g["uoms"].append((uom, qty))
		g["hours"] += float(hours or 0)
		g["pay"] += float(pv or 0)
		g["entries"] += n
	return [
		{
			"key": k, "qty_by_uom": analytics.merge_uoms(g["uoms"]), "hours": g["hours"],
			"pay_value": round(g["pay"], 2) if pay else None, "entries": g["entries"],
		}
		for k, g in grouped.items()
	]


def get_value_adder_detail_data(crop, employee, from_date, to_date, pay):
	frm, to = analytics._range(from_date, to_date)
	base = unit_filter({"crop": crop, "employee": employee, "work_date": ("between", [frm, to])})
	recent = frappe.get_all(
		"Value Adder Work",
		filters={**base, "docstatus": 1},
		fields=["work_date", "unit", "operation", "qty", "uom", "hours", "pay_value"],
		order_by="work_date desc, creation desc",
		limit=10,
	)
	for w in recent:
		if not pay:
			w["pay_value"] = None
	return {
		"employee": employee,
		"employee_name": frappe.db.get_value("Employee", employee, "employee_name") or employee,
		"by_day": _breakdown(crop, employee, frm, to, "work_date", pay),
		"by_unit": _breakdown(crop, employee, frm, to, "unit", pay),
		"by_operation": _breakdown(crop, employee, frm, to, "operation", pay),
		"recent": recent,
		"pending_entries": frappe.db.count("Value Adder Work", {**base, "docstatus": 0, "approval_status": "Pending"}),
	}


@frappe.whitelist(methods=["POST"])
@run
def value_adder_detail(crop, employee, from_date=None, to_date=None):
	frappe.has_permission("Value Adder Work", "read", throw=True)
	return get_value_adder_detail_data(crop, employee, from_date, to_date, can_see_pay())
