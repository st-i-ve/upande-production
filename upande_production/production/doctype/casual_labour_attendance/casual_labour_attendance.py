# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from upande_production.production.logic import attendance


class CasualLabourAttendance(Document):
	def validate(self):
		attendance.validate_row(self)
