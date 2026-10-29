# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

# Today's avocado model values, kept in one place for SEEDING only.
#
# Until the model moved onto Production Crop / Production Variety these figures were
# constants in the avocado API modules. They are the starting values for the demo and
# for a site that predates the settings (see patches/seed_avocado_model.py); after that
# a manager edits them in Settings, Crop model. The model code never imports this
# module (tests/test_avocado_no_literals.py greps for that), so nothing here can leak
# back into a forecast.
#
# Source of the curve: the estate's "Master Yield Summary - edit July 2025" (kg per
# planted tree by age: 12 at 2-3 years, 35 at 4, 63 at 5, 97 at 6, about 90 mature).
# The off-year factor is 56.6 kg/tree in an off year against 97.1 in an on year. The late
# crop's share is 434,362 kg of 513,248 kg delivered in 2025 (84.6%).

import frappe
from frappe.utils import flt

# (from age in years, kg per plant): each row applies until the next.
YIELD_BY_AGE = [(0, 0.0), (2, 12.0), (3, 12.0), (4, 35.0), (5, 63.0), (6, 97.0), (7, 90.0), (10, 90.0)]
BIENNIAL_OFF_FACTOR = 0.58
ON_YEARS = "Even"
LATE_CROP_SHARE_PCT = 84.6
PRICE_PER_KG = 95
DRY_MATTER_TARGET_PCT = 24

# (count, min g, max g): the export count sizes off the estate's maturity sheets.
COUNT_SIZES = [
	(14, 275, 317), (16, 242, 275), (18, 216, 242), (20, 196, 216), (22, 179, 196),
	(24, 164, 179), (26, 152, 164), (28, 142, 152), (30, 132, 142), (32, 94, 132),
]

# Crop fields filled from the doctype's own field defaults when empty.
CROP_DEFAULTED = ["harvest_days_per_week", "min_trees_to_override_curve", "default_kg_per_picker_day",
	"plausible_kg_per_picker_day_min", "plausible_kg_per_picker_day_max", "dry_matter_max_pct",
	"dm_gain_per_week", "stale_sample_weeks", "default_pick_weeks"]


def apply_to_crop(name):
	"""Fill the avocado crop's model fields where they are empty. Never overwrites a value."""
	doc = frappe.get_doc("Production Crop", name)
	meta = frappe.get_meta("Production Crop")
	changed = False
	for f in CROP_DEFAULTED:
		if not flt(doc.get(f)):
			default = meta.get_field(f).default
			if default is not None:
				doc.set(f, flt(default))
				changed = True
	for f, v in (("price_per_kg", PRICE_PER_KG), ("dry_matter_target_pct", DRY_MATTER_TARGET_PCT)):
		if not flt(doc.get(f)):
			doc.set(f, v)
			changed = True
	if not doc.get("count_sizes"):
		for c, lo, hi in COUNT_SIZES:
			doc.append("count_sizes", {"count": c, "min_g": lo, "max_g": hi})
		changed = True
	if changed:
		doc.flags.ignore_permissions = True
		doc.save()
	return changed


def apply_to_variety(name):
	"""Fill a variety's yield model where it is empty. Never overwrites a value."""
	doc = frappe.get_doc("Production Variety", name)
	changed = False
	if not doc.get("yield_by_age"):
		for age, kg in YIELD_BY_AGE:
			doc.append("yield_by_age", {"age_years": age, "kg_per_plant": kg})
		changed = True
	if not flt(doc.get("biennial_off_factor")):
		doc.biennial_off_factor, doc.on_years = BIENNIAL_OFF_FACTOR, ON_YEARS
		changed = True
	if not flt(doc.get("late_crop_share_pct")):
		doc.late_crop_share_pct = LATE_CROP_SHARE_PCT
		changed = True
	if changed:
		doc.flags.ignore_permissions = True
		doc.save()
	return changed
