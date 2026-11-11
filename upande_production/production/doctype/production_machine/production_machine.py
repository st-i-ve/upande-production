# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from upande_production.production.logic import asset_allocation


class ProductionMachine(Document):
	def before_insert(self):
		asset_allocation.ensure_qr_token(self)

	def validate(self):
		asset_allocation.validate_machine(self)
