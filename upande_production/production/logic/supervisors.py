"""Weekly supervisor <-> block assignment. A supervisor's phone shows the tasks of the blocks assigned to them
that week, because a plan task takes its `supervisor` from the week's assignment for its block."""
import frappe
from frappe import _
from frappe.utils import add_days, getdate

from upande_production.production.logic.units import unit_filter
from upande_production.production.logic.weeks import iso_of, iso_week_bounds

DOCTYPE = "Production Supervisor Assignment"
MANAGER_ROLES = ("Production Manager", "Avocado Production Manager", "System Manager")
SUPERVISOR_ROLES = ("Production Supervisor",) + MANAGER_ROLES
FIELDS = ["name", "unit", "supervisor", "supervisor_name", "user", "farm", "crop", "notes"]


def can_manage(user: str | None = None) -> bool:
	user = user or frappe.session.user
	return user == "Administrator" or bool(set(MANAGER_ROLES) & set(frappe.get_roles(user)))


def previous_week(year: int, week: int) -> tuple[int, int]:
	return iso_of(add_days(iso_week_bounds(year, week)[0], -7))


def week_units(crop: str, farm: str | None) -> list[dict]:
	"""The farm's blocks of the crop that can be assigned: active, and not a group (pivot)."""
	filters = {"crop": crop, "status": ("!=", "Retired"), "is_group": 0}
	if farm:
		filters["farm"] = farm
	return frappe.get_all("Production Unit", filters=filters, fields=["name", "unit_name", "area_ha", "farm"], order_by="name asc")


def assignments(crop, year, week, farm=None, units=None) -> list[dict]:
	filters = {"crop": crop, "plan_year": int(year), "plan_week": int(week)}
	if farm:
		filters["farm"] = farm
	if units is not None:
		filters["unit"] = ("in", list(units) or [""])
	return frappe.get_all(DOCTYPE, filters=filters, fields=FIELDS, order_by="unit asc")


SUPERVISOR_FIELDS = ["name", "employee_name", "user", "image", "phone", "farm", "active"]


def supervisor_options(crop=None, extra=()) -> list[dict]:
	"""The supervisor dropdown: active Production Supervisors (for `crop` when given; a supervisor with no
	sections listed serves every crop), plus any `extra` employees already assigned so old records still show.
	Every row's `name` is the Employee id, which is what gets stored."""
	filters = {"active": 1}
	rows = frappe.get_all("Production Supervisor", filters=filters, fields=SUPERVISOR_FIELDS, order_by="employee_name asc")
	if crop:
		scoped = {}
		for r in frappe.get_all("Production Supervisor Crop", filters={"parenttype": "Production Supervisor"},
				fields=["parent", "crop"]):
			scoped.setdefault(r.parent, set()).add(r.crop)
		rows = [r for r in rows if not scoped.get(r.name) or crop in scoped[r.name]]
	have = {r.name for r in rows}
	missing = [e for e in dict.fromkeys(extra or []) if e and e not in have]
	if missing:
		rows += frappe.get_all("Production Supervisor", filters={"name": ("in", missing)},
			fields=SUPERVISOR_FIELDS, order_by="employee_name asc")
		have = {r.name for r in rows}
		rows += frappe.get_all("Employee", filters={"name": ("in", [e for e in missing if e not in have])},
			fields=["name", "employee_name", "user_id as user", "image", "cell_number as phone"])
		for r in rows:
			r.setdefault("active", 0)
	for r in rows:
		r["status"] = "Active" if r.get("active") else "Inactive"
	return rows


def candidates(extra=()) -> list[dict]:
	"""Active Production Supervisors, plus any `extra` employees already assigned."""
	return supervisor_options(extra=extra)


def leave_warnings(rows, year, week) -> list[dict]:
	"""Approved leave that overlaps the week, for the employees being assigned (a warning, never a block)."""
	start, end = iso_week_bounds(year, week)
	emps = {r["supervisor"] for r in rows}
	if not emps or not frappe.db.exists("DocType", "Leave Application"):
		return []
	leaves = frappe.get_all(
		"Leave Application",
		filters={"employee": ("in", list(emps)), "status": "Approved", "docstatus": 1,
			"from_date": ("<=", end), "to_date": (">=", start)},
		fields=["employee", "employee_name", "from_date", "to_date"],
	)
	by_emp = {lv.employee: lv for lv in leaves}
	out = []
	for r in rows:
		lv = by_emp.get(r["supervisor"])
		if lv:
			out.append({
				"unit": r["unit"], "supervisor": lv.employee, "supervisor_name": lv.employee_name,
				"message": _("{0} is on approved leave from {1} to {2}.").format(
					lv.employee_name or lv.employee, lv.from_date, lv.to_date),
			})
	return out


def get_week(crop, farm, year, week) -> dict:
	year, week = int(year), int(week)
	farm = farm or None
	cur = assignments(crop, year, week, farm)
	prev_y, prev_w = previous_week(year, week)
	prev = assignments(crop, prev_y, prev_w, farm)
	start, end = iso_week_bounds(year, week)
	return {
		"week_start": start, "week_end": end, "can_edit": can_manage(),
		"units": week_units(crop, farm),
		"supervisors": candidates({r["supervisor"] for r in cur}),
		"assignments": cur, "last_week": prev, "last_week_label": {"year": prev_y, "week": prev_w},
		"warnings": leave_warnings(cur, year, week),
	}


def save_week(crop, farm, year, week, rows) -> dict:
	"""Replace the week's assignments for the farm's blocks of the crop with `rows` ([{unit, supervisor}])."""
	if not can_manage():
		frappe.throw(_("Only a manager can assign supervisors."), frappe.PermissionError)
	year, week, farm = int(year), int(week), farm or None
	iso_week_bounds(year, week)
	allowed = {u.name for u in week_units(crop, farm)}
	wanted = {}
	for r in rows or []:
		unit, sup = (r.get("unit") or "").strip(), (r.get("supervisor") or "").strip()
		if not unit or not sup:
			continue
		if unit in wanted:
			frappe.throw(_("{0} is listed twice.").format(unit), frappe.ValidationError)
		if unit not in allowed:
			frappe.throw(_("{0} is not a block of this crop and farm.").format(unit), frappe.ValidationError)
		if not frappe.db.exists("Employee", sup):
			frappe.throw(_("Unknown employee {0}.").format(sup), frappe.ValidationError)
		wanted[unit] = sup
	existing = {a.unit: a for a in assignments(crop, year, week, units=allowed)}
	touched = set()
	for unit, a in existing.items():
		if unit not in wanted:
			frappe.delete_doc(DOCTYPE, a.name, ignore_permissions=True)
			touched.add(unit)
		elif a.supervisor != wanted[unit]:
			doc = frappe.get_doc(DOCTYPE, a.name)
			doc.supervisor = wanted[unit]
			doc.save(ignore_permissions=True)
			touched.add(unit)
	for unit, sup in wanted.items():
		if unit not in existing:
			frappe.get_doc({"doctype": DOCTYPE, "crop": crop, "farm": farm or frappe.db.get_value("Production Unit", unit, "farm"),
				"unit": unit, "supervisor": sup, "plan_year": year, "plan_week": week}).insert(ignore_permissions=True)
			touched.add(unit)
	updated = refresh_plan_tasks(crop, farm, year, week)
	return {"saved": len(wanted), "tasks_updated": updated,
		"warnings": leave_warnings([{"unit": u, "supervisor": s} for u, s in wanted.items()], year, week)}


def copy_week(crop, farm, year, week) -> dict:
	"""Copy the previous week's assignments into this week when this week has none."""
	if not can_manage():
		frappe.throw(_("Only a manager can assign supervisors."), frappe.PermissionError)
	year, week, farm = int(year), int(week), farm or None
	allowed = {u.name for u in week_units(crop, farm)}
	if assignments(crop, year, week, units=allowed):
		frappe.throw(_("This week already has supervisors assigned; clear them before copying."), frappe.ValidationError)
	py, pw = previous_week(year, week)
	prev = assignments(crop, py, pw, units=allowed)
	if not prev:
		frappe.throw(_("Last week has no supervisors assigned."), frappe.ValidationError)
	res = save_week(crop, farm, year, week, [{"unit": a.unit, "supervisor": a.supervisor} for a in prev])
	res["copied"] = len(prev)
	return res


# -- tasks follow the mapping -------------------------------------------------


def fill_plan_tasks(plan) -> int:
	"""Fill `supervisor` on the plan's tasks from the week's assignment. A task with no supervisor, or one the
	mapping set earlier (supervisor_from_plan), follows the mapping; a supervisor a manager set by hand stays.
	Returns the number of tasks changed."""
	by_unit = {a.unit: a.supervisor for a in assignments(plan.crop, plan.plan_year, plan.plan_week)}
	changed = 0
	for t in plan.tasks:
		if t.supervisor and not t.supervisor_from_plan:
			continue
		want = by_unit.get(t.unit)
		if want:
			if t.supervisor != want or not t.supervisor_from_plan:
				t.supervisor, t.supervisor_from_plan = want, 1
				changed += 1
		elif t.supervisor_from_plan:
			t.supervisor, t.supervisor_from_plan = None, 0
			changed += 1
	return changed


def refresh_plan_tasks(crop, farm, year, week) -> int:
	"""The supervisor plan of a week changed: bring that week's plan tasks in line."""
	filters = {"crop": crop, "plan_year": int(year), "plan_week": int(week)}
	filters["farm"] = farm if farm else ("in", ["", None])
	total = 0
	for name in frappe.get_all("Production Work Plan", filters=filters, pluck="name"):
		plan = frappe.get_doc("Production Work Plan", name)
		n = fill_plan_tasks(plan)
		if n:
			plan.save(ignore_permissions=True)
			total += n
	return total


# -- the phone ----------------------------------------------------------------


def my_assignments(employee, crop, year, week, farm=None) -> dict:
	"""The blocks an employee supervises in a week, for the top of the phone's Plan tab."""
	units = []
	if employee:
		rows = [a for a in assignments(crop, year, week, farm) if a.supervisor == employee]
		names = {u.name: u.unit_name for u in week_units(crop, farm)}
		units = [{"unit": a.unit, "unit_name": names.get(a.unit) or a.unit} for a in rows]
	return {"employee": employee, "year": int(year), "week": int(week), "units": units}
