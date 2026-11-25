# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ProductionFieldCrop(Document):
	def validate(self):
		self.crop_name = (self.crop_name or "").strip()
		if not self.crop_name:
			frappe.throw(_("Enter the crop name."), frappe.ValidationError)

	def on_update(self):
		from upande_production.production.logic import field_crops

		field_crops.align_items(self.name)
