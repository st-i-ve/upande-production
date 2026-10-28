"""Desk API for break-even. Same envelope as api.production: data or {"error": msg}."""

import frappe

from upande_production.api.envelope import run
from upande_production.production.logic import breakeven
from upande_production.production.logic.settings import can_see_pay


@frappe.whitelist(methods=["POST"])
@run
def crop_breakeven(crop, farm=None):
	return breakeven.crop(crop, farm or None, can_see_pay())
