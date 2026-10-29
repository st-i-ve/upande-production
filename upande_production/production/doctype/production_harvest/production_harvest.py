# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate

from upande_production.production.logic.harvest import valuation_rate


class ProductionHarvest(Document):
	def validate(self):
		if not self.crop:
			self.crop = frappe.db.get_value("Production Unit", self.unit, "crop")
		if not self.price_per_uom:
			self.price_per_uom = valuation_rate(self.item, self.crop)
		self.value = (self.qty or 0) * (self.price_per_uom or 0)

	def on_update(self):
		if not self.cycle:
			return
		cur = frappe.db.get_value("Production Crop Cycle", self.cycle, "actual_harvest_start")
		if not cur or getdate(cur) > getdate(self.harvest_date):
			cycle = frappe.get_doc("Production Crop Cycle", self.cycle)
			cycle.actual_harvest_start = self.harvest_date
			cycle.flags.ignore_permissions = True
			cycle.save()
