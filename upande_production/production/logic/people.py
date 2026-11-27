"""People profiles: per-person figures over a date range for the desk Supervisors and Casual Labourers pages.

Every figure is computed from rows read in a fixed number of queries (no per-person queries). No pay amounts.
Scores (0-100, outward is better) feed the radar; `medians` are the farm medians shown beside each person."""
from collections import defaultdict
from datetime import timedelta
from statistics import median

import frappe
from frappe.utils import add_days, getdate, today

from upande_production.production.logic import supervisor_page, supervisors, task_approval
from upande_production.production.logic.units import unit_filter
from upande_production.production.logic.weeks import iso_of

DEFAULT_DAYS = 28  # four weeks
STALE_DAYS = 3  # an open task with no progress log this long is flagged
ABSENT_DAYS = 14  # an active labourer not seen this long is flagged
CHECK_CAP_DAYS = 7  # a check this slow scores zero
FINISHED = supervisors.FINISHED


def date_range(from_date=None, to_date=None):
	"""(from, to) as dates; defaults to the last four weeks ending today."""
	to = getdate(to_date) if to_date else getdate(today())
	frm = getdate(from_date) if from_date else add_days(to, -DEFAULT_DAYS)
	if frm > to:
		frm, to = to, frm
	return frm, to


def weeks_of(frm, to) -> list[str]:
	"""Monday (ISO date string) of every week touching the range, oldest first."""
	d = frm - timedelta(days=frm.weekday())
	out = []
	while d <= to:
		out.append(str(d))
		d += timedelta(days=7)
	return out


def week_key(d) -> str:
	d = getdate(d)
	return str(d - timedelta(days=d.weekday()))


def pct(n, d):
	"""n as a percent of d, one decimal; None when d is zero."""
	return round(100.0 * n / d, 1) if d else None


def med(values):
	"""Median of the non-None values, one decimal; None when there are none."""
	xs = [v for v in values if v is not None]
	return round(median(xs), 1) if xs else None


def shares(counter, names=None, limit=8) -> list[dict]:
	"""[{key, label, count, share}] biggest first; share is a percent of the total."""
	total = sum(counter.values())
	rows = sorted(counter.items(), key=lambda kv: (-kv[1], str(kv[0])))[:limit]
	return [{"key": k, "label": (names or {}).get(k) or k, "count": n, "share": pct(n, total)} for k, n in rows]


def medians_of(people, keys, scope=("metrics", "scores")) -> dict:
	return {k: med(p[s].get(k) for p in people for s in scope if k in p[s]) for k in keys}


# -- supervisors -----------------------------------------------------------------------------------------------


def _plan_tasks(crop, frm, to):
	"""Work plan tasks due in the range, each tagged with its plan's (year, week), plus {(year, week)}."""
	plans = frappe.get_all("Production Work Plan", filters={"crop": crop, "week_start": ("between", [add_days(frm, -6), to])},
		fields=["name", "plan_year", "plan_week"])
	if not plans:
		return [], {}
	by_plan = {p.name: (p.plan_year, p.plan_week) for p in plans}
	filters = unit_filter({"parent": ("in", list(by_plan)), "parenttype": "Production Work Plan",
		"due_date": ("between", [frm, to]), **task_approval.visible_filter()})
	tasks = frappe.get_all("Work Plan Task", filters=filters, parent_doctype="Production Work Plan",
		fields=["name", "parent", "unit", "operation", "supervisor", "status", "deviation", "due_date", "completed_at",
			"postpone_count"])
	for t in tasks:
		t["wk"] = by_plan[t.parent]
	return tasks, by_plan


def _is_done_on_time(t) -> bool:
	if t.status != "Done" or t.deviation == "Late":
		return False
	return not t.completed_at or getdate(t.completed_at) <= getdate(t.due_date)


def _is_late(t, today_) -> bool:
	"""Postponed at least once, flagged Late, or still unfinished past its due date."""
	return bool(t.postpone_count) or t.deviation == "Late" or (t.status not in FINISHED and getdate(t.due_date) < today_)


def supervisor_people(crop, from_date=None, to_date=None) -> dict:
	"""The Supervisors roster with each supervisor's figures, flags, block shares and weekly strip for the range."""
	supervisor_page._need_crop(crop)
	frm, to = date_range(from_date, to_date)
	today_ = getdate(today())
	year, week = iso_of(today_)
	sups = frappe.get_all("Production Supervisor", fields=supervisors.SUPERVISOR_FIELDS, order_by="employee_name asc")
	now = supervisor_page._Week(crop, year, week)
	held = {s.name: now.assignments_of(s.name) for s in sups}
	scoped = supervisor_page._scoped()
	sups = [s for s in sups if not scoped.get(s.name) or crop in scoped[s.name] or held[s.name]]
	names = [s.name for s in sups]
	images, crews = supervisor_page._images(names), supervisor_page._crew(names)

	tasks, plan_week = _plan_tasks(crop, frm, to)
	cats = supervisors.operation_categories(t.operation for t in tasks)
	week_rows = defaultdict(list)
	for r in frappe.get_all(supervisors.DOCTYPE, filters={"crop": crop, "plan_year": ("in", list({y for y, _w in plan_week.values()})),
			"plan_week": ("in", list({w for _y, w in plan_week.values()}))}, fields=supervisors.FIELDS + ["plan_year", "plan_week"]) if tasks else []:
		week_rows[(r.plan_year, r.plan_week)].append(r)
	active = supervisors.active_map([r for rows in week_rows.values() for r in rows])
	keyed = {wk: supervisors.by_key(rows, active) for wk, rows in week_rows.items()}
	by_week = defaultdict(list)
	for t in tasks:
		by_week[t["wk"]].append(t)

	def visible(emp):
		out = []
		for wk, ts in by_week.items():
			out += supervisors._visible(emp, ts, keyed.get(wk, {}), cats)
		return out

	mine = {s.name: visible(s.name) if s.active else [] for s in sups}
	logs = defaultdict(list)  # task -> [log_date]
	task_names = list({t.name for ts in mine.values() for t in ts})
	if task_names:
		for r in frappe.get_all("Task Progress Log", filters={"task": ("in", task_names)}, fields=["task", "log_date"]):
			logs[r.task].append(getdate(r.log_date))

	# crew entries: those in the range (sent back, check speed) and those waiting on a check now
	crew_of = {e: [c.employee for c in cs] for e, cs in crews.items()}
	crew_all = [c for cs in crew_of.values() for c in cs]
	entries = defaultdict(list)
	waiting = defaultdict(int)
	if crew_all:
		owner = {c: e for e, cs in crew_of.items() for c in cs}
		for r in frappe.get_all("Casual Labour Work", filters={"employee": ("in", crew_all), "crop": crop, "docstatus": ("<", 2),
				"work_date": ("between", [frm, to])}, fields=["employee", "approval_status", "creation", "checked_at"]):
			entries[owner[r.employee]].append(r)
		for r in frappe.get_all("Casual Labour Work", filters={"employee": ("in", crew_all), "crop": crop, "docstatus": 0,
				"approval_status": "Pending"}, fields=["employee"]):
			waiting[owner[r.employee]] += 1

	unit_names = dict(frappe.get_all("Production Unit", filters={"name": ("in", list({t.unit for ts in mine.values() for t in ts}) or [""])},
		fields=["name", "unit_name"], as_list=True))
	weeks = weeks_of(frm, to)
	people = []
	for s in sups:
		ts = mine[s.name]
		full = supervisor_page._full(s)
		due = [t for t in ts if getdate(t.due_date) <= today_]
		on_time = sum(1 for t in due if _is_done_on_time(t))
		late = sum(1 for t in ts if _is_late(t, today_))
		overdue = [t for t in ts if t.status not in FINISHED and getdate(t.due_date) < today_]
		stale = []
		in_range_logs = []
		for t in ts:
			ds = logs.get(t.name, [])
			in_range_logs += [d for d in ds if frm <= d <= to]
			if t.status not in FINISHED and getdate(t.due_date) <= today_:
				anchor = max(ds) if ds else getdate(t.due_date)
				if (today_ - anchor).days >= STALE_DAYS:
					stale.append(t)
		active_days = len(set(in_range_logs))
		es = entries.get(s.name, [])
		sent_back = sum(1 for e in es if e.approval_status == "Sent Back")
		lags = [(e.checked_at - e.creation).total_seconds() / 86400 for e in es if e.checked_at and e.creation]
		lags = [max(0.0, x) for x in lags]
		check_days = round(sum(lags) / len(lags), 1) if lags else None
		per_week = {w: {"week": w, "done": 0, "logs": 0} for w in weeks}
		for t in ts:
			if t.status == "Done":
				wk = week_key(t.completed_at or t.due_date)
				if wk in per_week:
					per_week[wk]["done"] += 1
		for d in in_range_logs:
			per_week[week_key(d)]["logs"] += 1
		blocks = supervisor_page._blocks(held[s.name], unit_names)
		metrics = {
			"assigned": len(ts), "done": sum(1 for t in ts if t.status == "Done"),
			"on_time_pct": pct(on_time, len(due)), "late_pct": pct(late, len(ts)),
			"logs": len(in_range_logs), "active_days": active_days,
			"logs_per_day": round(len(in_range_logs) / active_days, 1) if active_days else None,
			"sent_back": sent_back if full else None, "entries": len(es) if full else None,
			"sent_back_pct": pct(sent_back, len(es)) if full else None,
			"check_days": check_days if full else None,
		}
		flags = []
		if overdue:
			flags.append({"kind": "overdue", "label": "Overdue tasks", "count": len(overdue),
				"detail": f"{len(overdue)} unfinished past their due date."})
		if full and waiting.get(s.name):
			flags.append({"kind": "waiting", "label": "Labour waiting on their check", "count": waiting[s.name],
				"detail": f"{waiting[s.name]} entries from their crew are still Pending."})
		if stale:
			flags.append({"kind": "stale", "label": "No progress log", "count": len(stale),
				"detail": f"{len(stale)} open tasks with no log for {STALE_DAYS}+ days."})
		people.append({
			"employee": s.name, "employee_name": s.employee_name, "image": s.image or images.get(s.name), "phone": s.phone,
			"user": s.user, "farm": s.farm, "active": bool(s.active),
			"blocks": len(blocks), "activities": sum(len(b["categories"]) for b in blocks),
			"overseer": any(b["overseer"] for b in blocks), "crew": sum(1 for c in crews.get(s.name, []) if c.active),
			"full": full, "metrics": metrics, "scores": {}, "flags": flags,
			"where": shares(_count(ts, "unit"), unit_names),
			"weekly": list(per_week.values()),
		})
	top = max((p["metrics"]["logs_per_day"] or 0 for p in people), default=0)
	for p in people:
		m = p["metrics"]
		p["scores"] = {
			"on_time": m["on_time_pct"],
			"steady": None if m["late_pct"] is None else round(100 - m["late_pct"], 1),
			"logging": round(100 * m["logs_per_day"] / top, 1) if m["logs_per_day"] and top else (0.0 if m["assigned"] else None),
			"returns": None if m["sent_back_pct"] is None else round(100 - m["sent_back_pct"], 1),
			"check_speed": None if m["check_days"] is None else round(100 * (1 - min(m["check_days"], CHECK_CAP_DAYS) / CHECK_CAP_DAYS), 1),
		}
	live = [p for p in people if p["active"] and p["metrics"]["assigned"]]
	return {
		"from": str(frm), "to": str(to), "weeks": weeks, "people": people,
		"medians": medians_of(live, [*people[0]["metrics"], *people[0]["scores"]] if people else []),
		"can_manage": supervisors.can_manage(),
	}


def _count(rows, field) -> dict:
	out = defaultdict(int)
	for r in rows:
		if r.get(field):
			out[r[field]] += 1
	return out


# -- casual labourers ------------------------------------------------------------------------------------------


def _workdays(frm, to) -> int:
	"""Days in the range up to today, Sundays excluded (the farm works six days)."""
	end = min(to, getdate(today()))
	n, d = 0, frm
	while d <= end:
		n += d.weekday() != 6
		d += timedelta(days=1)
	return n


def labourer_people(crop, from_date=None, to_date=None) -> dict:
	"""The Casual Labourers roster with each person's figures, flags, block/activity shares and weekly strip."""
	supervisor_page._need_crop(crop)
	frm, to = date_range(from_date, to_date)
	today_ = getdate(today())
	roster = frappe.get_all("Casual Labourer", fields=["employee", "employee_name", "active", "supervisor", "supervisor_name", "crew"],
		order_by="employee_name asc")
	emps = [r.employee for r in roster]
	images = supervisor_page._images(emps)
	rows = frappe.get_all("Casual Labour Work", filters=unit_filter({"employee": ("in", emps or [""]), "crop": crop,
		"docstatus": ("<", 2), "work_date": ("between", [frm, to])}),
		fields=["employee", "work_date", "plan_task", "unit", "operation", "qty", "uom", "approval_status"])
	last = dict(frappe.get_all("Casual Labour Work", filters={"employee": ("in", emps or [""]), "crop": crop, "docstatus": ("<", 2),
		"approval_status": ("!=", "Sent Back")}, fields=["employee", {"MAX": "work_date", "as": "last"}], group_by="employee",
		as_list=True))
	ops = dict(frappe.get_all("Field Operation", filters={"name": ("in", list({r.operation for r in rows if r.operation}) or [""])},
		fields=["name", "operation_name"], as_list=True))
	unit_names = dict(frappe.get_all("Production Unit", filters={"name": ("in", list({r.unit for r in rows if r.unit}) or [""])},
		fields=["name", "unit_name"], as_list=True))
	mine = defaultdict(list)
	for r in rows:
		mine[r.employee].append(r)

	# output per working day, by (activity, unit of measure): what each person does against the others on it
	perday = {}  # (employee, key) -> (qty per day, days)
	by_key = defaultdict(list)
	for e, rs in mine.items():
		agg = defaultdict(lambda: [0.0, set()])
		for r in rs:
			if r.approval_status != "Sent Back" and r.operation:
				a = agg[(r.operation, r.uom)]
				a[0] += r.qty or 0
				a[1].add(str(r.work_date))
		for k, (q, days) in agg.items():
			perday[(e, k)] = (q / len(days), len(days))
			by_key[k].append(q / len(days))
	peer = {k: median(v) for k, v in by_key.items() if len(v) >= 2 and median(v) > 0}

	weeks = weeks_of(frm, to)
	workdays = _workdays(frm, to)
	people = []
	for r in roster:
		rs = mine.get(r.employee, [])
		counted = [x for x in rs if x.approval_status != "Sent Back"]
		sent_back = [x for x in rs if x.approval_status == "Sent Back"]
		days = {str(x.work_date) for x in counted}
		idx_num = idx_den = 0.0
		for (e, k), (v, n) in perday.items():
			if e == r.employee and k in peer:
				idx_num += n * v / peer[k]
				idx_den += n
		idx = round(100 * idx_num / idx_den, 1) if idx_den else None
		uoms = _count(({"u": x.uom} for x in counted), "u")
		uom = max(uoms, key=lambda u: (uoms[u], u)) if uoms else None
		uom_days = {str(x.work_date) for x in counted if x.uom == uom}
		uom_qty = sum(x.qty or 0 for x in counted if x.uom == uom)
		per_week = {w: {"week": w, "days": set(), "output": 0.0} for w in weeks}
		for x in counted:
			w = per_week[week_key(x.work_date)]
			w["days"].add(str(x.work_date))
			if x.uom == uom:
				w["output"] += x.qty or 0
		weekly = [{"week": w["week"], "days": len(w["days"]), "output": round(w["output"], 1)} for w in per_week.values()]
		seen = last.get(r.employee)
		metrics = {
			"days_worked": len(days), "tasks": len({x.plan_task for x in counted if x.plan_task}), "entries": len(rs),
			"output_per_day": round(uom_qty / len(uom_days), 1) if uom_days else None,
			"output_vs_peers": idx, "sent_back": len(sent_back), "sent_back_pct": pct(len(sent_back), len(rs)),
			"attendance_pct": min(100.0, pct(len(days), workdays)) if workdays and days else (0.0 if workdays else None),
		}
		flags = []
		if sent_back:
			flags.append({"kind": "sent_back", "label": "Sent-back work not fixed", "count": len(sent_back),
				"detail": f"{len(sent_back)} entries sent back and still waiting for a correction."})
		gap = (today_ - getdate(seen)).days if seen else None
		if r.active and (gap is None or gap >= ABSENT_DAYS):
			flags.append({"kind": "absent", "label": f"Absent {ABSENT_DAYS}+ days",
				"count": gap or 0, "detail": f"Last worked {gap} days ago." if gap is not None else "No work recorded yet."})
		people.append({
			"employee": r.employee, "employee_name": r.employee_name, "image": images.get(r.employee), "active": bool(r.active),
			"supervisor": r.supervisor, "supervisor_name": r.supervisor_name, "crew": r.crew,
			"last_worked": str(seen) if seen else None, "output_uom": uom, "metrics": metrics,
			"scores": {
				"attendance": metrics["attendance_pct"],
				"output": None if idx is None else round(min(100.0, idx / 2), 1),
				"quality": None if metrics["sent_back_pct"] is None else round(100 - metrics["sent_back_pct"], 1),
			},
			"flags": flags,
			"where_blocks": shares(_count(counted, "unit"), unit_names),
			"where_activities": shares(_count(counted, "operation"), ops),
			"weekly": weekly,
		})
	live = [p for p in people if p["active"] and p["metrics"]["days_worked"]]
	return {
		"from": str(frm), "to": str(to), "weeks": weeks, "people": people, "workdays": workdays,
		"medians": medians_of(live, ["days_worked", "tasks", "output_vs_peers", "sent_back_pct", "attendance_pct",
			"attendance", "output", "quality"]),
	}
