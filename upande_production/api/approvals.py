"""Desk API for the approvals page. Same envelope as api.production: data or {"error": msg}."""

from upande_production.api.envelope import as_dict, run
from upande_production.production.logic import approvals as logic

import frappe


@frappe.whitelist(methods=["POST"])
@run
def list_approvals(crop=None, status="Pending", from_date=None, to_date=None, unit=None, operation=None,
		supervisor=None):
	return logic.list_approvals(crop or None, status or "Pending", from_date or None, to_date or None,
		unit or None, operation or None, supervisor or None)


@frappe.whitelist(methods=["POST"])
@run
def approve(names):
	return logic.approve(names)


@frappe.whitelist(methods=["POST"])
@run
def send_back(names, note=""):
	return logic.send_back(names, note)


@frappe.whitelist(methods=["POST"])
@run
def resubmit(names, entries=None):
	return logic.resubmit(names, as_dict(entries) if entries else None)


@frappe.whitelist(methods=["POST"])
@run
def approval_counts():
	return logic.approval_counts()
