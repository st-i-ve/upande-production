# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class ProductionVariety(Document):
	def validate(self):
		seen = set()
		for s in self.stages:
			if s.stage in seen:
				frappe.throw(_("Stage {0} is listed twice").format(s.stage), frappe.ValidationError)
			seen.add(s.stage)
		if sum(1 for s in self.stages if s.is_harvest) > 1:
			frappe.throw(_("Only one stage can be the harvest stage"), frappe.ValidationError)
