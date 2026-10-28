# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

AFTER = "Not within days after operation"
BEFORE = "Not within days before harvest"
STAGE_TYPES = ("Not in stage", "Only in stage")


class ProductionActivityRule(Document):
	def validate(self):
		if not (self.operation or self.operation_category):
			frappe.throw(_("Pick the operation or the operation category the rule applies to."), frappe.ValidationError)
		if self.rule_type in STAGE_TYPES and not self.stage:
			frappe.throw(_("A stage rule needs a stage."), frappe.ValidationError)
		if self.rule_type in (AFTER, BEFORE) and (self.days or 0) <= 0:
			frappe.throw(_("Days must be greater than zero."), frappe.ValidationError)
		if self.rule_type == AFTER and not (self.other_operation or self.other_category):
			frappe.throw(_("Pick the other operation or category this rule waits for."), frappe.ValidationError)
		if self.variety and frappe.db.get_value("Production Variety", self.variety, "crop") != self.crop:
			frappe.throw(_("{0} is not a variety of {1}.").format(self.variety, self.crop), frappe.ValidationError)
		if self.rule_type not in STAGE_TYPES:
			self.stage = None
