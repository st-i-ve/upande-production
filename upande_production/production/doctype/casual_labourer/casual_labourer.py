# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class CasualLabourer(Document):
	"""A person on the casual labour roster: an Employee plus an active flag, a default
	crew/supervisor and per-operation daily target overrides. Targets are a yardstick; they never change pay."""

	def validate(self):
		seen = set()
		for row in self.targets or []:
			if row.operation in seen:
				frappe.throw(_("Row {0}: {1} already has a target for this person.").format(row.idx, row.operation),
					frappe.ValidationError)
			seen.add(row.operation)
			if float(row.daily_target or 0) <= 0:
				frappe.throw(_("Row {0}: the daily target must be greater than zero.").format(row.idx),
					frappe.ValidationError)
		if self.supervisor and self.supervisor == self.employee:
			frappe.throw(_("A labourer cannot supervise themselves."), frappe.ValidationError)
