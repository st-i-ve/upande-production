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
CATEGORIES = ("", "Spraying", "Weeding", "Fertilising", "Irrigation", "Harvesting", "Pruning", "Feeding", "Mulching", "Other")
FIELDS = ["name", "unit", "category", "supervisor", "supervisor_name", "user", "farm", "crop", "notes"]


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
	return frappe.get_all(DOCTYPE, filters=filters, fields=FIELDS, order_by="unit asc, creation asc, name asc")


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


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def supervisor_query(doctype, txt, searchfield, start, page_len, filters):
	"""Link search for Employee fields that hold a supervisor: Employees with an active Production Supervisor record."""
	txt = f"%{txt or ''}%"
	return frappe.db.sql(
		"""select ps.employee, ps.employee_name from `tabProduction Supervisor` ps
		where ps.active = 1 and (ps.employee like %(t)s or ps.employee_name like %(t)s)
		order by ps.employee_name limit %(s)s, %(l)s""",
		{"t": txt, "s": int(start), "l": int(page_len)})


def candidates(crop=None, extra=()) -> list[dict]:
	"""Active Production Supervisors for `crop`, plus any `extra` employees already assigned."""
	return supervisor_options(crop, extra)


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
		"supervisors": candidates(crop, {r["supervisor"] for r in cur}),
		"assignments": cur, "last_week": prev, "last_week_label": {"year": prev_y, "week": prev_w},
		"warnings": leave_warnings(cur, year, week),
	}


def save_week(crop, farm, year, week, rows) -> dict:
	"""Replace the week's assignments for the farm's blocks of the crop with `rows`
	([{unit, supervisor, category}], category blank = the block's overseer). Row order is the order of
	sharing: the first listed active supervisor of a (block, category) gets its tasks."""
	if not can_manage():
		frappe.throw(_("Only a manager can assign supervisors."), frappe.PermissionError)
	year, week, farm = int(year), int(week), farm or None
	iso_week_bounds(year, week)
	allowed = {u.name for u in week_units(crop, farm)}
	categories = set(CATEGORIES)
	wanted, seen = {}, set()
	for r in rows or []:
		unit, sup = (r.get("unit") or "").strip(), (r.get("supervisor") or "").strip()
		cat = (r.get("category") or "").strip()
		if not unit or not sup:
			continue
		if cat not in categories:
			frappe.throw(_("Unknown activity {0}.").format(cat), frappe.ValidationError)
		if (unit, cat, sup) in seen:
			frappe.throw(_("{0} lists the same supervisor twice for the same activity.").format(unit), frappe.ValidationError)
		if unit not in allowed:
			frappe.throw(_("{0} is not a block of this crop and farm.").format(unit), frappe.ValidationError)
		if not frappe.db.exists("Employee", sup):
			frappe.throw(_("Unknown employee {0}.").format(sup), frappe.ValidationError)
		if not cat and any(k[0] == unit and not k[1] for k in seen):
			frappe.throw(_("Block {0} already has an overseer this week.").format(unit), frappe.ValidationError)
		seen.add((unit, cat, sup))
		wanted.setdefault((unit, cat), []).append(sup)
	existing = {}
	for a in assignments(crop, year, week, units=allowed):
		existing.setdefault((a.unit, a.category or ""), []).append(a)
	for key, rows_ in existing.items():
		if [a.supervisor for a in rows_] != wanted.get(key):  # changed, removed or reordered: rewrite the group
			for a in rows_:
				frappe.delete_doc(DOCTYPE, a.name, ignore_permissions=True)
	for (unit, cat), sups in wanted.items():
		if [a.supervisor for a in existing.get((unit, cat), [])] == sups:
			continue
		for sup in sups:
			frappe.get_doc({"doctype": DOCTYPE, "crop": crop, "farm": farm or frappe.db.get_value("Production Unit", unit, "farm"),
				"unit": unit, "category": cat, "supervisor": sup, "plan_year": year, "plan_week": week}).insert(ignore_permissions=True)
	updated = refresh_plan_tasks(crop, farm, year, week)
	flat = [{"unit": u, "category": c, "supervisor": s} for (u, c), ss in wanted.items() for s in ss]
	return {"saved": len(flat), "tasks_updated": updated, "warnings": leave_warnings(flat, year, week)}


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
	res = save_week(crop, farm, year, week, [{"unit": a.unit, "category": a.category or "", "supervisor": a.supervisor} for a in prev])
	res["copied"] = len(prev)
	return res


# -- tasks follow the mapping -------------------------------------------------


def active_map(rows) -> dict:
	"""{employee: active} for the supervisors in `rows`, from one query. An employee with no Production
	Supervisor record (assigned before records existed) counts as active."""
	emps = list({r["supervisor"] for r in rows})
	flags = dict(frappe.get_all("Production Supervisor", filters={"name": ("in", emps)}, fields=["name", "active"],
		as_list=True)) if emps else {}
	return {e: bool(flags.get(e, 1)) for e in emps}


def by_key(rows, active=None) -> dict:
	"""{(unit, category): [active supervisors in listed order]}; category "" is the block's overseer. Inactive
	supervisors (per `active`, from active_map; computed when not given) are left out, overseer or sharer."""
	active = active if active is not None else active_map(rows)
	out = {}
	for a in rows:
		if active.get(a["supervisor"], True):
			out.setdefault((a["unit"], a.get("category") or ""), []).append(a["supervisor"])
	return out


def route(task, keyed) -> str | None:
	"""Who a plan task goes to: the first listed active supervisor of its (block, activity), else the block's
	active overseer, else nobody. `task` carries `unit` and `category`; `keyed` is from by_key."""
	cat = task.get("category") or ""
	for key in ((task["unit"], cat),) if cat else ():
		if keyed.get(key):
			return keyed[key][0]
	overseers = keyed.get((task["unit"], ""), [])
	return overseers[0] if overseers else None


def operation_categories(operations) -> dict:
	ops = [o for o in set(operations) if o]
	if not ops:
		return {}
	return dict(frappe.get_all("Field Operation", filters={"name": ("in", ops)}, fields=["name", "category"], as_list=True))


def _visible(employee, tasks, keyed, cats) -> list:
	out = []
	for t in tasks:
		unit, cat = t.get("unit"), cats.get(t.get("operation")) or ""
		sharers = keyed.get((unit, cat), []) if cat else []
		if t.get("supervisor") == employee or employee in sharers:
			out.append(t)
		elif not sharers and employee in keyed.get((unit, ""), []):
			out.append(t)
	return out


def visible_to(employee, tasks, rows) -> list:
	"""Of `tasks` (each with supervisor, unit, operation) of one week, those `employee` should see on the
	phone: their own, those of a (block, activity) they share, and, for a block's active overseer, those of
	activities no active sharer covers. `rows` are the week's assignments."""
	if not employee:
		return []
	return _visible(employee, tasks, by_key(rows), operation_categories(t.get("operation") for t in tasks))


def visible_in_plans(employee, tasks, plan_weeks, crop, farm=None) -> list:
	"""visible_to across several plans at once. `tasks` carry `parent`; `plan_weeks` is {plan: (year, week)}.
	One query each for assignments, supervisor activity and operation categories."""
	if not employee or not tasks:
		return []
	rows = frappe.get_all(
		DOCTYPE, filters={"crop": crop, "plan_year": ("in", list({y for y, _w in plan_weeks.values()})),
			"plan_week": ("in", list({w for _y, w in plan_weeks.values()})), **({"farm": farm} if farm else {})},
		fields=FIELDS + ["plan_year", "plan_week"], order_by="unit asc, creation asc, name asc")
	active = active_map(rows)
	cats = operation_categories(t.get("operation") for t in tasks)
	keyed = {wk: by_key([r for r in rows if (r.plan_year, r.plan_week) == wk], active) for wk in set(plan_weeks.values())}
	by_plan = {}
	for t in tasks:
		by_plan.setdefault(t.parent, []).append(t)
	return [t for plan, ts in by_plan.items() for t in _visible(employee, ts, keyed.get(plan_weeks.get(plan), {}), cats)]


def fill_plan_tasks(plan) -> int:
	"""Fill `supervisor` on the plan's tasks by routing through the week's assignments. A task with no
	supervisor, or one the mapping set earlier (supervisor_from_plan), follows the mapping; a supervisor a
	manager set by hand stays. Returns the number of tasks changed."""
	keyed = by_key(assignments(plan.crop, plan.plan_year, plan.plan_week))
	cats = operation_categories(t.operation for t in plan.tasks)
	changed = 0
	for t in plan.tasks:
		if t.supervisor and not t.supervisor_from_plan:
			continue
		want = route({"unit": t.unit, "category": cats.get(t.operation)}, keyed)
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
	"""The blocks an employee supervises in a week, for the top of the phone's Plan tab: each block once, with
	`categories` (the activities they share there) and `overseer` (they hold the block's blank-category row)."""
	units = {}
	if employee:
		names = {u.name: u.unit_name for u in week_units(crop, farm)}
		for a in assignments(crop, year, week, farm):
			if a.supervisor != employee:
				continue
			u = units.setdefault(a.unit, {"unit": a.unit, "unit_name": names.get(a.unit) or a.unit, "categories": [], "overseer": False})
			if a.category:
				u["categories"].append(a.category)
			else:
				u["overseer"] = True
	return {"employee": employee, "year": int(year), "week": int(week), "units": list(units.values())}
