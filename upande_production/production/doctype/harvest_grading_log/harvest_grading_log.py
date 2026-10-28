# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class HarvestGradingLog(Document):
	def validate(self):
		self.crop = frappe.db.get_value("Production Unit", self.unit, "crop")
		if flt(self.received_kg) <= 0:
			frappe.throw(_("Received kg must be more than zero."))
		if flt(self.rejects_kg) < 0:
			frappe.throw(_("Rejects cannot be negative."))
		if flt(self.rejects_kg) > 0 and not self.reject_reason:
			frappe.throw(_("Give a reason for the rejects."))
		if not self.lines:
			frappe.throw(_("Add at least one grade line."))
		total = 0.0
		for row in self.lines:
			if not (row.grade or "").strip():
				frappe.throw(_("Every grade line needs a grade name."))
			if flt(row.kg) < 0 or flt(row.crates) < 0:
				frappe.throw(_("Grade quantities cannot be negative."))
			total += flt(row.kg)
		self.graded_kg = round(total, 2)
		if total + flt(self.rejects_kg) > flt(self.received_kg) * 1.005 + 0.01:
			frappe.throw(_("Graded kg plus rejects ({0}) is more than the {1} kg received.").format(round(total + flt(self.rejects_kg), 1), self.received_kg))
