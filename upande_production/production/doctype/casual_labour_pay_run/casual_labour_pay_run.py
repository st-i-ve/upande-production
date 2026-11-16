# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from upande_production.production.logic import payrun


class CasualLabourPayRun(Document):
	def autoname(self):
		# the number series comes from Production Settings.pay_reference_prefix (default PAY)
		from frappe.model.naming import make_autoname

		if not self.amended_from:
			self.name = make_autoname(payrun.name_series())

	def validate(self):
		payrun.validate_run(self)

	def on_submit(self):
		payrun.approve(self)

	def before_cancel(self):
		payrun.before_cancel(self)

	def on_cancel(self):
		payrun.release(self)
