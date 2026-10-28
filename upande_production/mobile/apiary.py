"""Mobile (field capture) endpoints for the Apiary logs. Same conventions as mobile/api.py:
payload via request JSON, result in frappe.response['data']."""
import frappe
from frappe.utils import add_days, today

from upande_production.api import apiary
from upande_production.mobile.api import _denied, _fail, _payload, _require, _run, _s


@frappe.whitelist()
def apiaryListHiveGroups():
	if _denied((apiary.INSPECTION, "read")):
		return

	def go():
		return {"groups": apiary.hive_groups(), "employees": apiary._employees(),
				"form": apiary.inspection_form(), "today": today()}

	_run("apiaryListHiveGroups", go)


@frappe.whitelist()
def apiaryRecordInspection():
	if _denied((apiary.INSPECTION, "create")):
		return
	data = _payload()
	err = _require(data, "unit", "colonies_inspected")
	if err:
		return _fail(err)

	def go():
		doc = apiary.create_inspection(data)
		frappe.db.commit()
		return {"status": "success", "name": doc.name, "message": "Inspection recorded."}

	_run("apiaryRecordInspection", go)


@frappe.whitelist()
def apiaryRecordHarvest():
	if _denied((apiary.HARVEST, "create")):
		return
	data = _payload()
	err = _require(data, "unit", "honey_kg")
	if err:
		return _fail(err)

	def go():
		doc = apiary.create_harvest(data)
		frappe.db.commit()
		return {"status": "success", "name": doc.name, "message": "Honey harvest recorded."}

	_run("apiaryRecordHarvest", go)


@frappe.whitelist()
def apiaryRecentLogs():
	"""The last 30 days of both logs, for the supervisor's own review on the phone."""
	if _denied((apiary.INSPECTION, "read"), (apiary.HARVEST, "read")):
		return
	data = _payload()

	def go():
		start, end = add_days(today(), -30), today()
		unit = _s(data, "unit") or None
		insp = apiary.hive_inspections(start, end, unit)
		hon = apiary.honey_harvest(start, end, unit)
		if "error" in insp:
			raise frappe.ValidationError(insp["error"])
		if "error" in hon:
			raise frappe.ValidationError(hon["error"])
		return {"inspections": insp["rows"], "harvests": hon["rows"]}

	_run("apiaryRecentLogs", go)
