# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe.utils.nestedset import NestedSet

from upande_production.production.logic.units import close_open_work, ensure_unit_cost_center


class ProductionUnit(NestedSet):
	nsm_parent_field = "parent_production_unit"

	def after_insert(self):
		self._ensure_cc()

	def on_update(self):
		super().on_update()
		if not self.cost_center:
			self._ensure_cc()
		if self.status == "Retired" and (self.flags.get("retired_now") or self.has_value_changed("status")):
			close_open_work(self.name)

	def _ensure_cc(self):
		if getattr(self.flags, "in_cc_sync", False):
			return
		self.flags.in_cc_sync = True
		try:
			ensure_unit_cost_center(self)
		finally:
			self.flags.in_cc_sync = False
