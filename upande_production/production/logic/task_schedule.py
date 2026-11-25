"""Changing, postponing and deleting planned tasks: who may, and when it is refused."""

import frappe
from frappe.utils import getdate
from frappe import _

from upande_production.production.logic.settings import can_reschedule, crop_allowed


def require_reschedule() -> None:
	if not can_reschedule():
		frappe.throw(_("You are not permitted to change or delete planned tasks."), frappe.PermissionError)


def has_work(task_name: str) -> bool:
	"""True when any Casual Labour Work (not cancelled) is recorded against the task."""
	return bool(frappe.db.exists("Casual Labour Work", {"plan_task": task_name, "docstatus": ("<", 2)}))


_NOT_COPIED = ("name", "parent", "parentfield", "parenttype", "idx", "creation", "modified", "owner",
	"modified_by", "docstatus")


def _rules(vals: dict, override_reason, exclude_task=None) -> dict:
	from upande_production.api.production import _task_rules  # lazy: api imports this module

	return _task_rules(vals, override_reason, exclude_task=exclude_task)


def _load(plan: str, task: str):
	doc = frappe.get_doc("Production Work Plan", plan)
	if not crop_allowed(doc.crop):  # the @run gate only sees `crop`, and these endpoints take a plan
		frappe.throw(_("You are not permitted to see this crop."), frappe.PermissionError)
	row = next((r for r in doc.tasks if r.name == task), None)
	if not row:
		frappe.throw(_("Task {0} not found on this plan").format(task), frappe.ValidationError)
	return doc, row


def _renumber(doc) -> None:
	for i, r in enumerate(doc.tasks, 1):
		r.idx = i


def _target_plan(doc, new_date):
	from upande_production.production.logic import plans
	from upande_production.production.logic.weeks import iso_of

	year, week = iso_of(new_date)
	if (year, week) == (doc.plan_year, doc.plan_week):
		return doc
	return plans.get_or_create_plan(doc.crop, doc.farm, year, week)


def _stamp(vals: dict, old_due, reason: str, prev_count: int) -> None:
	vals.update(
		original_due_date=vals.get("original_due_date") or old_due,
		postpone_count=(prev_count or 0) + 1,
		postpone_reason=reason,
		postponed_by=frappe.session.user,
		postponed_on=frappe.utils.now_datetime(),
		deviation="Late",
	)


def move_task(plan: str, task: str, new_date: str, override_reason: str | None = None) -> dict:
	"""Change the day of a task inside its own week."""
	from upande_production.production.logic.weeks import iso_of

	require_reschedule()
	doc, row = _load(plan, task)
	if iso_of(new_date) != (doc.plan_year, doc.plan_week):
		frappe.throw(_("Pick a day in the same week; use Postpone to move it later."), frappe.ValidationError)
	vals = {"due_date": new_date}
	vals.update(_rules({**row.as_dict(), **vals}, override_reason, exclude_task=row.name))
	if not row.original_due_date:
		vals["original_due_date"] = row.due_date
	row.update(vals)
	doc.save()
	return {"plan": doc.name, "task": task, "split": False}


def postpone_task(plan: str, task: str, new_date: str, reason: str, override_reason: str | None = None) -> dict:
	"""Move a task to a later day, in this or a later week; a task with work is split, keeping the work where it is."""
	require_reschedule()
	reason = (reason or "").strip()
	if not reason:
		frappe.throw(_("Give a reason for postponing."), frappe.ValidationError)
	doc, row = _load(plan, task)
	if row.status in ("Done", "Skipped"):
		frappe.throw(_("A {0} task cannot be postponed.").format(row.status), frappe.ValidationError)
	if not row.due_date or getdate(new_date) <= getdate(row.due_date):
		frappe.throw(_("Pick a day after the current due date."), frappe.ValidationError)

	target = _target_plan(doc, new_date)
	split = has_work(task)
	if split:
		remainder = (row.planned_qty or 0) - (row.done_qty or 0) - (row.pending_qty or 0)
		if remainder <= 0:
			frappe.throw(_("Nothing is left to do on this task."), frappe.ValidationError)
		vals = {k: row.get(k) for k in ("unit", "cycle", "operation", "operation_name", "uom", "rate", "supervisor",
			"supervisor_from_plan", "times_per_week", "note", "original_due_date", "postpone_count")}
		vals.update(planned_qty=remainder, status="Open")
		_stamp(vals, row.due_date, reason, row.postpone_count)
		vals["due_date"] = new_date
		vals.update(_rules(vals, override_reason))
		row.status = "Partly Done"
		new = target.append("tasks", vals)
	else:
		vals = {k: row.get(k) for k in row.as_dict() if k not in _NOT_COPIED}
		_stamp(vals, row.due_date, reason, row.postpone_count)
		vals["due_date"] = new_date
		vals.update(_rules(vals, override_reason, exclude_task=row.name))
		if target is doc:
			row.update(vals)
			new = row
		else:
			doc.tasks = [r for r in doc.tasks if r.name != task]
			new = target.append("tasks", vals)
	_renumber(doc)
	doc.save()
	if target is not doc:
		_renumber(target)
		target.save()
		new = target.tasks[-1]
	elif split:
		new = doc.tasks[-1]
	return {"plan": target.name, "task": new.name, "split": split}


def delete_task(plan: str, task: str, reason: str) -> dict:
	"""Remove a task with no work against it, leaving a comment on the plan."""
	require_reschedule()
	reason = (reason or "").strip()
	if not reason:
		frappe.throw(_("Give a reason for deleting."), frappe.ValidationError)
	doc, row = _load(plan, task)
	if has_work(task):
		frappe.throw(_("Work is recorded against this task; mark it Skipped instead."), frappe.ValidationError)
	op_name = row.operation_name or frappe.db.get_value("Field Operation", row.operation, "operation_name") or row.operation
	text = f"Deleted task {op_name} on {row.unit}, due {row.due_date}: {reason}"
	doc.tasks = [r for r in doc.tasks if r.name != task]
	_renumber(doc)
	doc.save()
	doc.add_comment("Comment", text)
	return {"deleted": task}
