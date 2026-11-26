"""Awaiting tasks: an assistant manager's plan rows wait for a manager to forward them to the supervisors."""

import frappe
from frappe import _
from frappe.utils import now_datetime

from upande_production.production.logic import settings

REAWAIT_FIELDS = ("unit", "cycle", "operation", "planned_qty", "rate", "uom")


def visible_filter() -> dict:
	"""Filter for task queries: supervisors do not see awaiting tasks while the step is on."""
	if settings.assistant_step_on() and not settings.is_manager() and not settings.is_assistant_manager():
		return {"awaiting_approval": 0}
	return {}


def refuse_if_awaiting(row):
	if settings.assistant_step_on() and row.get("awaiting_approval"):
		frappe.throw(_("This task is waiting for a manager's approval."), frappe.ValidationError)


def forward(plan: str, tasks: list | None = None) -> dict:
	"""Managers forward all awaiting tasks of a plan (or the named ones): clear the flag, stamp who and when."""
	if not settings.is_manager():
		frappe.throw(_("Only a manager can forward tasks."), frappe.PermissionError)
	doc = frappe.get_doc("Production Work Plan", plan)
	wanted = set(tasks) if tasks else None
	out = []
	for r in doc.tasks:
		if r.awaiting_approval and (wanted is None or r.name in wanted):
			r.awaiting_approval = 0
			r.forwarded_by = frappe.session.user
			r.forwarded_on = now_datetime()
			out.append(r.name)
	if out:
		doc.save()  # the plan save runs the Work Management plan-row sync for the newly released rows
	return {"forwarded": out}
