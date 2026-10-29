"""Desk API for the block cost breakdown. Same envelope as api.production: data or {"error": msg}."""

import frappe

from upande_production.api.envelope import run
from upande_production.production.logic import blockcost
from upande_production.production.logic.settings import can_see_pay


@frappe.whitelist(methods=["POST"])
@run
def block_breakdown(unit, from_date=None, to_date=None):
	frappe.has_permission("Production Unit", "read", throw=True)
	return blockcost.breakdown(unit, from_date or None, to_date or None, can_see_pay())
