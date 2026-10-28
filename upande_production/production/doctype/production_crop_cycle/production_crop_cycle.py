# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ProductionCropCycle(Document):
	def validate(self):
		if self.unit:
			self.crop = frappe.db.get_value("Production Unit", self.unit, "crop")
		self.title = f"{self.unit} · {self.item or self.crop}"
