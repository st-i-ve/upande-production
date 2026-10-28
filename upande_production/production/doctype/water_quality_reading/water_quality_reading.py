# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from upande_production.production.logic import aquaculture as logic


class WaterQualityReading(Document):
	def validate(self):
		logic.validate_water_quality_reading(self)
