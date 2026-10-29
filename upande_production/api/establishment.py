"""Desk API for capital / setup costs and opening balances. Same envelope as api.production."""

import frappe
from frappe import _

from upande_production.api.envelope import as_dict, run
from upande_production.production.logic import establishment as logic
from upande_production.production.logic.settings import can_see_pay, is_manager


def _manage():
	if not is_manager():
		frappe.throw(_("Only a manager can change establishment costs."), frappe.PermissionError)


@frappe.whitelist(methods=["POST"])
@run
def list_costs(crop, farm=None):
	frappe.has_permission("Block Establishment Cost", "read", throw=True)
	return logic.list_costs(crop, farm or None, can_see_pay())


@frappe.whitelist(methods=["POST"])
@run
def save_cost(data):
	_manage()
	return logic.save_cost(as_dict(data))


@frappe.whitelist(methods=["POST"])
@run
def cancel_cost(name):
	_manage()
	frappe.get_doc("Block Establishment Cost", name).cancel()
	return {"ok": True}


@frappe.whitelist(methods=["POST"])
@run
def capital_activities(crop):
	frappe.has_permission("Block Establishment Cost", "read", throw=True)
	return {"rows": logic.capital_activities(crop)}


@frappe.whitelist(methods=["POST"])
@run
def list_opening_balances(crop):
	if not can_see_pay():
		frappe.throw(_("Opening balances include pay; ask a manager."), frappe.PermissionError)
	return logic.list_opening_balances(crop)


@frappe.whitelist(methods=["POST"])
@run
def save_opening_balance(data):
	_manage()
	return logic.save_opening_balance(as_dict(data))
