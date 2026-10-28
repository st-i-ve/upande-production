"""Mobile (field capture) API. Payload via request JSON, result in frappe.response['data']."""
import frappe
from frappe.utils import cint, today

from upande_production.production.logic import work
from upande_production.production.logic.settings import can_see_pay
from upande_production.production.logic.weeks import iso_of, iso_week_bounds

TASK_FIELDS = [
	"name", "unit", "cycle", "operation", "operation_name", "planned_qty", "done_qty", "uom",
	"rate", "due_date", "supervisor", "status", "deviation", "note",
]


def _payload() -> dict:
	return frappe.request.get_json() or {}


def _s(data, key) -> str:
	return str(data.get(key) or "").strip()


def _fail(msg: str, exc: Exception | None = None):
	if exc is not None:
		frappe.db.rollback()
		frappe.log_error(f"{msg}: {exc}")
		frappe.response["data"] = {"error": str(exc)}
	else:
		frappe.response["data"] = {"error": msg}


def _denied(*checks) -> bool:
	"""checks are (doctype, ptype) pairs. On refusal sets the error response and returns True."""
	for doctype, ptype in checks:
		if not frappe.has_permission(doctype, ptype):
			_fail("You do not have permission to do this.")
			return True
	return False


def _strip_pay(rows, *keys):
	if can_see_pay():
		return rows
	for r in rows if isinstance(rows, list) else [rows]:
		for k in keys:
			if k in r:
				r[k] = None
	return rows


def _require(data, *keys) -> str | None:
	for k in keys:
		if not data.get(k) or (isinstance(data.get(k), str) and not data[k].strip()):
			return f"{k.replace('_', ' ').capitalize()} is required."
	return None


def _run(name, fn):
	try:
		frappe.response["data"] = fn()
	except frappe.ValidationError as e:
		frappe.db.rollback()
		frappe.response["data"] = {"error": frappe.utils.strip_html(str(e))}
	except Exception as e:
		_fail(name + " error", e)


@frappe.whitelist()
def productionListCrops():
	if _denied(("Production Crop", "read")):
		return
	_run("productionListCrops", lambda: frappe.get_all(
		"Production Crop", filters={"enabled": 1},
		fields=["name", "crop_name", "crop_key", "accent_color", "icon_key", "unit_label",
			"sub_unit_label", "yield_uom"],
		order_by="sort_order asc, crop_name asc",
	))


@frappe.whitelist()
def productionListUnits():
	if _denied(("Production Unit", "read")):
		return
	data = _payload()
	err = _require(data, "crop")
	if err:
		return _fail(err)
	_run("productionListUnits", lambda: frappe.get_all(
		"Production Unit", filters={"crop": _s(data, "crop"), "status": "Active"},
		fields=["name", "unit_name", "unit_type", "farm", "is_group", "parent_production_unit",
			"area_ha", "plant_count"],
		order_by="unit_name asc",
	))


@frappe.whitelist()
def productionGetWeekPlan():
	if _denied(("Production Work Plan", "read")):
		return
	data = _payload()
	err = _require(data, "crop")
	if err:
		return _fail(err)

	def go():
		crop, farm = _s(data, "crop"), _s(data, "farm")
		cur_year, cur_week = iso_of(today())
		year = cint(data.get("year")) or cur_year
		week = cint(data.get("week")) or cur_week
		start, end = iso_week_bounds(year, week)
		filters = {"crop": crop, "plan_year": year, "plan_week": week}
		filters["farm"] = farm if farm else ("in", ["", None])
		name = frappe.db.get_value("Production Work Plan", filters)
		tasks = []
		if name:
			tasks = frappe.get_all(
				"Production Plan Task", filters={"parent": name, "parenttype": "Production Work Plan"},
				fields=TASK_FIELDS, order_by="due_date asc, idx asc",
			)
			_strip_pay(tasks, "rate")
		return {
			"plan": name, "farm": farm or None, "crop": crop, "year": year, "week": week,
			"week_start": str(start), "week_end": str(end), "tasks": tasks,
		}

	_run("productionGetWeekPlan", go)


@frappe.whitelist()
def productionUpdateTask():
	if _denied(("Production Work Plan", "write")):
		return
	data = _payload()
	err = _require(data, "plan", "task", "status")
	if err:
		return _fail(err)
	if _s(data, "status") not in work.STATUSES:
		return _fail("Status must be one of " + ", ".join(work.STATUSES) + ".")

	def go():
		res = work.record_task_work(
			_s(data, "plan"), _s(data, "task"), _s(data, "status"),
			data.get("entries") or [], note=_s(data, "note"),
		)
		frappe.db.commit()
		task = res["task"]
		return {
			"status": "success", "task": _strip_pay({k: task.get(k) for k in TASK_FIELDS}, "rate"),
			"work": res["work"],
			"message": f"{task.get('operation_name') or 'Task'} marked {task.get('status')}.",
		}

	_run("productionUpdateTask", go)


@frappe.whitelist()
def productionRecordUnplannedWork():
	if _denied(("Value Adder Work", "create")):
		return
	data = _payload()
	err = _require(data, "unit", "operation", "entries")
	if err:
		return _fail(err)

	def go():
		names = work.record_unplanned_work(
			_s(data, "unit"), _s(data, "operation"), data.get("entries") or [],
			_s(data, "work_date") or None, _s(data, "note"),
		)
		frappe.db.commit()
		return {"status": "success", "work": names, "message": f"{len(names)} work record(s) saved."}

	_run("productionRecordUnplannedWork", go)


@frappe.whitelist()
def productionRecordHarvest():
	if _denied(("Production Harvest", "create")):
		return
	data = _payload()
	err = _require(data, "unit", "qty")
	if err:
		return _fail(err)
	if float(data.get("qty") or 0) <= 0:
		return _fail("Quantity must be greater than zero.")

	def go():
		unit = _s(data, "unit")
		crop = frappe.db.get_value("Production Unit", unit, "crop")
		uom = _s(data, "uom") or (frappe.db.get_value("Production Crop", crop, "yield_uom") if crop else None)
		doc = frappe.get_doc({
			"doctype": "Production Harvest", "unit": unit, "crop": crop,
			"cycle": _s(data, "cycle") or None, "item": _s(data, "item") or None,
			"qty": float(data.get("qty")), "uom": uom, "grade": _s(data, "grade") or None,
			"harvest_date": _s(data, "harvest_date") or today(),
		})
		doc.insert()
		frappe.db.commit()
		return {"status": "success", "name": doc.name, "value": doc.value, "message": "Harvest recorded."}

	_run("productionRecordHarvest", go)


@frappe.whitelist()
def productionRecordSample():
	if _denied(("Yield Sample", "create")):
		return
	data = _payload()
	err = _require(data, "unit", "sample_basis", "sample_size", "sampled_yield")
	if err:
		return _fail(err)

	def go():
		unit = _s(data, "unit")
		crop = frappe.db.get_value("Production Unit", unit, "crop")
		doc = frappe.get_doc({
			"doctype": "Yield Sample", "unit": unit, "crop": crop,
			"cycle": _s(data, "cycle") or None, "sample_basis": _s(data, "sample_basis"),
			"sample_size": float(data.get("sample_size")),
			"sampled_yield": float(data.get("sampled_yield")),
			"growth_stage": _s(data, "growth_stage") or None,
			"sample_date": _s(data, "sample_date") or today(),
		})
		doc.insert()
		frappe.db.commit()
		return {
			"status": "success", "name": doc.name, "est_unit_yield": doc.est_unit_yield,
			"message": "Sample recorded.",
		}

	_run("productionRecordSample", go)


@frappe.whitelist()
def productionListValueAdders():
	if _denied(("Value Adder Work", "create")):
		return
	def go():
		filters = {"status": "Active", "designation": "Value Adder"}
		return frappe.get_all(
			"Employee", filters=filters, fields=["name", "employee_name"], order_by="employee_name asc"
		)

	_run("productionListValueAdders", go)


@frappe.whitelist()
def productionListOperations():
	if _denied(("Production Operation", "read")):
		return
	data = _payload()
	err = _require(data, "crop")
	if err:
		return _fail(err)
	_run("productionListOperations", lambda: _strip_pay(frappe.get_all(
		"Production Operation", filters={"crop": _s(data, "crop")},
		fields=["name", "operation_name", "category", "work_uom", "default_rate", "is_harvest"],
		order_by="operation_name asc",
	), "default_rate"))
