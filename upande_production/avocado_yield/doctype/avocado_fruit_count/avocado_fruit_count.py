# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

# Fruit counted on the tree — the one measurement nobody was taking.
#
# The orchard master knows how many trees bear and the harvest logs know what
# came off them last season, but neither says what is hanging RIGHT NOW. A count
# does, and it is the difference between a forecast that follows a curve and one
# that follows the crop.
#
# Fruit weight is not asked for twice: the block's own lab sample already carries
# it, and a number typed here only overrides that when someone weighed fruit on
# the spot.

import frappe
from frappe.model.document import Document
from frappe.utils import flt

# Their own harvests recorded 215-230 g. Only reached when a block has neither a
# typed weight nor a lab sample, and the basis field says so on the record.
DEFAULT_FRUIT_WEIGHT_G = 220.0


class AvocadoFruitCount(Document):
	def validate(self):
		self.set_estimate()

	def set_estimate(self):
		grams = flt(self.avg_fruit_weight_g)
		basis = "typed on this count"
		if not grams:
			grams, basis = self._weight_from_sample()

		keep = 1.0 - min(max(flt(self.drop_pct), 0.0), 90.0) / 100.0
		self.est_kg_per_tree = flt(self.fruit_per_tree) * grams / 1000.0 * keep
		self.weight_basis = f"{grams:.0f} g, {basis}"

		# Sized on BEARING trees. Live trees include everything not yet in crop,
		# and using them is how a young orchard forecasts a mature one's harvest.
		self.bearing_trees = flt(self._block_value("bearing_trees"))
		self.est_block_kg = flt(self.est_kg_per_tree) * flt(self.bearing_trees)

	def _weight_from_sample(self):
		if frappe.db.exists("DocType", "Avocado Fruit Sample"):
			g = frappe.db.get_value(
				"Avocado Fruit Sample",
				{"orchard_block": self.orchard_block, "avg_fruit_weight_g": [">", 0]},
				"avg_fruit_weight_g", order_by="sample_date desc",
			)
			if flt(g):
				return flt(g), "from this block's latest fruit sample"
		return DEFAULT_FRUIT_WEIGHT_G, "estate default, no sample on this block"

	def _block_value(self, fieldname):
		if not frappe.db.exists("DocType", "Avocado Orchard Block"):
			return 0
		return frappe.db.get_value("Avocado Orchard Block", self.orchard_block, fieldname)
