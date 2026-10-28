# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

LOCKED = ("Active", "Superseded", "Pending Approval", "Rejected")


class ProductionProtocol(Document):
	def validate(self):
		if not self.protocol_family:
			self.protocol_family = self.protocol_name
		if self.is_new() and frappe.flags.in_demo_seed and not self.previous_version:
			self.version_status = "Active"  # the demo's base protocols are v1 Active
		if self.variety:
			vcrop, vitem = frappe.db.get_value("Production Variety", self.variety, ["crop", "item"]) or (None, None)
			if vcrop and self.crop and vcrop != self.crop:
				frappe.throw(_("Variety {0} belongs to {1}, not {2}").format(self.variety, vcrop, self.crop),
					frappe.ValidationError)
			if not self.item:
				self.item = vitem
		if not self.version:
			self.version = 1
		if self.is_new():
			return
		# Only Drafts are editable; status moves are made by production/logic/protocols.py.
		if frappe.flags.in_patch or frappe.flags.in_demo_seed or self.flags.protocol_transition:
			return
		before = self.get_doc_before_save()
		if before and before.version_status in LOCKED:
			frappe.throw(
				_("{0} is {1} and cannot be edited. Create a new version instead.").format(
					self.name, before.version_status
				),
				frappe.ValidationError,
			)

