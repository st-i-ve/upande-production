# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

# A shelf trial: cut a few fruit, lay them out, write down the day each goes soft.
#
# The second opinion on the same question the oven answers. Dry matter says the fruit
# is legally pickable; days to ripen says whether it behaves like mature fruit, and
# it needs no laboratory. Where the two agree the estate can pick with confidence.
# Where they disagree somebody should walk the orchard before the trucks are booked.
#
# Nothing on this record gates a harvest date. The estate has never published a
# ripening threshold and there is not yet enough here to derive one, so these rows
# are reported beside dry matter and never in place of it.

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class AvocadoRipeningTest(Document):
	def validate(self):
		if flt(self.fruit_harvested) <= 0:
			frappe.throw("A trial nobody cut fruit for is a heading, not a test.")
		if flt(self.fruit_ripe) > flt(self.fruit_harvested):
			frappe.throw(f"{self.fruit_ripe} fruit ripened out of {self.fruit_harvested} "
						 f"cut. More fruit came off the shelf than went onto it.")
		self.pct_ripe = round(flt(self.fruit_ripe) / flt(self.fruit_harvested) * 100, 1)
		# A trial still running has no average, and a zero is not one: no avocado
		# softens the day it is cut. Better empty than a number nobody measured.
		if flt(self.avg_days_to_ripen) <= 0:
			self.avg_days_to_ripen = None
		if self.last_observed and self.harvest_date and self.last_observed < self.harvest_date:
			frappe.throw("The shelf cannot end before the fruit was cut.")
