# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from upande_production.production.logic import harvest


class HarvestBatch(Document):
	def validate(self):
		harvest.validate_batch(self)

	def on_submit(self):
		harvest.post_batch(self)

	def before_cancel(self):
		harvest.reverse_batch(self)

	def on_cancel(self):
		self.db_set("status", "Cancelled", update_modified=False)
