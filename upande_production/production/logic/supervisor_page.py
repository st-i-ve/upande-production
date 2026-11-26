"""The desk Supervisors page: a card per Production Supervisor with this week's figures, and one supervisor's detail."""
import frappe
from frappe import _
from frappe.utils import getdate, today

from upande_production.production.logic import supervisors
from upande_production.production.logic.settings import crop_allowed
from upande_production.production.logic.weeks import iso_of

PENDING = ("Pending", "Checked")


def _week(year, week) -> tuple[int, int]:
	if year and week:
		return int(year), int(week)
	return iso_of(today())


def _week_assignments(crop, year, week) -> list[dict]:
	filters = {"plan_year": year, "plan_week": week}
	if crop:
		filters["crop"] = crop
	rows = frappe.get_all(supervisors.DOCTYPE, filters=filters, fields=supervisors.FIELDS, order_by="unit asc, creation asc, name asc")
	return [r for r in rows if crop_allowed(r.crop)]


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


def _week_tasks(crop, year, week, employees) -> dict:
	"""{employee: [task rows]} of the week's plans."""
	if not employees:
		return {}
	filters = {"plan_year": year, "plan_week": week}
	if crop:
		filters["crop"] = crop
	plans = frappe.get_all("Production Work Plan", filters=filters, pluck="name")
	if not plans:
		return {}
	rows = frappe.get_all("Work Plan Task", filters={"parent": ("in", plans), "parenttype": "Production Work Plan",
		"supervisor": ("in", list(employees))}, fields=["parent", "supervisor", "status", "deviation", "due_date", "unit", "operation"],
		parent_doctype="Production Work Plan")
	out = {}
	for r in rows:
		out.setdefault(r.supervisor, []).append(r)
	return out


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


def _pending(crop, labourers) -> int:
	if not labourers:
		return 0
	filters = {"employee": ("in", list(labourers)), "docstatus": 0, "approval_status": ("in", PENDING)}
	if crop:
		filters["crop"] = crop
	return frappe.db.count("Casual Labour Work", filters)


def _scoped(crop) -> dict:
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


def list_supervisors(crop=None, year=None, week=None) -> list[dict]:
	year, week = _week(year, week)
	sups = frappe.get_all("Production Supervisor", fields=supervisors.SUPERVISOR_FIELDS, order_by="employee_name asc")
	rows = _week_assignments(crop, year, week)
	held = {}
	for a in rows:
		held.setdefault(a.supervisor, []).append(a)
	if crop:
		scoped = _scoped(crop)
		sups = [s for s in sups if not scoped.get(s.name) or crop in scoped[s.name] or s.name in held]
	names = [s.name for s in sups]
	tasks, crews, images = _week_tasks(crop, year, week, names), _crew(names), _images(names)
	out = []
	for s in sups:
		crew = crews.get(s.name, [])
		pending = _pending(crop, [c.employee for c in crew if c.active])
		out.append(_card(s, _blocks(held.get(s.name, [])), tasks.get(s.name, []), crew, pending, images.get(s.name)))
	return out


def get_supervisor(employee, crop=None, year=None, week=None) -> dict:
	year, week = _week(year, week)
	if not frappe.db.exists("Production Supervisor", employee):
		frappe.throw(_("{0} is not a Production Supervisor.").format(employee), frappe.ValidationError)
	sup = frappe.get_doc("Production Supervisor", employee)
	rows = [a for a in _week_assignments(crop, year, week) if a.supervisor == employee]
	unit_names = dict(frappe.get_all("Production Unit", filters={"name": ("in", [a.unit for a in rows] or [""])},
		fields=["name", "unit_name"], as_list=True))
	tasks = _week_tasks(crop, year, week, [employee]).get(employee, [])
	crew = _crew([employee]).get(employee, [])
	images = _images([c.employee for c in crew] + [employee])
	pending = _pending(crop, [c.employee for c in crew if c.active])
	return {
		"supervisor": {
			"employee": sup.name, "employee_name": sup.employee_name, "image": sup.image or images.get(employee), "phone": sup.phone,
			"user": sup.user, "farm": sup.farm, "active": bool(sup.active), "notes": sup.notes,
			"crops": [c.crop for c in sup.crops],
		},
		"year": year, "week": week, "can_edit": supervisors.can_manage(),
		"blocks": _blocks(rows, unit_names),
		"tasks": _task_counts(tasks),
		"pending": pending,
		"labourers": [{"employee": c.employee, "employee_name": c.employee_name, "image": images.get(c.employee),
			"active": int(bool(c.active)), "crew": c.crew} for c in crew],
	}


def save_supervisor(data) -> dict:
	"""Create or edit a Production Supervisor (keyed by Employee). Photo, phone and user default from the Employee."""
	if not supervisors.can_manage():
		frappe.throw(_("Only a manager can add or edit supervisors."), frappe.PermissionError)
	data = dict(data or {})
	employee = (data.get("employee") or "").strip()
	if not employee or not frappe.db.exists("Employee", employee):
		frappe.throw(_("Choose an employee."), frappe.ValidationError)
	if frappe.db.exists("Production Supervisor", employee):
		doc = frappe.get_doc("Production Supervisor", employee)
	else:
		doc = frappe.get_doc({"doctype": "Production Supervisor", "employee": employee})
	if "active" in data:
		doc.active = 1 if data["active"] in (1, True, "1", "true") else 0
	for f in ("farm", "notes"):
		if f in data:
			doc.set(f, data[f] or None)
	if "crops" in data:
		doc.set("crops", [{"crop": c} for c in dict.fromkeys(data["crops"] or []) if c])
	emp = frappe.db.get_value("Employee", employee, ["image", "cell_number", "user_id"], as_dict=True)
	for f, v in (("image", emp.image), ("phone", emp.cell_number), ("user", emp.user_id)):
		if not doc.get(f):
			doc.set(f, v)
	doc.flags.ignore_permissions = True
	doc.insert() if doc.is_new() else doc.save()
	return {"employee": doc.name, "employee_name": doc.employee_name}
