"""Crop labels and a block's type pick from Production Unit Type.

Makes sure every standard type exists, maps each crop's three labels onto the list ("Pivot 1" -> "Pivot"),
normalises crop_key to its slug, blanks an icon_key the Select no longer offers, and adds a type for any
Production Unit.unit_type value not yet in the list. Idempotent.
"""

import re

import frappe

from upande_production.production.doctype.production_section.production_section import slugify
from upande_production.production.doctype.production_unit_type.production_unit_type import STANDARD

LABELS = ("parent_unit_label", "unit_label", "sub_unit_label")
ICONS = ("avocado", "fruit", "vegetables", "fish", "hive")


def _ensure_type(name, description=None):
	if not frappe.db.exists("Production Unit Type", name):
		frappe.get_doc({"doctype": "Production Unit Type", "unit_type_name": name, "description": description}
			).insert(ignore_permissions=True)
		print(f"unit_type_list: added unit type {name}")
	return name


def _match(label):
	"""The list name a crop label maps to, creating a type when none matches; None for an empty label."""
	base = re.sub(r"\s+\d+$", "", (label or "").strip()).strip()
	if not base:
		return None
	by_lower = {n.lower(): n for n in frappe.get_all("Production Unit Type", pluck="name")}
	return by_lower.get(base.lower()) or _ensure_type(base)


def execute():
	for name, desc in STANDARD:
		_ensure_type(name, desc)

	for crop in frappe.get_all("Production Section", fields=["name", "crop_key", "icon_key", *LABELS]):
		changes = {}
		for f in LABELS:
			new = _match(crop[f])
			if new != (crop[f] or None):
				changes[f] = new
		key = slugify(crop.crop_key or crop.name)
		if key != crop.crop_key:
			changes["crop_key"] = key
		if crop.icon_key and crop.icon_key not in ICONS:
			changes["icon_key"] = ""
		if changes:
			frappe.db.set_value("Production Section", crop.name, changes, update_modified=False)
			print(f"unit_type_list: crop {crop.name}: " + ", ".join(
				f"{k} {crop.get(k)!r} -> {v!r}" for k, v in changes.items()))

	for t in frappe.get_all("Production Unit", pluck="unit_type", distinct=True):
		if t:
			_ensure_type(t)
