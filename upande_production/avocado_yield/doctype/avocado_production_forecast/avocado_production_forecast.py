# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

# A typed forecast, kept beside the calculated one, never inside it.
#
# The production page can show either: the estate's own age-curve/dry-matter
# arithmetic (see api/avocadoapi.py), or whatever a person has typed here. One row
# per block per season per crop, so a phone entered late in the day still lands on
# the same row a desk edits later instead of piling up duplicates.

import frappe
from frappe.model.document import Document


class AvocadoProductionForecast(Document):
	def validate(self):
		dupe = frappe.db.exists("Avocado Production Forecast", {
			"orchard_block": self.orchard_block,
			"season": self.season,
			"crop": self.crop,
			"name": ("!=", self.name or ""),
		})
		if dupe:
			frappe.throw(
				f"{self.orchard_block} already has a {self.crop} forecast for {self.season} "
				f"({dupe}). Edit that one so the block's forecast stays in one place."
			)
