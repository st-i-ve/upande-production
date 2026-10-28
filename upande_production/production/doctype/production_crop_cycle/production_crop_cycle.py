# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from upande_production.production.logic.cycles import crop_uses_cycles


class ProductionCropCycle(Document):
	def validate(self):
		if self.unit:
			self.crop = frappe.db.get_value("Production Unit", self.unit, "crop")
		if self.crop and not crop_uses_cycles(self.crop):
			frappe.throw(f"{self.crop} does not use crop cycles.")
		if self.protocol and (self.is_new() or self.has_value_changed("protocol")) and not frappe.flags.in_demo_seed:
			if frappe.db.get_value("Production Protocol", self.protocol, "version_status") != "Active":
				frappe.throw(_("Only an Active protocol can be used for a cycle."), frappe.ValidationError)
		self.title = f"{self.unit} · {self.item or self.crop}"
