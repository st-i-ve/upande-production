"""Changing, postponing and deleting planned tasks: who may, and when it is refused."""

import frappe
from frappe import _

from upande_production.production.logic.settings import can_reschedule


def require_reschedule() -> None:
	if not can_reschedule():
		frappe.throw(_("You are not permitted to change or delete planned tasks."), frappe.PermissionError)


def has_work(task_name: str) -> bool:
	"""True when any Casual Labour Work (not cancelled) is recorded against the task."""
	return bool(frappe.db.exists("Casual Labour Work", {"plan_task": task_name, "docstatus": ("<", 2)}))
