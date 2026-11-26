"""Desk API for the approvals page. Same envelope as api.production: data or {"error": msg}."""

from upande_production.api.envelope import as_dict, run
from upande_production.production.logic import approvals as logic

import frappe


@frappe.whitelist(methods=["POST"])
@run
def list_approvals(crop=None, status="Pending", from_date=None, to_date=None, unit=None, operation=None,
		supervisor=None, queue=None, all_teams=0):
	return logic.list_approvals(crop or None, status or "Pending", from_date or None, to_date or None,
		unit or None, operation or None, supervisor or None, queue or None, all_teams)


@frappe.whitelist(methods=["POST"])
@run
def check(names):
	return logic.check(names)


@frappe.whitelist(methods=["POST"])
@run
def approve(names, unchecked_ok=0, confirm_other_team=0):
	return logic.approve(names, unchecked_ok, confirm_other_team)


@frappe.whitelist(methods=["POST"])
@run
def send_back(names, note="", confirm_other_team=0):
	return logic.send_back(names, note, confirm_other_team)


@frappe.whitelist(methods=["POST"])
@run
def resubmit(names, entries=None, override_reason=None):
	return logic.resubmit(names, as_dict(entries) if entries else None, override_reason or None)


@frappe.whitelist(methods=["POST"])
@run
def approval_counts(all_teams=0):
	return logic.approval_counts(all_teams)
