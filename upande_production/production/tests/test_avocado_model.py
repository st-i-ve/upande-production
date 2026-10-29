"""The avocado model reads its parameters from records, never from code.

Site tests run against the demo data (avocado_seed, which is idempotent and
uncommitted here). Each test changes one setting on Production Crop / Production
Variety / a Harvest Team and checks the endpoint output moves with it. The grep tests
fail if a removed constant or a stand-in number comes back into the avocado modules.
"""

import re
import unittest
from pathlib import Path
from unittest import mock

import frappe
from frappe.tests import IntegrationTestCase

from upande_production.api import avocado as api
from upande_production.api import avocado_model, avocadoapi
from upande_production.production.demo import avocado_seed

APP = Path(__file__).resolve().parents[2]
MODEL_FILES = ["api/avocado.py", "api/avocadoapi.py", "api/avocadolabour.py", "api/avocadomaturity.py",
			   "api/avocado_model.py", "api/production.py", "production/logic/harvest.py"]
REMOVED = ["SEASON_CALIBRATION", "ESTATE_AGE_CURVE", "DEFAULT_AGE_CURVE", "MIN_TREES_TO_OVERRIDE_CURVE",
		   "BIENNIAL_OFF_FACTOR", "ON_YEARS_ARE_EVEN", "LATE_CROP_SHARE", "LATE_COUNT_MAX_AGE_WEEKS",
		   "KG_PER_CRATE", "DEFAULT_KG_PER_PICKER_DAY", "PLAUSIBLE_RATE", "COUNT_SIZES",
		   "MIN_DRY_MATTER_PCT", "MAX_DRY_MATTER_PCT", "STALE_SAMPLE_WEEKS", "DEFAULT_PICK_WEEKS",
		   "DEFAULT_DM_GAIN_PER_WEEK", "DEFAULT_PRICE_PER_KG", "DEFAULT_CREW", "DEFAULT_AVG_KG",
		   "PREF_PRICE", "PREF_CREW", "avocado_price_per_kg", "avocado_crew_available"]


class TestNoLiterals(unittest.TestCase):
	def test_removed_names_stay_removed(self):
		for f in MODEL_FILES:
			text = (APP / f).read_text()
			for name in REMOVED:
				self.assertIsNone(re.search(rf"\b{name}\b", text), f"{name} is back in {f}")

	def test_no_estate_figures_in_the_model_code(self):
		# the invented 2026 season and the figures that used to stand in for records
		for f in MODEL_FILES:
			text = (APP / f).read_text()
			for lit in ("1185400", "1,185.4", "1037700", "1,037.7", "0.846", "84.6", "0.58"):
				self.assertNotIn(lit, text, f"{lit} is back in {f}")

	def test_model_code_never_imports_the_seed_values(self):
		for f in MODEL_FILES:
			self.assertNotIn("avocado_defaults", (APP / f).read_text(), f)


class TestAvocadoModel(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		avocado_seed.run(commit=False)

	def setUp(self):
		patcher = mock.patch.object(frappe.db, "commit", lambda *a, **k: None)
		patcher.start()
		self.addCleanup(patcher.stop)
		# every test edits settings; undo them so the next one starts from the seeded model
		frappe.db.savepoint("avocado_model_test")
		self.addCleanup(frappe.db.rollback, save_point="avocado_model_test")
		self.crop = frappe.get_doc("Production Crop", "Avocado")

	def set_crop(self, **values):
		frappe.db.set_value("Production Crop", "Avocado", values)

	def test_every_parameter_is_read_from_the_crop(self):
		m = avocado_model.load_model()
		for field, key in (("price_per_kg", "price_per_kg"), ("avg_kg_per_crate", "avg_kg_per_crate"),
						   ("harvest_days_per_week", "harvest_days_per_week"),
						   ("default_kg_per_picker_day", "default_kg_per_picker_day"),
						   ("min_trees_to_override_curve", "min_trees_to_override_curve"),
						   ("dry_matter_target_pct", "dm_min"), ("dry_matter_max_pct", "dm_max"),
						   ("dm_gain_per_week", "dm_gain_per_week"), ("stale_sample_weeks", "stale_sample_weeks"),
						   ("default_pick_weeks", "default_pick_weeks")):
			self.assertEqual(m[key], self.crop.get(field), field)
		self.assertEqual(m["plausible_rate"], (self.crop.plausible_kg_per_picker_day_min,
											   self.crop.plausible_kg_per_picker_day_max))
		self.assertEqual(len(m["count_sizes"]), len(self.crop.count_sizes))
		hass = frappe.get_doc("Production Variety", "Hass")
		self.assertEqual(len(m["varieties"]["Hass"]["curve"]), len(hass.yield_by_age))
		self.assertEqual(m["varieties"]["Hass"]["off_factor"], hass.biennial_off_factor)

	def test_a_missing_parameter_names_where_to_set_it(self):
		self.set_crop(stale_sample_weeks=0)
		with self.assertRaises(frappe.ValidationError) as e:
			avocado_model.load_model()
		self.assertIn("Stale Sample Weeks", str(e.exception))

	def test_price_and_crate_weight_follow_the_crop(self):
		self.set_crop(price_per_kg=100, avg_kg_per_crate=36)
		self.assertEqual(api.production_forecast()["price_per_kg"], 100)
		self.assertEqual(api.season_outlook()["price_per_kg"], 100)
		self.assertEqual(api.harvest_calendar()["kg_per_crate"], 36)
		self.assertEqual(api.picking_plan()["kg_per_crate"], 36)
		# the caller may try another price for the session; it is not saved anywhere
		self.assertEqual(api.production_forecast(price_per_kg=80)["price_per_kg"], 80)
		self.assertEqual(api.production_forecast()["price_per_kg"], 100)

	def test_crate_weight_is_required_to_book_a_harvest(self):
		from upande_production.production.logic import harvest
		self.set_crop(avg_kg_per_crate=0)
		with self.assertRaises(frappe.ValidationError):
			harvest.avg_kg_per_crate(None, "Avocado")

	def test_pick_weeks_and_days_follow_the_crop(self):
		self.set_crop(default_pick_weeks=3, harvest_days_per_week=4)
		self.assertEqual(api.production_forecast()["schedule"]["pick_weeks"], 3)
		self.assertEqual(api.picking_plan()["days_per_week"], 4)
		self.assertEqual(api.picking_plan(days_per_week=6)["days_per_week"], 6)

	def test_dry_matter_window_follows_the_crop_and_variety(self):
		self.set_crop(dry_matter_target_pct=22, dry_matter_max_pct=30)
		frappe.db.set_value("Production Variety", "Fuerte", "dry_matter_target_pct", 0)
		frappe.db.set_value("Production Variety", "Hass", "dry_matter_target_pct", 0)
		r = api.dry_matter()
		self.assertEqual((r["minimum_pct"], r["maximum_pct"]), (22.0, 30.0))
		self.assertEqual(api.dry_matter_preview([{"count_size": 14, "moisture": 0.77}])["min_pct"], 22.0)
		self.assertEqual(api.dry_matter_preview([{"count_size": 14, "moisture": 0.77}])["sizes"][0]["window"], "in")
		self.assertEqual(api.harvest_calendar()["minimum_pct"], 22.0)
		# a variety's own target wins for its blocks (block B is Fuerte)
		frappe.db.set_value("Production Variety", "Fuerte", "dry_matter_target_pct", 25)
		mins = avocadoapi.block_minimums(avocado_model.load_model())
		self.assertEqual(mins["B"], 25.0)
		self.assertEqual(mins["A"], 22.0)

	def test_count_sizes_follow_the_crop(self):
		crop = frappe.get_doc("Production Crop", "Avocado")
		crop.set("count_sizes", [{"count": 10, "min_g": 400, "max_g": 500}])
		crop.save()
		self.assertEqual(api.dry_matter()["form"]["sizes"], [{"count": 10, "min_g": 400.0, "max_g": 500.0}])

	def test_yield_by_age_and_biennial_follow_the_variety(self):
		before = {c["label"]: c["kg_per_tree"] for c in api.production_forecast()["yield_curve"]}
		self.assertEqual(before["2"], 12.0)
		hass = frappe.get_doc("Production Variety", "Hass")
		for row in hass.yield_by_age:
			if row.age_years == 2:
				row.kg_per_plant = 20
		hass.save()
		after = {c["label"]: c["kg_per_tree"] for c in api.production_forecast()["yield_curve"]}
		self.assertEqual(after["2"], 20.0)
		# no biennial setting, no biennial effect and no on/off label
		hass.biennial_off_factor, hass.on_years = 0, None
		hass.save()
		frappe.db.set_value("Production Variety", "Fuerte", {"biennial_off_factor": 0, "on_years": ""})
		self.assertIsNone(api.season_outlook()["header"]["on_year"])
		self.assertTrue(all(y["on_year"] is None for y in api.season_outlook()["delivered_by_season"]))

	def test_crew_is_the_active_members_of_the_crops_harvest_teams(self):
		crew = api.season_outlook()["crew_available"]
		self.assertEqual(crew, avocado_seed.DEMO["crew_available"])
		team = frappe.get_all("Harvest Team", filters={"unit": "Avocado Block A"}, pluck="name")[0]
		emp = frappe.get_all("Harvest Team Member", filters={"parent": team}, pluck="employee")[0]
		frappe.db.set_value("Employee", emp, "status", "Left")
		self.assertEqual(api.season_outlook()["crew_available"], crew - 1)
		self.assertEqual(api.picking_plan()["crew_available"], crew - 1)
		# a figure the caller is trying wins for the session
		self.assertEqual(api.season_outlook(crew_available=3)["crew_available"], 3)
		# other crops' teams are not this crop's crew
		other = frappe.get_all("Harvest Team", filters={"unit": "P2-B2"}, pluck="name")
		self.assertTrue(other)
		self.assertEqual(api.season_outlook(farm="No Such Farm")["crew_available"], 0)

	def test_price_is_saved_by_a_production_manager_only(self):
		frappe.set_user("Guest")
		try:
			self.assertIn("error", api.save_price_per_kg(120))
		finally:
			frappe.set_user("Administrator")

	def test_no_delivered_season_shows_none_not_a_stand_in(self):
		with mock.patch.object(avocadoapi, "_history", return_value=[]), \
				mock.patch.object(avocadoapi, "_harvest_rows", return_value=[]):
			o = api.season_outlook()
			f = api.production_forecast()
		k = {x["key"]: x for x in o["kpis"]}
		self.assertIsNone(k["estimate_accuracy"]["value"])
		self.assertTrue(k["estimate_accuracy"]["none_yet"])
		self.assertEqual(k["estimate_accuracy"]["note"], "no delivered season yet")
		self.assertEqual(k["season_crop"]["calibration_factor"], 1.0)
		self.assertEqual(o["calibration"]["factor"], 1.0)
		self.assertFalse(o["calibration"]["has_data"])
		self.assertEqual(k["season_crop"]["note"], "none delivered yet")
		self.assertEqual(o["delivered_by_season"], [])
		self.assertEqual(f["delivered"]["kg"], 0)
		self.assertFalse(f["delivered"]["recorded"])
		self.assertEqual(f["estimate_vs_delivered"]["basis"], "none")
		self.assertEqual(f["estimate_vs_delivered"]["note"], "No delivered season recorded yet.")

	def test_calibration_comes_from_the_records(self):
		o = api.season_outlook()
		est = sum(avocado_seed.DEMO["early_estimates"].values())
		act = sum(parts[(avocado_seed.DEMO["season"], "Early")][0]
				  for parts in avocado_seed.DEMO["history"].values())
		self.assertEqual(o["calibration"]["estimated_kg"], est)
		self.assertEqual(o["calibration"]["actual_kg"], act)
		self.assertEqual(o["calibration"]["factor"], round(act / est, 3))
		k = {x["key"]: x for x in o["kpis"]}
		self.assertFalse(k["estimate_accuracy"]["none_yet"])
		# change an estimate and the factor follows
		name = frappe.db.get_value("Avocado Production Forecast",
								   {"orchard_block": "A", "season": avocado_seed.DEMO["season"], "crop": "Early"})
		frappe.db.set_value("Avocado Production Forecast", name, "expected_kg", 140000)
		self.assertNotEqual(api.season_outlook()["calibration"]["factor"], o["calibration"]["factor"])
