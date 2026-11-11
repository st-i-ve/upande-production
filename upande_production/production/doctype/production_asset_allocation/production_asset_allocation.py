# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from upande_production.production.logic import asset_allocation


class ProductionAssetAllocation(Document):
	def validate(self):
		asset_allocation.validate_allocation(self)

	def before_submit(self):
		asset_allocation.before_submit(self)

	def on_submit(self):
		asset_allocation.post_diesel(self)

	def before_cancel(self):
		asset_allocation.reverse_diesel(self)

	def on_cancel(self):
		self.db_set("status", "Cancelled", update_modified=False)
