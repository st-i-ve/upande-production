# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from upande_production.production.logic import aquaculture as logic


class FishMortalityLog(Document):
	def validate(self):
		logic.validate_fish_mortality_log(self)
