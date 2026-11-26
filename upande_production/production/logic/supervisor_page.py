"""The desk Supervisors page: a card per Production Supervisor with this week's figures, and one supervisor's detail."""
import frappe
from frappe import _
from frappe.utils import getdate, today

from upande_production.production.logic import supervisors, task_approval
from upande_production.production.logic.settings import avocado_only_crop_keys, crop_allowed, is_assistant_manager
from upande_production.production.logic.units import unit_filter
from upande_production.production.logic.weeks import iso_of

PENDING = ("Pending", "Checked")


def _week(year, week) -> tuple[int, int]:
	if year and week:
		return int(year), int(week)
	return iso_of(today())


def _need_crop(crop):
	if not crop:
		frappe.throw(_("Choose a crop."), frappe.ValidationError)
	if not crop_allowed(crop):
		frappe.throw(_("You are not permitted to see this crop."), frappe.PermissionError)


def _week_assignments(crop, year, week) -> list[dict]:
	return frappe.get_all(supervisors.DOCTYPE, filters={"crop": crop, "plan_year": year, "plan_week": week},
		fields=supervisors.FIELDS, order_by="unit asc, creation asc, name asc")


def _sees_everyone() -> bool:
	"""Managers and assistant managers see every supervisor's crew and approvals."""
	return supervisors.can_manage() or is_assistant_manager()


def _full(sup) -> bool:
	"""May see this supervisor's crew names and pending approvals: a manager, an assistant manager, or the supervisor themself."""
	return _sees_everyone() or bool(sup.user and sup.user == frappe.session.user)


def _blocks(rows, names=None) -> list[dict]:
	"""One entry per block a supervisor holds: `categories` they share there, `overseer` for the blank-category row."""
	units = {}
	for a in rows:
		u = units.setdefault(a.unit, {"unit": a.unit, "unit_name": (names or {}).get(a.unit) or a.unit, "crop": a.crop,
			"categories": [], "overseer": False})
		if a.category:
			u["categories"].append(a.category)
		else:
			u["overseer"] = True
	return list(units.values())


def _task_counts(rows) -> dict:
	"""done / late (past due and not finished, or flagged Late) / open (the rest still to do); skipped counted apart."""
	today_ = getdate(today())
	out = {"done": 0, "open": 0, "late": 0, "skipped": 0, "total": 0}
	for t in rows:
		out["total"] += 1
		if t.status == "Done":
			out["done"] += 1
		elif t.status == "Skipped":
			out["skipped"] += 1
		elif t.deviation == "Late" or (t.due_date and getdate(t.due_date) < today_):
			out["late"] += 1
		else:
			out["open"] += 1
	return out


class _Week:
	"""The week's assignments and plan tasks, read once; `tasks_of` is what a supervisor sees (own tasks, those of an
	activity they share, and for a block's overseer those no sharer covers)."""

	def __init__(self, crop, year, week):
		self.rows = _week_assignments(crop, year, week)
		self.active = supervisors.active_map(self.rows)
		self.keyed = supervisors.by_key(self.rows, self.active)
		plans = frappe.get_all("Production Work Plan", filters={"crop": crop, "plan_year": year, "plan_week": week}, pluck="name")
		task_filters = unit_filter({"parent": ("in", plans), "parenttype": "Production Work Plan", **task_approval.visible_filter()})
		self.tasks = frappe.get_all("Work Plan Task", filters=task_filters,
			fields=["parent", "supervisor", "status", "deviation", "due_date", "unit", "operation"],
			parent_doctype="Production Work Plan") if plans else []
		self.cats = supervisors.operation_categories(t.operation for t in self.tasks)

	def tasks_of(self, employee) -> list:
		if not self.active.get(employee, True):
			return []
		return supervisors._visible(employee, self.tasks, self.keyed, self.cats)

	def assignments_of(self, employee) -> list:
		"""Only an active supervisor holds blocks."""
		return [a for a in self.rows if a.supervisor == employee] if self.active.get(employee, True) else []


def _crew(employees) -> dict:
	"""{supervisor: [Casual Labourer rows]}, one query."""
	if not employees:
		return {}
	rows = frappe.get_all("Casual Labourer", filters={"supervisor": ("in", list(employees))},
		fields=["employee", "employee_name", "active", "crew", "supervisor"], order_by="employee_name asc")
	out = {}
	for r in rows:
		out.setdefault(r.supervisor, []).append(r)
	return out


def _images(employees) -> dict:
	if not employees:
		return {}
	return dict(frappe.get_all("Employee", filters={"name": ("in", list(employees))}, fields=["name", "image"], as_list=True))


def _pending_by_labourer(crop, labourers) -> dict:
	"""{labourer: entries waiting for approval}, one grouped query."""
	if not labourers:
		return {}
	rows = frappe.get_all("Casual Labour Work", filters={"employee": ("in", list(labourers)), "crop": crop, "docstatus": 0,
		"approval_status": ("in", PENDING)}, fields=["employee", {"COUNT": "name", "as": "n"}], group_by="employee")
	return {r.employee: r.n for r in rows}


def _scoped() -> dict:
	"""{supervisor: set of crops it is limited to}; absent = all crops."""
	out = {}
	for r in frappe.get_all("Production Supervisor Crop", filters={"parenttype": "Production Supervisor"}, fields=["parent", "crop"]):
		out.setdefault(r.parent, set()).add(r.crop)
	return out


def _card(sup, blocks, tasks, crew, pending, image) -> dict:
	return {
		"employee": sup.name, "employee_name": sup.employee_name, "image": sup.image or image, "phone": sup.phone,
		"user": sup.user, "farm": sup.farm, "active": bool(sup.active),
		"kpis": {"blocks": len(blocks), "tasks": _task_counts(tasks), "crew": sum(1 for c in crew if c.active), "pending": pending},
	}


def list_supervisors(crop, year=None, week=None) -> list[dict]:
	_need_crop(crop)
	year, week = _week(year, week)
	sups = frappe.get_all("Production Supervisor", fields=supervisors.SUPERVISOR_FIELDS, order_by="employee_name asc")
	wk = _Week(crop, year, week)
	scoped = _scoped()
	held = {s.name: wk.assignments_of(s.name) for s in sups}
	sups = [s for s in sups if not scoped.get(s.name) or crop in scoped[s.name] or held[s.name]]
	names = [s.name for s in sups]
	crews, images = _crew(names), _images(names)
	allowed = [c.employee for s in sups if _full(s) for c in crews.get(s.name, []) if c.active]
	pending = _pending_by_labourer(crop, allowed)
	out = []
	for s in sups:
		crew = crews.get(s.name, [])
		n = sum(pending.get(c.employee, 0) for c in crew if c.active) if _full(s) else None
		out.append(_card(s, _blocks(held[s.name]), wk.tasks_of(s.name), crew, n, images.get(s.name)))
	return out


def get_supervisor(employee, crop, year=None, week=None) -> dict:
	_need_crop(crop)
	year, week = _week(year, week)
	if not frappe.db.exists("Production Supervisor", employee):
		frappe.throw(_("{0} is not a Production Supervisor.").format(employee), frappe.ValidationError)
	sup = frappe.get_doc("Production Supervisor", employee)
	wk = _Week(crop, year, week)
	rows = wk.assignments_of(employee)
	unit_names = dict(frappe.get_all("Production Unit", filters={"name": ("in", [a.unit for a in rows] or [""])},
		fields=["name", "unit_name"], as_list=True))
	crew = _crew([employee]).get(employee, [])
	full = _full(sup)
	images = _images([c.employee for c in crew] + [employee]) if full else _images([employee])
	pending = None
	if full:
		pending = sum(_pending_by_labourer(crop, [c.employee for c in crew if c.active]).values())
	return {
		"supervisor": {
			"employee": sup.name, "employee_name": sup.employee_name, "image": sup.image or images.get(employee), "phone": sup.phone,
			"user": sup.user, "farm": sup.farm, "active": bool(sup.active), "notes": sup.notes,
			"crops": [c.crop for c in sup.crops],
		},
		"year": year, "week": week, "can_edit": supervisors.can_manage(),
		"blocks": _blocks(rows, unit_names),
		"tasks": _task_counts(wk.tasks_of(employee)),
		"pending": pending,
		"crew_count": sum(1 for c in crew if c.active),
		"crew_hidden": not full,
		"labourers": [{"employee": c.employee, "employee_name": c.employee_name, "image": images.get(c.employee),
			"active": int(bool(c.active)), "crew": c.crew} for c in crew] if full else [],
	}


def save_supervisor(data) -> dict:
	"""Create or edit a Production Supervisor (keyed by Employee). Photo, phone and user default from the Employee."""
	if not supervisors.can_manage():
		frappe.throw(_("Only a manager can add or edit supervisors."), frappe.PermissionError)
	data = dict(data or {})
	employee = (data.get("employee") or "").strip()
	if not employee or not frappe.db.exists("Employee", employee):
		frappe.throw(_("Choose an employee."), frappe.ValidationError)
	if "crops" in data and not isinstance(data["crops"], (list, tuple)):
		frappe.throw(_("Sections must be a list."), frappe.ValidationError)
	is_new = not frappe.db.exists("Production Supervisor", employee)
	if not is_new:
		doc = frappe.get_doc("Production Supervisor", employee)
	else:
		doc = frappe.get_doc({"doctype": "Production Supervisor", "employee": employee})
	was_active = None if is_new else bool(doc.active)
	old_crops = [c.crop for c in doc.crops]
	# a manager limited to some crops may only touch records whose crops are all theirs (no crops = every crop; a new record has no old crops to check)
	new_crops = [c for c in dict.fromkeys(data["crops"]) if c] if "crops" in data else old_crops
	for crops in ((new_crops,) if is_new else (old_crops, new_crops)):
		if (not crops and avocado_only_crop_keys()) or not all(crop_allowed(c) for c in crops):
			frappe.throw(_("You are not permitted to edit a supervisor for these crops."), frappe.PermissionError)
	if "active" in data:
		doc.active = 1 if data["active"] in (1, True, "1", "true") else 0
	if doc.active and frappe.db.get_value("Employee", employee, "status") != "Active":
		frappe.throw(_("{0} is not an active employee; mark the record inactive.").format(employee), frappe.ValidationError)
	for f in ("farm", "notes"):
		if f in data:
			doc.set(f, data[f] or None)
	if "crops" in data:
		doc.set("crops", [{"crop": c} for c in dict.fromkeys(data["crops"]) if c])
	emp = frappe.db.get_value("Employee", employee, ["image", "cell_number", "user_id"], as_dict=True)
	for f, v in (("image", emp.image), ("phone", emp.cell_number), ("user", emp.user_id)):
		if not doc.get(f):
			doc.set(f, v)
	doc.flags.ignore_permissions = True
	doc.insert() if doc.is_new() else doc.save()
	if was_active is not None and was_active != bool(doc.active):
		supervisors.refresh_current_week(new_crops)
	return {"employee": doc.name, "employee_name": doc.employee_name}


def assistants_without_manager() -> list[dict]:
	"""Assistant managers with no manager (reports_to empty or not a manager): the desk flags them. Managers only."""
	if not supervisors.can_manage():
		frappe.throw(_("Only a manager can see this."), frappe.PermissionError)
	from upande_production.production.logic import teams

	return teams.assistants_without_manager()
