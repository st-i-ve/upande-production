"""Desk API for the Supervisors page. Every endpoint returns data or {"error": msg}."""

import frappe

from upande_production.api.envelope import as_dict, run
from upande_production.production.logic import people, supervisor_page


def _need(doctype, ptype="read"):
	frappe.has_permission(doctype, ptype, throw=True)


@frappe.whitelist(methods=["POST"])
@run
def list_supervisors(crop=None, year=None, week=None):
	"""A card per Production Supervisor: contact, active flag and this week's figures (blocks, tasks, crew, pending approvals)."""
	_need("Production Supervisor")
	return supervisor_page.list_supervisors(crop or None, year, week)


@frappe.whitelist(methods=["POST"])
@run
def get_supervisor(employee, crop=None, year=None, week=None):
	"""One supervisor: blocks and activities this week, task counts, casual labourers."""
	_need("Production Supervisor")
	return supervisor_page.get_supervisor(employee, crop or None, year, week)


@frappe.whitelist(methods=["POST"])
@run
def save_supervisor(data):
	"""Create or edit a Production Supervisor (employee, active, farm, crops, notes). Managers only."""
	return supervisor_page.save_supervisor(as_dict(data) or {})


@frappe.whitelist()
@run
def assistants_without_manager():
	return supervisor_page.assistants_without_manager()


@frappe.whitelist(methods=["POST"])
@run
def people_supervisors(crop=None, from_date=None, to_date=None):
	"""The Supervisors page: the roster with each supervisor's figures, flags, block shares and weekly strip for the range (default last four weeks)."""
	_need("Production Supervisor")
	return people.supervisor_people(crop or None, from_date or None, to_date or None)


@frappe.whitelist(methods=["POST"])
@run
def employee_options(search="", limit=20):
	"""Active employees for the Add supervisor picker: [{value, label}]. Managers only. Read past HR's user
	permissions on purpose: a manager limited to their own Employee record (self-service) must still pick
	the people they supervise."""
	from upande_production.production.logic import supervisors

	if not supervisors.can_manage():
		frappe.throw(frappe._("Only a manager can add supervisors."), frappe.PermissionError)
	or_filters = None
	search = (search or "").strip()
	if search:
		like = f"%{search}%"
		or_filters = {"employee_name": ("like", like), "name": ("like", like)}
	rows = frappe.get_all("Employee", filters={"status": "Active"}, or_filters=or_filters,
		fields=["name", "employee_name"], order_by="employee_name asc", limit=min(int(limit or 20), 50))
	return [{"value": r.name, "label": f"{r.employee_name} · {r.name}"} for r in rows]
