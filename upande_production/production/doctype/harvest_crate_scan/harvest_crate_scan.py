# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from upande_production.production.logic.harvest import OPEN_STATUSES


class HarvestCrateScan(Document):
	def validate(self):
		self.allocated_at = self.allocated_at or now_datetime()
		if self.status in OPEN_STATUSES and frappe.db.exists(
			"Harvest Crate Scan",
			{"crate_id": self.crate_id, "status": ("in", OPEN_STATUSES), "name": ("!=", self.name or "")},
		):
			frappe.throw(_("Crate {0} is already in use").format(self.crate_id), frappe.ValidationError)
		if self.is_new() and frappe.db.get_value("Harvest Crate", self.crate_id, "status") != "Active":
			frappe.throw(_("Crate {0} is not active").format(self.crate_id), frappe.ValidationError)
