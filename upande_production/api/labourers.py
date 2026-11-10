"""Desk API for the casual labour roster and its KPIs. Every endpoint returns data or {"error": msg}."""

import frappe

from upande_production.api.envelope import as_dict, run
from upande_production.production.logic import labourers
from upande_production.production.logic.settings import can_see_pay


def _need(doctype, ptype="read"):
	frappe.has_permission(doctype, ptype, throw=True)


@frappe.whitelist(methods=["POST"])
@run
def list_labourers(crop, from_date=None, to_date=None, search="", department="", designation="", active=""):
	_need("Casual Labourer")
	return labourers.labourer_list(crop, from_date, to_date, can_see_pay(), search, department, designation, active)


@frappe.whitelist(methods=["POST"])
@run
def labourer_detail(crop, employee, from_date=None, to_date=None):
	_need("Casual Labourer")
	return labourers.labourer_detail(crop, employee, from_date, to_date, can_see_pay())


@frappe.whitelist(methods=["POST"])
@run
def candidate_employees(search="", department="", designation="", limit=200):
	"""Active employees not on the roster yet, for the picker; also the filter options."""
	_need("Casual Labourer", "create")
	return {"people": labourers.candidate_employees(search, department, designation, limit),
		**labourers.employee_filter_options()}


@frappe.whitelist(methods=["POST"])
@run
def add_labourers(employees, supervisor=None, crew=None):
	_need("Casual Labourer", "create")
	return labourers.add_labourers(as_dict(employees) or [], supervisor, crew)


@frappe.whitelist(methods=["POST"])
@run
def save_labourer(employee, active=None, supervisor=None, crew=None, targets=None):
	"""Update active / supervisor / crew / targets ([{operation, daily_target, uom}]); only keys sent change."""
	_need("Casual Labourer", "write")
	given = {"active": active, "supervisor": supervisor, "crew": crew, "targets": targets}
	sent = tuple(k for k, v in given.items() if v is not None or k in frappe.form_dict)
	rows = as_dict(targets) if targets is not None else []
	return labourers.save_labourer(employee, active, supervisor, crew, rows if isinstance(rows, list) else [], sent)


@frappe.whitelist(methods=["POST"])
@run
def remove_labourer(employee):
	_need("Casual Labourer", "delete")
	return labourers.remove_labourer(employee)
