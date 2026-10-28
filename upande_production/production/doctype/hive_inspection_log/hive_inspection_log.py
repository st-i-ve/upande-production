# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt


class HiveInspectionLog(Document):
	def validate(self):
		self.crop = frappe.db.get_value("Production Unit", self.unit, "crop")
		if cint(self.colonies_inspected) < 1:
			frappe.throw(_("Colonies inspected must be at least 1."))
		if cint(self.colonies_queenright) < 0 or cint(self.colonies_queenright) > cint(self.colonies_inspected):
			frappe.throw(_("Colonies queenright must be between 0 and the colonies inspected."))
		if flt(self.varroa_per_100) < 0:
			frappe.throw(_("Varroa mites per 100 bees cannot be negative."))
		for f in ("frames_brood", "frames_honey", "frames_stores", "feeding_kg"):
			if flt(self.get(f)) < 0:
				frappe.throw(_("{0} cannot be negative.").format(self.meta.get_label(f)))
