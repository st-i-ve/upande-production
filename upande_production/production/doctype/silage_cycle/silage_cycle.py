# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from upande_production.production.logic import silage


class SilageCycle(Document):
	def validate(self):
		silage.validate_cycle(self)

	def before_submit(self):
		silage.before_close(self)

	def on_submit(self):
		silage.post_pit_receipt(self)

	def before_cancel(self):
		# The input issues and machine diesel stay submitted and stay the cycle's: cancelling a closed cycle
		# reverses only its pit receipt. Without this the issues' link back to the cycle refuses the cancel.
		self.ignore_linked_doctypes = ("Stock Entry", "Production Asset Allocation")
		silage.reverse_pit_receipt(self)

	def on_cancel(self):
		self.db_set("status", "Cancelled", update_modified=False)
