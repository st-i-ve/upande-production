# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, time_diff_in_hours


class PivotIrrigationRun(Document):
	def validate(self):
		unit = frappe.db.get_value("Production Unit", self.unit, ["crop", "unit_type"], as_dict=True)
		if not unit:
			frappe.throw(_("Pivot {0} not found.").format(self.unit))
		self.crop = unit.crop
		if unit.unit_type != "Pivot":
			frappe.throw(_("{0} is not a pivot.").format(self.unit))
		if not (self.start_time and self.end_time):
			frappe.throw(_("Start and end are required."))
		hours = time_diff_in_hours(self.end_time, self.start_time)
		if hours <= 0:
			frappe.throw(_("The run must end after it starts."))
		self.hours = round(hours, 2)
		if flt(self.depth_mm) < 0:
			frappe.throw(_("Depth applied cannot be negative."))
		pct = flt(self.percent_timer)
		if pct < 0 or pct > 100:
			frappe.throw(_("Percent timer must be between 0 and 100."))
		seen = set()
		for row in self.slices:
			parent = frappe.db.get_value("Production Unit", row.slice, "parent_production_unit")
			if parent != self.unit:
				frappe.throw(_("{0} is not a slice of {1}.").format(row.slice, self.unit))
			if row.slice in seen:
				frappe.throw(_("{0} is listed twice.").format(row.slice))
			seen.add(row.slice)
		if not self.fault:
			self.fault = "None"
