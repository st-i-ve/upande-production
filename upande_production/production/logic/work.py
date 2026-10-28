import frappe
from frappe import _
from frappe.utils import now_datetime, today

STATUSES = ("Open", "In Progress", "Done", "Partly Done", "Skipped")


def _insert_vaw(entry, work_date, unit, operation, uom, rate, cycle=None, plan=None, plan_task=None):
	qty = float(entry.get("qty") or 0)
	if qty <= 0:
		frappe.throw(_("Quantity must be greater than zero"), frappe.ValidationError)
	doc = frappe.get_doc({
		"doctype": "Value Adder Work", "work_date": work_date, "employee": entry.get("employee"),
		"plan": plan, "plan_task": plan_task, "unit": unit, "cycle": cycle, "operation": operation,
		"qty": qty, "uom": uom, "hours": entry.get("hours"), "rate": rate,
	})
	doc.insert()
	doc.submit()
	return doc.name


def record_task_work(plan, task, status, entries, note="", work_date=None) -> dict:
	if status not in STATUSES:
		frappe.throw(_("Invalid status {0}").format(status), frappe.ValidationError)
	entries = entries or []
	for e in entries:
		if float(e.get("qty") or 0) <= 0:
			frappe.throw(_("Quantity must be greater than zero"), frappe.ValidationError)
	doc = frappe.get_doc("Production Plan", plan)
	row = next((t for t in doc.tasks if t.name == task), None)
	if not row:
		frappe.throw(_("Task not found on plan {0}").format(plan), frappe.ValidationError)
	work_date = work_date or today()
	names = [
		_insert_vaw(e, work_date, row.unit, row.operation, row.uom, row.rate, row.cycle, plan, row.name)
		for e in entries
	]
	row.done_qty = sum(
		frappe.get_all(
			"Value Adder Work", filters={"plan": plan, "plan_task": row.name, "docstatus": 1}, pluck="qty"
		)
	)
	now = now_datetime()
	if status in ("In Progress", "Done", "Partly Done") and not row.started_at:
		row.started_at = now
	row.completed_at = now if status in ("Done", "Partly Done", "Skipped") else None
	row.status = status
	if note:
		row.note = note
	doc.save()
	row = next(t for t in doc.tasks if t.name == task)
	return {"task": row.as_dict(), "work": names}


def record_unplanned_work(unit, operation, entries, work_date, note="") -> list[str]:
	op = frappe.db.get_value("Production Operation", operation, ["work_uom", "default_rate"], as_dict=True)
	return [
		_insert_vaw(e, work_date or today(), unit, operation, op.work_uom, op.default_rate)
		for e in entries
	]
