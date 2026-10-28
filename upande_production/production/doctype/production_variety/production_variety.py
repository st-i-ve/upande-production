# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt


def _get(doc, key):
	return doc.get(key) if hasattr(doc, "get") else getattr(doc, key, None)


def _set(doc, key, value):
	if isinstance(doc, dict):
		doc[key] = value
	else:
		setattr(doc, key, value)


def derive(doc) -> None:
	"""Fill the derived template fields (weeks, days, plant density) and clear fields the
	current pattern hides. Works on a Document or any dict-like object."""
	flowering = bool(_get(doc, "is_flowering"))
	if not flowering:
		for f in ("weeks_to_first_flowering", "weeks_flowering_to_harvest", "weeks_to_reflower_after_harvest"):
			_set(doc, f, 0)
	if _get(doc, "harvest_pattern") in (None, "", "Once"):
		_set(doc, "harvest_interval_weeks", 0)
		_set(doc, "weeks_to_reflower_after_harvest", 0)
	if flowering:
		_set(doc, "weeks_to_first_harvest",
			(_get(doc, "weeks_to_first_flowering") or 0) + (_get(doc, "weeks_flowering_to_harvest") or 0))
	if _get(doc, "weeks_to_first_harvest"):
		_set(doc, "days_to_first_harvest", cint(_get(doc, "weeks_to_first_harvest")) * 7)
	if _get(doc, "harvest_window_weeks"):
		_set(doc, "harvest_window_days", cint(_get(doc, "harvest_window_weeks")) * 7)
	if _get(doc, "plants_per_m2"):
		_set(doc, "plants_per_ha", round(flt(_get(doc, "plants_per_m2")) * 10000, 4))
	elif _get(doc, "plants_per_ha"):
		_set(doc, "plants_per_m2", round(flt(_get(doc, "plants_per_ha")) / 10000, 6))


class ProductionVariety(Document):
	def validate(self):
		derive(self)
		seen = set()
		for s in self.stages:
			if s.stage in seen:
				frappe.throw(_("Stage {0} is listed twice").format(s.stage), frappe.ValidationError)
			seen.add(s.stage)
		if sum(1 for s in self.stages if s.is_harvest) > 1:
			frappe.throw(_("Only one stage can be the harvest stage"), frappe.ValidationError)
