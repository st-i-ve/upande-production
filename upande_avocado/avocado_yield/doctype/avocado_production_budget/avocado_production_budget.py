# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

# The season's target, typed once by whoever plans it. Estate-wide by crop — a
# budget is a target for the desk to plan against, not a per-block measurement,
# so this carries no orchard block at all. Entered month by month, because
# "1,200 t this season" is never how anyone actually plans a budget — it is
# built up from what each month is expected to give, and the season total is
# only ever the sum of that, never typed on its own.

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class AvocadoProductionBudget(Document):
	def validate(self):
		dupe = frappe.db.exists("Avocado Production Budget", {
			"season": self.season,
			"crop": self.crop,
			"name": ("!=", self.name or ""),
		})
		if dupe:
			frappe.throw(
				f"{self.season} already has a {self.crop} budget ({dupe}). "
				"Edit that one so the season's budget stays in one place."
			)

		seen = set()
		for row in self.months:
			if row.month in seen:
				frappe.throw(f"{row.month} is on this budget twice — one row per month.")
			seen.add(row.month)
			row.budget_value = (round(flt(row.budget_kg) * flt(self.budget_price_per_kg), 0)
								 if flt(self.budget_price_per_kg) else None)

		# The total is never typed — it is only ever what the months add up to.
		self.budget_kg = round(sum(flt(row.budget_kg) for row in self.months), 0)
		self.budget_value = (round(flt(self.budget_kg) * flt(self.budget_price_per_kg), 0)
							  if flt(self.budget_price_per_kg) else None)
