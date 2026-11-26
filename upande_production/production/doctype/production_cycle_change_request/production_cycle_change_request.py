# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from upande_production.production.logic.cycle_requests import LOGIC_FLAG
from upande_production.production.logic.settings import is_manager


def _only_through_logic():
	"""Requests are written only by cycle_requests (so changes, payload, status and reviewer cannot be forged)."""
	if not is_manager() and not frappe.flags.get(LOGIC_FLAG):
		frappe.throw(_("Use Edit cycle to send or change a request."), frappe.PermissionError)


class ProductionCycleChangeRequest(Document):
	def validate(self):
		_only_through_logic()

	def on_trash(self):
		_only_through_logic()
