# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from upande_production.production.logic.weeks import iso_of


class BuyerCommitment(Document):
	def validate(self):
		self.iso_year, self.iso_week = iso_of(self.week_start)
