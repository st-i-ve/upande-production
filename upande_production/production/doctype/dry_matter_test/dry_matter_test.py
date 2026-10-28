# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class DryMatterTest(Document):
	def validate(self):
		unit = frappe.db.get_value("Production Unit", self.unit, ["crop"], as_dict=True)
		self.crop = self.crop or (unit.crop if unit else None)
		crop = frappe.db.get_value(
			"Production Crop", self.crop, ["dry_matter_testing", "dry_matter_on", "dry_matter_target_pct"], as_dict=True
		)
		if not crop or not crop.dry_matter_testing:
			frappe.throw(_("Dry matter testing is not switched on for crop {0}.").format(self.crop), frappe.ValidationError)
		self.tested_on = crop.dry_matter_on or self.tested_on
		self.tested_by = self.tested_by or frappe.session.user

		vals = [flt(s.dry_matter_pct) for s in self.samples or []]
		if not vals:
			frappe.throw(_("Add at least one sample."), frappe.ValidationError)
		self.avg_pct = round(sum(vals) / len(vals), 2)

		variety_target = flt(frappe.db.get_value("Production Variety", self.variety, "dry_matter_target_pct")) if self.variety else 0
		self.target_pct = variety_target or flt(crop.dry_matter_target_pct)
		self.ready = 1 if self.avg_pct >= self.target_pct else 0
