# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ProductionSubCrop(Document):
	def validate(self):
		self.sub_crop_name = (self.sub_crop_name or "").strip()
		if not self.sub_crop_name:
			frappe.throw(_("Enter the sub-crop name."), frappe.ValidationError)
