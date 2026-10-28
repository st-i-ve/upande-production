# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from upande_production.production.logic import aquaculture as logic


class PondStocking(Document):
	def validate(self):
		logic.validate_pond_stocking(self)
		if self.strain:
			crop = frappe.db.get_value("Production Variety", self.strain, "crop")
			if crop and crop != "Aquaculture":
				frappe.throw(_("Strain {0} is a {1} variety, not an Aquaculture strain").format(self.strain, crop),
					frappe.ValidationError)

	def get_stage(self, on_date=None):
		from upande_production.production.logic.stages import stage_on

		return stage_on(self, on_date)
