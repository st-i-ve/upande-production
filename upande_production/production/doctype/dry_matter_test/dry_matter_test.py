# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from upande_production.production.logic import drymatter


class DryMatterTest(Document):
	def validate(self):
		unit = frappe.db.get_value("Production Unit", self.unit, ["crop"], as_dict=True)
		self.crop = self.crop or (unit.crop if unit else None)
		# the cycle and variety follow the block at the test date unless the caller named them
		if not self.cycle:
			self.cycle = drymatter.cycle_on(self.unit, self.test_date)
		if not self.variety and self.cycle:
			self.variety = frappe.db.get_value("Production Crop Cycle", self.cycle, "variety")
		rule = drymatter.rules_for(self.variety, self.crop)
		if not rule["testing"]:
			frappe.throw(
				_("Dry matter testing is not switched on for {0}.").format(self.variety or self.crop), frappe.ValidationError
			)
		self.tested_on = rule["on"] or self.tested_on
		self.tested_by = self.tested_by or frappe.session.user
		self.stage = drymatter.stage_of_cycle(self.cycle, self.test_date)

		vals = [flt(s.dry_matter_pct) for s in self.samples or []]
		if not vals:
			frappe.throw(_("Add at least one sample."), frappe.ValidationError)
		self.avg_pct = round(sum(vals) / len(vals), 2)

		self.target_pct = flt(rule["target"])
		self.ready = 1 if self.avg_pct >= self.target_pct else 0
