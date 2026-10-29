# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

# The avocado model's parameters, read from the records a manager edits in Settings.
#
# Nothing here is a number about this estate. Estate-wide parameters sit on the
# Avocado Production Crop (price, crate weight, picking rates, dry matter window,
# model constants, count sizes); parameters that differ by variety sit on Production
# Variety (yield by age, biennial bearing, late crop share, dry matter target).
# `load_model()` reads them once per request and the forecasting maths takes the
# result as a plain dict, so the pure functions stay testable without a site.
#
# A parameter that has to exist and does not is an error that names where to set it,
# never a quiet stand-in: a forecast on an invented number is worse than none.

import frappe
from frappe.utils import cint, flt

CROP_KEY = "avocado"

# The last band of a yield-by-age table has no upper age. Not a business figure: it
# is only the sentinel for "and older".
OPEN_END_AGE = 99

# A flowering season whose name contains this word is the late crop.
LATE_SEASON_WORD = "late"

# (field, label) of the crop parameters that must be set for the model to run.
REQUIRED_CROP_FIELDS = [
	("dry_matter_target_pct", "Dry Matter Target %"),
	("dry_matter_max_pct", "Dry Matter Max %"),
	("dm_gain_per_week", "Dry Matter Gain per Week"),
	("stale_sample_weeks", "Stale Sample Weeks"),
	("default_pick_weeks", "Default Pick Weeks"),
	("harvest_days_per_week", "Harvest Days per Week"),
	("default_kg_per_picker_day", "Default Kg per Picker Day"),
	("plausible_kg_per_picker_day_min", "Plausible Rate Min"),
	("plausible_kg_per_picker_day_max", "Plausible Rate Max"),
	("min_trees_to_override_curve", "Min Trees to Override Curve"),
	("avg_kg_per_crate", "Avg Kg per Crate"),
]


def crop_name():
	return frappe.db.get_value("Production Crop", {"crop_key": CROP_KEY})


def curve_bands(rows):
	"""[(from_age, to_age, kg_per_plant)] from yield-by-age rows (each applies until the next)."""
	rows = sorted(((cint(r.get("age_years")), flt(r.get("kg_per_plant"))) for r in rows or []),
				  key=lambda r: r[0])
	out = []
	for i, (age, kg) in enumerate(rows):
		hi = rows[i + 1][0] - 1 if i + 1 < len(rows) else OPEN_END_AGE
		out.append((age, max(hi, age), kg))
	return out


def late_share(seasons, fallback_pct):
	"""The late crop's share of a year as a fraction: the season named Late, else the variety's own figure."""
	for s in seasons or []:
		if LATE_SEASON_WORD in str(s.get("season_name") or "").lower() and flt(s.get("crop_share_pct")) > 0:
			return flt(s["crop_share_pct"]) / 100.0
	return flt(fallback_pct) / 100.0 if flt(fallback_pct) > 0 else None


def _variety(v, crop_dm_min):
	off = flt(v.get("biennial_off_factor"))
	on = str(v.get("on_years") or "")
	return {
		"name": v.get("name"),
		"curve": curve_bands(v.get("yield_by_age")),
		# Both halves are needed: an off factor without saying which years are on says nothing.
		"off_factor": off if off > 0 and on in ("Even", "Odd") else None,
		"on_years_even": on == "Even",
		"late_share": late_share(v.get("flowering_seasons"), v.get("late_crop_share_pct")),
		"dm_min": flt(v.get("dry_matter_target_pct")) or crop_dm_min,
	}


def build_model(crop, varieties):
	"""The model dict from a Production Crop row and its Production Variety rows (plain dicts)."""
	for field, label in REQUIRED_CROP_FIELDS:
		if not flt(crop.get(field)):
			frappe.throw(f"Set {label} on the {crop.get('name')} crop (Settings, Crop model).",
						 frappe.ValidationError)
	dm_min = flt(crop.get("dry_matter_target_pct"))
	return {
		"crop": crop.get("name"),
		"price_per_kg": flt(crop.get("price_per_kg")),
		"avg_kg_per_crate": flt(crop.get("avg_kg_per_crate")),
		"harvest_days_per_week": cint(crop.get("harvest_days_per_week")),
		"default_kg_per_picker_day": flt(crop.get("default_kg_per_picker_day")),
		"plausible_rate": (flt(crop.get("plausible_kg_per_picker_day_min")),
						   flt(crop.get("plausible_kg_per_picker_day_max"))),
		"min_trees_to_override_curve": cint(crop.get("min_trees_to_override_curve")),
		"dm_min": dm_min,
		"dm_max": flt(crop.get("dry_matter_max_pct")),
		"dm_gain_per_week": flt(crop.get("dm_gain_per_week")),
		"stale_sample_weeks": cint(crop.get("stale_sample_weeks")),
		"default_pick_weeks": cint(crop.get("default_pick_weeks")),
		"count_sizes": [(cint(s.get("count")), flt(s.get("min_g")), flt(s.get("max_g")))
						for s in sorted(crop.get("count_sizes") or [], key=lambda s: cint(s.get("count")))],
		"varieties": {v["name"]: _variety(v, dm_min) for v in varieties},
	}


def load_model(crop=None):
	"""Read the avocado model from Production Crop / Production Variety."""
	name = crop or crop_name()
	if not name:
		frappe.throw("There is no avocado crop. Add a Production Crop with the key 'avocado'.",
					 frappe.ValidationError)
	c = frappe.get_doc("Production Crop", name).as_dict()
	varieties = [frappe.get_doc("Production Variety", n).as_dict()
				 for n in frappe.get_all("Production Variety", filters={"crop": name, "enabled": 1},
										 pluck="name", order_by="name asc")]
	return build_model(c, varieties)


def variety_for(model, variety):
	"""The model's variety for a block's variety text ("Hass", "Fuerte, Hass"): the first listed one it knows."""
	known = model["varieties"]
	names = [p.strip() for p in str(variety or "").split(",") if p.strip()]
	hit = [known[n] for n in names if n in known]
	with_curve = [v for v in hit if v["curve"]]
	return (with_curve or hit or [None])[0]


def dm_min_for(model, variety):
	v = variety_for(model, variety)
	return v["dm_min"] if v else model["dm_min"]
