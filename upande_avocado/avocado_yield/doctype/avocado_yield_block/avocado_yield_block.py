# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

# Fallback orchard master.
#
# Where the avocado_production app is installed, its own Avocado Orchard Block is
# used and this table stays empty. It exists so the forecast page works on a site
# without that app, and so the estate's yield spreadsheets have somewhere to land.

import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate


class AvocadoYieldBlock(Document):
	def validate(self):
		if self.planting_date and not self.planting_year:
			self.planting_year = getdate(self.planting_date).year
		if not flt(self.total_trees) and flt(self.area_ha) and flt(self.trees_per_ha):
			self.total_trees = int(round(flt(self.area_ha) * flt(self.trees_per_ha)))
		if not flt(self.live_trees):
			self.live_trees = self.total_trees
		# Bearing cannot exceed live: the forecast multiplies by it, so a typo here
		# would quietly inflate a whole season.
		if flt(self.bearing_trees) > flt(self.live_trees):
			frappe.throw(f"Bearing trees ({flt(self.bearing_trees):.0f}) cannot exceed "
						 f"live trees ({flt(self.live_trees):.0f}).")
