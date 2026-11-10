# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from upande_production.production.logic import count_sizes


class ProductionCrop(Document):
	def validate(self):
		self.warn_count_size_bands()

	def warn_count_size_bands(self):
		"""Gaps and overlaps between count sizes are a warning, not an error: save still goes through."""
		issues = count_sizes.band_issues(self.get("count_sizes"))
		if issues:
			frappe.msgprint(
				_("Check the count sizes:") + "<ul>" + "".join(f"<li>{_(i['message'])}</li>" for i in issues) + "</ul>",
				title=_("Count size bands"), indicator="orange",
			)
