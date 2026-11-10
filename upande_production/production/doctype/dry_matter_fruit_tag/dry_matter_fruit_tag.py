# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from upande_production.production.logic import drymatter_monitor as mon


class DryMatterFruitTag(Document):
	def validate(self):
		self.tree_label = (self.tree_label or "").strip()
		self.fruit_tag = (self.fruit_tag or "").strip()
		if not self.tree_label or not self.fruit_tag:
			frappe.throw(_("A fruit needs a tree and a tag number."), frappe.ValidationError)
		clash = frappe.db.exists(mon.TAG, {"unit": self.unit, "tree_label": self.tree_label, "fruit_tag": self.fruit_tag,
			"name": ("!=", self.name or "")})
		if clash:
			frappe.throw(_("Fruit {0} on tree {1} in {2} is already tagged ({3}).").format(
				self.fruit_tag, self.tree_label, self.unit, clash), frappe.ValidationError)
		mon.tag_context(self)
		for r in self.readings or []:
			mon.fill_reading(r)
			if self.tagged_on and str(r.reading_date) < str(self.tagged_on):
				frappe.throw(_("A reading cannot be dated before the fruit was tagged ({0}).").format(self.tagged_on),
					frappe.ValidationError)
		mon.refresh_latest(self)
