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
		for f in ("weeks_to_first_flowering", "weeks_flowering_to_harvest", "weeks_to_reflower_after_harvest",
				"flowering_interval_weeks"):
			_set(doc, f, 0)
		_set(doc, "flowering_pattern", None)
	seasonal = flowering and _get(doc, "flowering_pattern") == "Seasonal"
	if seasonal:
		# a seasonal crop has no first-flowering / interval of its own; its first harvest is maturity plus
		# the first season's flowering to harvest weeks (the real season is picked from the calendar)
		_set(doc, "weeks_to_first_flowering", 0)
		_set(doc, "flowering_interval_weeks", 0)
		seasons = _get(doc, "flowering_seasons") or []
		_set(doc, "weeks_flowering_to_harvest", cint(_get(seasons[0], "weeks_flowering_to_harvest")) if seasons else 0)
	elif flowering and _get(doc, "flowering_pattern") == "Interval":
		_set(doc, "flowering_seasons", [])
	if _get(doc, "harvest_pattern") in (None, "", "Once"):
		_set(doc, "harvest_interval_weeks", 0)
		_set(doc, "weeks_to_reflower_after_harvest", 0)
	if seasonal:
		_set(doc, "weeks_to_first_harvest",
			(_get(doc, "weeks_to_maturity") or 0) + (_get(doc, "weeks_flowering_to_harvest") or 0))
	elif flowering:
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


def validate_flowering(doc) -> None:
	"""Seasonal needs at least one season (shares total 100 when any is set); Interval needs the interval."""
	if not doc.is_flowering:
		return
	if not doc.flowering_pattern:
		frappe.throw(_("A flowering variety needs a flowering pattern (Seasonal or Interval)"), frappe.ValidationError)
	if doc.flowering_pattern == "Seasonal":
		seasons = doc.flowering_seasons or []
		if not seasons:
			frappe.throw(_("A seasonal variety needs at least one flowering season"), frappe.ValidationError)
		names = [s.season_name for s in seasons]
		if len(set(names)) != len(names):
			frappe.throw(_("A flowering season is listed twice"), frappe.ValidationError)
		for s in seasons:
			if cint(s.weeks_flowering_to_harvest) <= 0:
				frappe.throw(_("Season {0} needs the weeks from flowering to harvest").format(s.season_name),
					frappe.ValidationError)
		if any(flt(s.crop_share_pct) for s in seasons):
			total = sum(flt(s.crop_share_pct) for s in seasons)
			if abs(total - 100) > 0.01:
				frappe.throw(_("Season shares must total 100 % (now {0} %)").format(round(total, 2)),
					frappe.ValidationError)
	elif doc.flowering_pattern == "Interval" and (doc.harvest_pattern or "Once") != "Once" \
			and cint(doc.flowering_interval_weeks) <= 0:
		frappe.throw(_("An interval variety needs the flowering interval (weeks)"), frappe.ValidationError)


class ProductionVariety(Document):
	def validate(self):
		derive(self)
		validate_flowering(self)
		seen = set()
		for s in self.stages:
			if s.stage in seen:
				frappe.throw(_("Stage {0} is listed twice").format(s.stage), frappe.ValidationError)
			seen.add(s.stage)
		if sum(1 for s in self.stages if s.is_harvest) > 1:
			frappe.throw(_("Only one stage can be the harvest stage"), frappe.ValidationError)
