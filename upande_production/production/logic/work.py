import frappe
from frappe import _
from frappe.utils import now_datetime, today

from upande_production.production.logic import rules

STATUSES = ("Open", "In Progress", "Done", "Partly Done", "Skipped")


def _insert_vaw(entry, work_date, unit, operation, uom, rate, cycle=None, plan=None, plan_task=None, stamp=None):
	qty = float(entry.get("qty") or 0)
	if qty <= 0:
		frappe.throw(_("Quantity must be greater than zero"), frappe.ValidationError)
	doc = frappe.get_doc({
		"doctype": "Value Adder Work", "work_date": work_date, "employee": entry.get("employee"),
		"plan": plan, "plan_task": plan_task, "unit": unit, "cycle": cycle, "operation": operation,
		"qty": qty, "uom": uom, "hours": entry.get("hours"), "rate": rate,
		"approval_status": "Pending", "submitted_by": frappe.session.user, **(stamp or {}),
	})
	doc.insert()  # stays a draft: it counts only once a manager approves (submits) it
	return doc.name


def submitted_qty(plan, plan_task) -> float:
	return sum(
		frappe.get_all(
			"Value Adder Work", filters={"plan": plan, "plan_task": plan_task, "docstatus": 1}, pluck="qty"
		)
	)


def pending_qty(plan, plan_task) -> float:
	"""Quantity keyed but not yet approved (drafts awaiting review)."""
	return sum(
		frappe.get_all(
			"Value Adder Work",
			filters={"plan": plan, "plan_task": plan_task, "docstatus": 0, "approval_status": "Pending"},
			pluck="qty",
		)
	)


def refresh_task_done(plan, plan_task):
	"""Re-sum a task's approved (submitted) Value Adder Work into done_qty and its pending drafts into
	pending_qty, then save the plan (recomputes deviation)."""
	if not plan or not plan_task or not frappe.db.exists("Production Work Plan", plan):
		return
	doc = frappe.get_doc("Production Work Plan", plan)
	row = next((t for t in doc.tasks if t.name == plan_task), None)
	if not row:
		return
	row.done_qty = submitted_qty(plan, plan_task)
	row.pending_qty = pending_qty(plan, plan_task)
	doc.flags.ignore_permissions = True
	doc.save()


def record_task_work(plan, task, status, entries, note="", work_date=None, override_reason=None) -> dict:
	if status not in STATUSES:
		frappe.throw(_("Invalid status {0}").format(status), frappe.ValidationError)
	entries = entries or []
	for e in entries:
		if float(e.get("qty") or 0) <= 0:
			frappe.throw(_("Quantity must be greater than zero"), frappe.ValidationError)
	doc = frappe.get_doc("Production Work Plan", plan)
	row = next((t for t in doc.tasks if t.name == task), None)
	if not row:
		frappe.throw(_("Task not found on plan {0}").format(plan), frappe.ValidationError)
	if status in ("Done", "Partly Done") and not entries and not frappe.db.exists(
		"Value Adder Work", {"plan": plan, "plan_task": row.name, "docstatus": ("<", 2)}
	):
		# Done with nobody recorded has no quantity and no one to pay (the mobile app asks the same).
		frappe.throw(_("Record who did the work before marking it {0}.").format(_(status)),
			frappe.ValidationError)
	work_date = work_date or today()
	stamp = None
	if entries or status in ("In Progress", "Done", "Partly Done"):
		# Activity rules: Block refuses, Warn needs a reason (one given earlier on the task still stands)
		breaches = rules.check(cycle=row.cycle, unit=row.unit, operation=row.operation, on_date=work_date,
			exclude_task=row.name)
		stamp = rules.enforce(breaches, override_reason or row.get("override_reason"))
		row.rule_status, row.rule_notes, row.override_reason = (
			stamp["rule_status"], stamp["rule_notes"], stamp["override_reason"])
	names = [
		_insert_vaw(e, work_date, row.unit, row.operation, row.uom, row.rate, row.cycle, plan, row.name, stamp)
		for e in entries
	]
	row.done_qty = submitted_qty(plan, row.name)
	row.pending_qty = pending_qty(plan, row.name)
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


def record_unplanned_work(unit, operation, entries, work_date, note="", override_reason=None) -> list[str]:
	work_date = work_date or today()
	stamp = rules.enforce(rules.check(unit=unit, operation=operation, on_date=work_date), override_reason)
	op = frappe.db.get_value("Production Operation", operation, ["work_uom", "default_rate"], as_dict=True)
	return [
		_insert_vaw(e, work_date, unit, operation, op.work_uom, op.default_rate, stamp=stamp)
		for e in entries
	]
