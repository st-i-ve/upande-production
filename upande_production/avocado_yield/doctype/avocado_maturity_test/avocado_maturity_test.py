# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

# A maturity test: the date the crop is allowed to be picked.
#
# Fruit size and fruit weight do not decide when a Hass can be cut — dry matter
# does, and below the export minimum the fruit is not legally pickable however
# big it is. So this record sits alongside the fruit counts: the counts size the
# crop, this dates it.
#
# The estate's lab writes MOISTURE, not dry matter, because that is what the oven
# reads. Dry matter is the remainder, and it is derived here rather than typed so
# the two can never disagree on a record.
#
# One honest limitation, carried in the field labels: these tests are kept per
# PLANTING (the 23 Ha, 70 Ha and 65 Ha blocks of trees), not per block. Sampling
# is done on the planting because trees of one age flower and fill together, so a
# test speaks for every block of that planting and for no single one of them.

import frappe
from frappe.model.document import Document
from frappe.utils import flt

from upande_production.api.avocadoapi import MIN_DRY_MATTER_PCT, dry_matter_from_moisture


class AvocadoMaturityTest(Document):
	def validate(self):
		# One of the two must identify the fruit, or the reading describes nothing.
		if not (self.orchard_block or self.planting_area):
			frappe.throw("Give the block the fruit came off, or the planting area it "
						 "belongs to. A reading with neither cannot be used.")

		self.dry_matter_pct = dry_matter_from_moisture(self.moisture_pct)
		# A reading that says the flesh is all water, or has none, is a blank cell
		# or a template placeholder rather than a test. Their sheets are full of
		# 1.00 in the weeks nobody sampled.
		if not (5.0 <= flt(self.dry_matter_pct) <= 60.0):
			frappe.throw(
				f"Moisture {self.moisture_pct} gives {self.dry_matter_pct}% dry matter, "
				f"which no avocado has. Check the reading."
			)
		self.export_ready = 1 if flt(self.dry_matter_pct) >= MIN_DRY_MATTER_PCT else 0
