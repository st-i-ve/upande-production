# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class YieldSample(Document):
	def validate(self):
		if not self.crop:
			self.crop = frappe.db.get_value("Production Unit", self.unit, "crop")
		if not self.unit_population:
			area, plants = frappe.db.get_value("Production Unit", self.unit, ["area_ha", "plant_count"])
			if self.sample_basis == "Square Metres":
				self.unit_population = (area or 0) * 10000
			else:
				self.unit_population = plants or 0
		size = float(self.sample_size or 0)
		self.est_unit_yield = (
			float(self.sampled_yield or 0) / size * float(self.unit_population or 0) if size else 0
		)
