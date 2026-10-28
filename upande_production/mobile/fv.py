"""Mobile (field capture) API for the Fruits & Vegetables logs. Payload via request JSON,
result in frappe.response['data'] (same style as mobile/api.py)."""
import frappe
from frappe.utils import add_days, today

from upande_production.api import fv
from upande_production.mobile.api import _denied, _fail, _payload, _require, _run, _s


@frappe.whitelist()
def productionListPivots():
	if _denied(("Production Unit", "read")):
		return
	_run("productionListPivots", lambda: {
		"pivots": fv.pivot_tree(), "faults": ["None", "Tower misalignment", "Pressure drop", "Power", "Stuck"],
		"directions": ["Forward", "Reverse"],
	})


@frappe.whitelist()
def productionListIrrigation():
	if _denied(("Pivot Irrigation Run", "read")):
		return
	data = _payload()
	filters = {"start_time": (">=", f"{_s(data, 'from_date') or add_days(today(), -14)} 00:00:00")}
	if _s(data, "pivot"):
		filters["unit"] = _s(data, "pivot")
	_run("productionListIrrigation", lambda: frappe.get_all(
		"Pivot Irrigation Run", filters=filters,
		fields=["name", "unit", "start_time", "end_time", "hours", "depth_mm", "fault", "direction", "percent_timer"],
		order_by="start_time desc", limit_page_length=100,
	))


@frappe.whitelist()
def productionRecordIrrigation():
	if _denied(("Pivot Irrigation Run", "create")):
		return
	data = _payload()
	err = _require(data, "unit", "start_time", "end_time", "depth_mm")
	if err:
		return _fail(err)

	def go():
		doc = fv.build_run(data)
		doc.insert()
		frappe.db.commit()
		return {"status": "success", "name": doc.name, "hours": doc.hours, "message": "Irrigation run recorded."}

	_run("productionRecordIrrigation", go)


@frappe.whitelist()
def productionListGradingBlocks():
	if _denied(("Harvest Grading Log", "read")):
		return
	_run("productionListGradingBlocks", lambda: {
		"blocks": fv._grading_units(), "reasons": ["Undersize", "Greening", "Rot", "Mechanical damage", "Pest damage"],
		"default_grades": ["Class 1", "Class 2", "Ware", "Seed", "Chats"],
	})


@frappe.whitelist()
def productionRecordGrading():
	if _denied(("Harvest Grading Log", "create")):
		return
	data = _payload()
	err = _require(data, "unit", "received_kg")
	if err:
		return _fail(err)
	data.setdefault("grading_date", today())

	def go():
		doc = fv.build_grading(data)
		doc.insert()
		frappe.db.commit()
		return {"status": "success", "name": doc.name, "graded_kg": doc.graded_kg, "message": "Grading recorded."}

	_run("productionRecordGrading", go)
