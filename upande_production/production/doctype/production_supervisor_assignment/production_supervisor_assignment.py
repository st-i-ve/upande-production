# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from upande_production.production.logic.weeks import iso_week_bounds


class ProductionSupervisorAssignment(Document):
	def validate(self):
		try:
			self.week_start = iso_week_bounds(self.plan_year, self.plan_week)[0]
		except ValueError:
			frappe.throw(_("Not a valid ISO week."), frappe.ValidationError)
		unit = frappe.db.get_value("Production Unit", self.unit, ["crop", "farm"], as_dict=True)
		if unit.crop != self.crop:
			frappe.throw(_("{0} does not belong to the crop {1}.").format(self.unit, self.crop), frappe.ValidationError)
		self.farm = self.farm or unit.farm
		dup = frappe.db.get_value("Production Supervisor Assignment", {
			"unit": self.unit, "plan_year": self.plan_year, "plan_week": self.plan_week, "crop": self.crop,
			"name": ("!=", self.name or ""),
		})
		if dup:
			frappe.throw(
				_("{0} already has a supervisor for week {1} of {2}: {3}").format(
					self.unit, self.plan_week, self.plan_year, dup),
				frappe.DuplicateEntryError,
			)
