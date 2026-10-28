# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ProductionHarvest(Document):
	def validate(self):
		if not self.crop:
			self.crop = frappe.db.get_value("Production Unit", self.unit, "crop")
		if not self.price_per_uom:
			filters = {"crop": self.crop, "price_per_uom": (">", 0)}
			if self.item:
				filters["item"] = self.item
			self.price_per_uom = (
				frappe.db.get_value("Buyer Commitment", filters, "price_per_uom", order_by="week_start desc")
				or 0
			)
		self.value = (self.qty or 0) * (self.price_per_uom or 0)
