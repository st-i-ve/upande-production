# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from upande_production.production.logic.weeks import iso_of


class ProductionForecast(Document):
	def validate(self):
		if not self.crop:
			self.crop = frappe.db.get_value("Production Unit", self.unit, "crop")
		total = 0.0
		for row in self.weeks:
			row.iso_year, row.iso_week = iso_of(row.week_start)
			total += float(row.expected_qty or 0)
		self.total_expected = total
