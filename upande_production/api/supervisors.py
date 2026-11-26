"""Desk API for the Supervisors page. Every endpoint returns data or {"error": msg}."""

import frappe

from upande_production.api.envelope import as_dict, run
from upande_production.production.logic import supervisor_page


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
