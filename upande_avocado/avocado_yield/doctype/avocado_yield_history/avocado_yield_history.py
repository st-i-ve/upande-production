# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

# One row per block per season: what it actually delivered.
#
# This is the record the whole forecast leans on. It comes from the estate's own
# Master Yield Summary, so the curve is no longer a constant in a Python file — it
# is data, and correcting a season corrects every number downstream.

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class AvocadoYieldHistory(Document):
	def validate(self):
		block = self._block()
		trees = int(self.trees or (block.get("total_trees") if block else 0) or 0)
		self.trees = trees
		self.kg_per_tree = flt(self.kg_harvested) / trees if trees else 0
		area = flt(block.get("area_ha")) if block else 0
		self.kg_per_ha = flt(self.kg_harvested) / area if area else 0
		if block and block.get("planting_year"):
			self.tree_age = int(self.year) - int(block["planting_year"])
		if block and not self.farm:
			self.farm = block.get("farm")

	def _block(self):
		for dt, field in (("Avocado Yield Block", "block_code"),
						  ("Avocado Orchard Block", "block_code")):
			if not frappe.db.exists("DocType", dt):
				continue
			row = frappe.db.get_value(dt, {field: self.block_code},
									  ["total_trees", "area_ha", "planting_year", "farm"],
									  as_dict=True)
			if row:
				return row
		return None
