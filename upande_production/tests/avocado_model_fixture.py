# Today's avocado model parameters as plain rows, for the pure-function tests.
#
# These are test inputs, not defaults: the model code has no copy of them (see
# test_avocado_no_literals.py). They mirror what the demo seed writes onto the
# Avocado Production Crop and the Hass variety, so the arithmetic is checked against
# the same figures the demo shows.

from upande_production.api.avocado_model import build_model

CROP = {
	"name": "Avocado", "price_per_kg": 95, "avg_kg_per_crate": 18, "harvest_days_per_week": 5,
	"default_kg_per_picker_day": 450, "plausible_kg_per_picker_day_min": 150,
	"plausible_kg_per_picker_day_max": 1200, "min_trees_to_override_curve": 1000,
	"dry_matter_target_pct": 24, "dry_matter_max_pct": 34, "dm_gain_per_week": 0.7,
	"stale_sample_weeks": 8, "default_pick_weeks": 6,
	"count_sizes": [{"count": 14, "min_g": 275, "max_g": 317}, {"count": 32, "min_g": 94, "max_g": 132}],
}

HASS = {
	"name": "Hass",
	"yield_by_age": [{"age_years": a, "kg_per_plant": k} for a, k in
					 [(0, 0.0), (2, 12.0), (3, 12.0), (4, 35.0), (5, 63.0), (6, 97.0), (7, 90.0), (10, 90.0)]],
	"biennial_off_factor": 0.58, "on_years": "Even", "late_crop_share_pct": 84.6,
	"flowering_seasons": [],
}


def make_model(crop=None, varieties=None):
	return build_model(dict(CROP, **(crop or {})), varieties if varieties is not None else [dict(HASS)])


MODEL = make_model()

# The one closed season the old constant used to carry, as the rows calibration_seasons returns.
CAL_SEASONS = [{"season": 2026, "crop": "Early", "estimated_kg": 1037700.0, "actual_kg": 1185400.0,
				"blocks_estimated": 55, "blocks_harvested": 51}]
