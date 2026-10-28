# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from upande_production.production.logic.pay import pay_value
from upande_production.production.logic.settings import get_company
from upande_production.production.logic.work import refresh_task_done
from upande_production.production.logic.units import ensure_unit_cost_center


class ValueAdderWork(Document):
	def validate(self):
		if not self.rate:
			self.rate = frappe.db.get_value("Production Operation", self.operation, "default_rate") or 0
		self.pay_value = pay_value(self.qty, self.rate)
		self.crop = frappe.db.get_value("Production Unit", self.unit, "crop")
		if not self.cost_center:
			self.cost_center = ensure_unit_cost_center(self.unit)
		self.company = self.company or get_company()
		self.unplanned = 0 if self.plan_task else 1

	def on_cancel(self):
		refresh_task_done(self.plan, self.plan_task)
