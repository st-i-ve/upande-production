"""Casual labourers: the roster, daily targets and the KPIs built on approved work.

Pay is per unit of work (qty x the operation's rate per unit) and is never touched here. A daily target
is a yardstick: for one person, one operation and one day the approved quantity is compared with the
target (the person's override, else the operation's default). A target applies only to work counted in
the target's UOM, so quantities in different units are never added together.
"""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint, flt

from upande_production.production.logic import analytics
from upande_production.production.logic.units import retired_sql


# -- targets -------------------------------------------------------------------


def operation_defaults(operations=None) -> dict:
	"""operation -> {"target", "uom", "name"}: the operation's default daily target (0 when none)."""
	filters = {"name": ("in", list(operations))} if operations is not None else {}
	if operations is not None and not operations:
		return {}
	out = {}
	for o in frappe.get_all("Field Operation", filters=filters,
			fields=["name", "operation_name", "daily_target", "target_uom", "work_uom"]):
		out[o.name] = {"target": flt(o.daily_target), "uom": o.target_uom or o.work_uom, "name": o.operation_name}
	return out


def person_overrides(employees=None) -> dict:
	"""employee -> {operation: {"target", "uom"}} from the roster's per-person rows."""
	filters = {"parent": ("in", list(employees))} if employees is not None else {}
	if employees is not None and not employees:
		return {}
	out = defaultdict(dict)
	for r in frappe.get_all("Casual Labourer Target", filters={**filters, "parenttype": "Casual Labourer"},
			fields=["parent", "operation", "daily_target", "uom"]):
		out[r.parent][r.operation] = {"target": flt(r.daily_target), "uom": r.uom}
	return out


def resolve_target(defaults, overrides, employee, operation):
	"""(target, uom, is_override) for a person and operation; target 0 means no target."""
	d = defaults.get(operation) or {}
	o = (overrides.get(employee) or {}).get(operation)
	if o and o["target"] > 0:
		return o["target"], o["uom"] or d.get("uom"), True
	return flt(d.get("target")), d.get("uom"), False


def _met(qty, target, work_uom, target_uom):
	"""True/False against a target, None when there is no target or the work is in another UOM."""
	if not target or (target_uom and work_uom and target_uom != work_uom):
		return None
	return flt(qty) >= flt(target)


def annotate_work(rows):
	"""Add target / day_qty / target_met to work rows (dicts with employee, operation, work_date and uom):
	the day's total for that person and operation against the daily target. Never changes pay."""
	rows = [r for r in rows if r.get("employee") and r.get("operation") and r.get("work_date")]
	if not rows:
		return
	emps = {r["employee"] for r in rows}
	ops = {r["operation"] for r in rows}
	defaults = operation_defaults(ops)
	overrides = person_overrides(emps)
	days = defaultdict(float)
	for e, op, d, q in frappe.db.sql(
		"""select employee, operation, work_date, sum(qty) from `tabCasual Labour Work`
		where docstatus < 2 and employee in %s and operation in %s group by employee, operation, work_date""",
		(tuple(emps), tuple(ops)),
	):
		days[(e, op, str(d))] = flt(q)
	for r in rows:
		target, uom, _o = resolve_target(defaults, overrides, r["employee"], r["operation"])
		day_qty = days.get((r["employee"], r["operation"], str(r["work_date"])), flt(r.get("qty")))
		r["target"] = target or None
		r["target_uom"] = uom if target else None
		r["day_qty"] = day_qty
		r["target_met"] = _met(day_qty, target, r.get("uom"), uom)


# -- aggregation ---------------------------------------------------------------


def _days(crop, frm, to, employee=None):
	"""Approved work grouped to one row per person, day, operation and UOM."""
	extra, args = "", [crop, frm, to, retired_sql()]
	if employee:
		extra = " and employee = %s"
		args.append(employee)
	return frappe.db.sql(
		f"""select employee, max(employee_name), work_date, operation, uom, sum(qty), sum(pay_value),
		sum(if(ifnull(paid, 'Unpaid') = 'Paid', pay_value, 0)), count(*)
		from `tabCasual Labour Work`
		where docstatus = 1 and crop = %s and work_date between %s and %s and unit not in %s{extra}
		group by employee, work_date, operation, uom""",
		tuple(args),
	)


def _score(rows):
	"""Fold day rows into per-person figures. Returns (by_person, by_date)."""
	ops = {r[3] for r in rows}
	emps = {r[0] for r in rows}
	defaults, overrides = operation_defaults(ops), person_overrides(emps)
	people = {}
	dates = {}

	def blank():
		return {"dates": set(), "uoms": [], "pay": 0.0, "paid": 0.0, "entries": 0, "target_days": 0, "met_days": 0,
			"ratios": [], "name": None}

	for emp, name, d, op, uom, qty, pay, paid, n in rows:
		p = people.setdefault(emp, blank())
		p["name"] = p["name"] or name
		p["dates"].add(str(d))
		p["uoms"].append((uom, qty))
		p["pay"] += flt(pay)
		p["paid"] += flt(paid)
		p["entries"] += n
		target, t_uom, _o = resolve_target(defaults, overrides, emp, op)
		met = _met(qty, target, uom, t_uom)
		dd = dates.setdefault(str(d), {"people": set(), "pay": 0.0, "target_days": 0, "met_days": 0, "uoms": [], "entries": 0})
		dd["people"].add(emp)
		dd["pay"] += flt(pay)
		dd["uoms"].append((uom, qty))
		dd["entries"] += n
		if met is not None:
			p["target_days"] += 1
			p["met_days"] += 1 if met else 0
			p["ratios"].append(flt(qty) / target)
			dd["target_days"] += 1
			dd["met_days"] += 1 if met else 0
	return people, dates


def _rate(met, total):
	return round(met * 100.0 / total, 1) if total else None


def _money(v, pay):
	return round(v, 2) if pay else None


def labourer_list(crop, from_date, to_date, pay, search="", department="", designation="", active=""):
	"""Roster rows with KPIs for the crop over the range, plus totals and a day series."""
	frm, to = analytics._range(from_date, to_date)
	filters = {}
	if active not in ("", None):
		filters["active"] = cint(active)
	roster = frappe.get_all(
		"Casual Labourer", filters=filters,
		fields=["name", "employee", "employee_name", "department", "designation", "active", "supervisor_name", "crew"],
		order_by="employee_name asc",
	)
	if department:
		roster = [r for r in roster if r.department == department]
	if designation:
		roster = [r for r in roster if r.designation == designation]
	if search:
		s = search.lower()
		roster = [r for r in roster if s in (r.employee_name or "").lower() or s in r.employee.lower()
			or s in (r.crew or "").lower()]
	people, dates = _score(_days(crop, frm, to))
	images = dict(frappe.get_all("Employee", filters={"name": ("in", [r.employee for r in roster])},
		fields=["name", "image"], as_list=True)) if roster else {}
	n_targets = dict(frappe.db.sql(
		"select parent, count(*) from `tabCasual Labourer Target` group by parent")) if roster else {}
	rows = []
	for r in roster:
		p = people.get(r.employee)
		rows.append({
			**r, "image": images.get(r.employee), "overrides": cint(n_targets.get(r.employee)),
			"days_worked": len(p["dates"]) if p else 0,
			"qty_by_uom": analytics.merge_uoms(p["uoms"]) if p else [],
			"entries": p["entries"] if p else 0,
			"target_days": p["target_days"] if p else 0, "met_days": p["met_days"] if p else 0,
			"hit_rate": _rate(p["met_days"], p["target_days"]) if p else None,
			"pay_value": _money(p["pay"], pay) if p else (0.0 if pay else None),
			"unpaid_value": _money(p["pay"] - p["paid"], pay) if p else (0.0 if pay else None),
		})
	shown = {r["employee"] for r in rows}
	mine = [people[e] for e in people if e in shown]
	met, tdays = sum(p["met_days"] for p in mine), sum(p["target_days"] for p in mine)
	series = [
		{"key": d, "labourers": len(v["people"]), "pay_value": _money(v["pay"], pay),
		"hit_rate": _rate(v["met_days"], v["target_days"])}
		for d, v in sorted(dates.items())
	]
	return {
		"rows": rows, "days": series,
		"totals": {
			"labourers": len(rows), "active": sum(1 for r in rows if r["active"]),
			"working": len(mine), "days_worked": sum(len(p["dates"]) for p in mine),
			"qty_by_uom": analytics.merge_uoms(u for p in mine for u in p["uoms"]),
			"hit_rate": _rate(met, tdays), "target_days": tdays,
			"pay_value": _money(sum(p["pay"] for p in mine), pay),
			"unpaid_value": _money(sum(p["pay"] - p["paid"] for p in mine), pay),
		},
	}


def labourer_detail(crop, employee, from_date, to_date, pay):
	frm, to = analytics._range(from_date, to_date)
	emp = frappe.db.get_value("Employee", employee, ["employee_name", "department", "designation", "image"], as_dict=True)
	if not emp:
		frappe.throw(_("Employee {0} not found").format(employee), frappe.ValidationError)
	roster = frappe.db.get_value("Casual Labourer", employee, ["active", "supervisor", "supervisor_name", "crew"], as_dict=True)
	rows = _days(crop, frm, to, employee)
	defaults = operation_defaults({r[3] for r in rows})
	overrides = person_overrides([employee])
	people, _dates = _score(rows)
	p = people.get(employee)

	ops = {}
	daily = []
	for _e, _n, d, op, uom, qty, pay_v, paid_v, n in sorted(rows, key=lambda r: (str(r[2]), r[3])):
		target, t_uom, is_over = resolve_target(defaults, overrides, employee, op)
		met = _met(qty, target, uom, t_uom)
		daily.append({"date": str(d), "operation": op, "operation_name": (defaults.get(op) or {}).get("name") or op,
			"uom": uom, "qty": flt(qty), "target": target or None if met is not None else None, "met": met})
		o = ops.setdefault((op, uom), {
			"operation": op, "operation_name": (defaults.get(op) or {}).get("name") or op, "uom": uom,
			"qty": 0.0, "days": set(), "pay": 0.0, "paid": 0.0, "target": target or None,
			"target_uom": t_uom if target else None, "override": is_over, "target_days": 0, "met_days": 0, "entries": 0,
		})
		o["qty"] += flt(qty)
		o["days"].add(str(d))
		o["pay"] += flt(pay_v)
		o["paid"] += flt(paid_v)
		o["entries"] += n
		if met is not None:
			o["target_days"] += 1
			o["met_days"] += 1 if met else 0
	by_operation = []
	for o in ops.values():
		days = len(o["days"])
		by_operation.append({
			"operation": o["operation"], "operation_name": o["operation_name"], "uom": o["uom"],
			"qty": round(o["qty"], 4), "days": days, "avg_per_day": round(o["qty"] / days, 2) if days else None,
			"target": o["target"], "target_uom": o["target_uom"], "override": o["override"],
			"target_days": o["target_days"], "met_days": o["met_days"],
			"hit_rate": _rate(o["met_days"], o["target_days"]),
			"avg_vs_target": round(o["qty"] / days / o["target"] * 100, 1) if days and o["target"] and o["target_days"] else None,
			"pay_value": _money(o["pay"], pay), "unpaid_value": _money(o["pay"] - o["paid"], pay), "entries": o["entries"],
		})
	by_operation.sort(key=lambda r: -r["qty"])

	recent = frappe.get_all(
		"Casual Labour Work",
		filters={"crop": crop, "employee": employee, "docstatus": 1, "work_date": ("between", [frm, to])},
		fields=["name", "employee", "work_date", "unit", "operation", "qty", "uom", "pay_value", "paid", "paid_on", "payroll_reference"],
		order_by="work_date desc, creation desc", limit=25,
	)
	annotate_work(recent)
	op_names = {k: v["name"] for k, v in operation_defaults({r["operation"] for r in recent}).items()}
	for r in recent:
		r["operation_name"] = op_names.get(r["operation"], r["operation"])
		r["paid"] = r["paid"] or "Unpaid"
		if not pay:
			r["pay_value"] = None
	return {
		"employee": employee, "employee_name": emp.employee_name, "department": emp.department,
		"designation": emp.designation, "image": emp.image,
		"on_roster": bool(roster), "active": bool(roster.active) if roster else None,
		"supervisor": roster.supervisor if roster else None, "supervisor_name": roster.supervisor_name if roster else None,
		"crew": roster.crew if roster else None,
		"kpis": {
			"days_worked": len(p["dates"]) if p else 0, "entries": p["entries"] if p else 0,
			"qty_by_uom": analytics.merge_uoms(p["uoms"]) if p else [],
			"target_days": p["target_days"] if p else 0, "met_days": p["met_days"] if p else 0,
			"hit_rate": _rate(p["met_days"], p["target_days"]) if p else None,
			"avg_vs_target": round(sum(p["ratios"]) / len(p["ratios"]) * 100, 1) if p and p["ratios"] else None,
			"pay_value": _money(p["pay"], pay) if p else None,
			"paid_value": _money(p["paid"], pay) if p else None,
			"unpaid_value": _money(p["pay"] - p["paid"], pay) if p else None,
		},
		"by_operation": by_operation, "daily": daily, "recent": recent,
		"pending_entries": frappe.db.count("Casual Labour Work",
			{"crop": crop, "employee": employee, "docstatus": 0, "approval_status": "Pending"}),
		"targets": [
			{"operation": op, "operation_name": (operation_defaults([op]).get(op) or {}).get("name") or op, **v}
			for op, v in (person_overrides([employee]).get(employee) or {}).items()
		],
	}


# -- roster management -----------------------------------------------------------


def candidate_employees(search="", department="", designation="", limit=200):
	"""Active employees not yet on the roster, newest filters first (for the picker)."""
	filters = {"status": "Active"}
	if department:
		filters["department"] = department
	if designation:
		filters["designation"] = designation
	or_filters = None
	if search:
		like = f"%{search}%"
		or_filters = {"employee_name": ("like", like), "name": ("like", like)}
	have = set(frappe.get_all("Casual Labourer", pluck="name"))
	rows = frappe.get_all("Employee", filters=filters, or_filters=or_filters,
		fields=["name", "employee_name", "department", "designation", "image"],
		order_by="employee_name asc", limit=cint(limit) + len(have))
	return [r for r in rows if r.name not in have][: cint(limit)]


def employee_filter_options():
	return {
		"departments": frappe.get_all("Department", filters={"disabled": 0}, pluck="name", order_by="name asc"),
		"designations": frappe.get_all("Designation", pluck="name", order_by="name asc"),
	}


def add_labourers(employees, supervisor=None, crew=None) -> dict:
	added, skipped = [], []
	for emp in dict.fromkeys(employees or []):
		if frappe.db.exists("Casual Labourer", emp):
			skipped.append(emp)
			continue
		if not frappe.db.exists("Employee", emp):
			frappe.throw(_("Employee {0} not found").format(emp), frappe.ValidationError)
		frappe.get_doc({"doctype": "Casual Labourer", "employee": emp, "active": 1,
			"supervisor": supervisor or None, "crew": crew or None}).insert()
		added.append(emp)
	return {"added": added, "skipped": skipped}


def save_labourer(employee, active=None, supervisor=None, crew=None, targets=None, fields=()) -> dict:
	"""Update the roster row. Only the keys named in ``fields`` change (so an omitted supervisor is kept)."""
	doc = frappe.get_doc("Casual Labourer", employee)
	if "active" in fields:
		doc.active = cint(active)
	if "supervisor" in fields:
		doc.supervisor = supervisor or None
	if "crew" in fields:
		doc.crew = crew or None
	if "targets" in fields:
		doc.set("targets", [])
		for t in targets or []:
			doc.append("targets", {"operation": t.get("operation"), "daily_target": flt(t.get("daily_target")),
				"uom": t.get("uom") or None})
	doc.save()
	return {"name": doc.name}


def remove_labourer(employee) -> dict:
	"""Delete a roster row; one with work history is made inactive instead."""
	if frappe.db.exists("Casual Labour Work", {"employee": employee}):
		doc = frappe.get_doc("Casual Labourer", employee)
		doc.active = 0
		doc.save()
		return {"removed": False, "deactivated": True}
	frappe.delete_doc("Casual Labourer", employee)
	return {"removed": True, "deactivated": False}


# -- pickers (crew entry on the web and mobile) -------------------------------------


def pickable_people(search="", limit=0) -> list:
	"""Who can be keyed on a task: active roster labourers, plus employees designated "Casual Labourer"
	who are not on the roster at all (so nothing is lost before the roster is filled). Each carries
	``targets``: {operation: {"target", "uom"}} per-person daily target overrides."""
	emp_filters = {"status": "Active"}
	or_filters = {"employee_name": ("like", f"%{search}%"), "name": ("like", f"%{search}%")} if search else None
	roster = frappe.get_all("Casual Labourer", fields=["employee", "active"])
	active = [r.employee for r in roster if r.active]
	known = [r.employee for r in roster]
	rows = frappe.get_all("Employee", filters={**emp_filters, "name": ("in", active or ["\0"])},
		or_filters=or_filters, fields=["name", "employee_name", "image"], order_by="employee_name asc")
	extra_filters = {**emp_filters, "designation": "Casual Labourer"}
	if known:
		extra_filters["name"] = ("not in", known)
	rows += frappe.get_all("Employee", filters=extra_filters, or_filters=or_filters,
		fields=["name", "employee_name", "image"], order_by="employee_name asc")
	rows.sort(key=lambda r: (r.employee_name or "").lower())
	if cint(limit):
		rows = rows[: cint(limit)]
	over = person_overrides([r.name for r in rows])
	for r in rows:
		r["targets"] = over.get(r.name, {})
	return rows


def attach_operation_targets(rows):
	"""Add daily_target / target_uom (the operation's default) to rows that carry an ``operation``."""
	defaults = operation_defaults({r.get("operation") for r in rows if r.get("operation")})
	for r in rows:
		d = defaults.get(r.get("operation")) or {}
		r["daily_target"] = d.get("target") or None
		r["target_uom"] = d.get("uom") if d.get("target") else None
