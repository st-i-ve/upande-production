# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from upande_production.production.logic import rates


class FieldOperationRate(Document):
	def validate(self):
		rates.validate_period(self)
