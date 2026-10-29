"""Bands and per-crop limits: every former constant is read from a setting, and changing the setting
changes the API output. The removed names are gone from the source."""

import pathlib

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from upande_production.api import apiary, aquaculture, fv
from upande_production.api import production as production_api
from upande_production.production.demo import apiary_seed, aquaculture_seed, bands_seed, fv_seed
from upande_production.production.logic import aquaculture as aqua_logic
from upande_production.production.logic import bands

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _rows(*spec):
	return [{"min": lo, "max": hi if hi > lo else None, "severity": sev, "label": lab} for lab, lo, hi, sev in spec]


class Isolated(IntegrationTestCase):
	"""Each test starts from the state the class set up and leaves nothing behind."""

	def setUp(self):
		super().setUp()
		frappe.db.savepoint("bands_test")

	def tearDown(self):
		frappe.db.rollback(save_point="bands_test")
		super().tearDown()


class TestBandMatching(IntegrationTestCase):
	def test_min_included_max_excluded_and_open_end(self):
		rows = _rows(("low", 0, 10, "Critical"), ("mid", 10, 25, "Watch"), ("high", 25, 0, "Good"))
		self.assertEqual(bands.band_for(rows, 0)["label"], "low")
		self.assertEqual(bands.band_for(rows, 9.99)["label"], "low")
		self.assertEqual(bands.band_for(rows, 10)["label"], "mid")
		self.assertEqual(bands.band_for(rows, 1e9)["label"], "high")
		self.assertIsNone(bands.band_for(rows, None))
		self.assertIsNone(bands.band_for([], 5))

	def test_on_target_is_the_lowest_good_row(self):
		rows = _rows(("a", 0, 50, "Critical"), ("b", 90, 125, "Good"), ("c", 125, 0, "Watch"))
		self.assertEqual(bands.on_target_from(rows), 90)
		self.assertIsNone(bands.on_target_from(_rows(("a", 0, 0, "Watch"))))


class TestBandSettings(Isolated):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		bands_seed.run(commit=False)

	def test_get_bands_endpoint_returns_every_set(self):
		b = production_api.get_bands()
		for s in ("Forecast error", "Estimate accuracy", "Irrigation % of target", "Fish survival", "Queen status", "Grade A share"):
			self.assertIn(s, b)
		fe = b["Forecast error"]
		self.assertEqual([(r["min"], r["max"], r["severity"]) for r in fe], [(0, 10, "Good"), (10, 25, "Watch"), (25, None, "Critical")])

	def test_editing_a_band_changes_the_output(self):
		rows = [dict(r, band_set="Forecast error") for r in bands.get_bands()["Forecast error"]]
		rows[0]["max"], rows[1]["min"] = 5, 5
		keep = [dict(r, band_set=s) for s, rs in bands.get_bands().items() if s != "Forecast error" for r in rs]
		bands.save_bands(keep + rows)
		self.assertEqual(bands.band_of("Forecast error", 7)["severity"], "Watch")
		self.assertEqual(production_api.get_bands()["Forecast error"][0]["max"], 5)

	def test_seed_does_not_overwrite_edited_sets(self):
		before = bands.get_bands()["Queen status"]
		self.assertEqual(bands_seed.run(commit=False), [])
		self.assertEqual(bands.get_bands()["Queen status"], before)

	def test_forecast_summary_carries_the_bands(self):
		crop = frappe.db.get_value("Production Crop", {"crop_key": "avocado"})
		r = production_api.forecast_summary(crop)
		self.assertNotIn("error", r)
		self.assertIn("Forecast error", r["bands"])


class TestApiaryLimits(Isolated):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		apiary_seed.run(commit=False)

	def _rng(self):
		return str(add_days(nowdate(), -400)), nowdate()

	def test_limits_come_from_the_crop(self):
		r = apiary.hive_inspections(*self._rng())
		self.assertEqual((r["threshold"], r["watch"]), (3.0, 2.0))
		self.assertEqual(apiary.honey_harvest(*self._rng())["form"]["moisture_limit"], 20.0)
		frappe.db.set_value("Production Crop", "Apiary", {"mite_threshold": 1.0, "mite_watch": 0.5, "honey_moisture_limit": 18.0})
		r = apiary.hive_inspections(*self._rng())
		self.assertEqual((r["threshold"], r["watch"]), (1.0, 0.5))
		self.assertEqual({g["mite_status"] for g in r["groups"]}, {"high"})
		self.assertEqual(r["form"]["threshold"], 1.0)
		self.assertEqual(apiary.honey_harvest(*self._rng())["form"]["moisture_limit"], 18.0)

	def test_queen_status_reads_the_bands(self):
		self.assertEqual(apiary.queen_status(20, 19, bands.get_bands()), "queenright")  # 95
		self.assertEqual(apiary.queen_status(10, 9, bands.get_bands()), "weak")  # 90: the old UI called this a warning too
		self.assertEqual(apiary.queen_status(10, 7, bands.get_bands()), "queenless")
		self.assertEqual(apiary.queen_status(0, 0, bands.get_bands()), "none")
		self.assertEqual(apiary.queen_status(10, 9, {}), "none")

	def test_payload_has_bands_and_kpi_queen_status(self):
		r = apiary.hive_inspections(*self._rng())
		self.assertIn("Queen status", r["bands"])
		self.assertIn(r["kpis"]["queen_status"], ("queenright", "weak", "queenless"))
		self.assertIn("Grade A share", apiary.honey_harvest(*self._rng())["bands"])

	def test_removed_constants(self):
		src = (ROOT / "api" / "apiary.py").read_text()
		for name in ("MITE_THRESHOLD", "MITE_WATCH", '"moisture_limit": 20.0'):
			self.assertNotIn(name, src)


class TestAquacultureLimits(Isolated):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		aquaculture_seed.ensure_limits()

	def test_reading_flags_use_the_bands_given_and_none_means_no_flags(self):
		r = {"dissolved_oxygen_mg_l": 3.0, "ph": 9.0}
		self.assertEqual(aqua_logic.reading_flags(r, None), [])
		strict = {"do_min": 6.0, "ph_min": 7.0, "ph_max": 8.0}
		self.assertEqual({f["metric"] for f in aqua_logic.reading_flags({"dissolved_oxygen_mg_l": 5.0}, strict)}, {"do"})
		self.assertEqual(aqua_logic.reading_flags({"dissolved_oxygen_mg_l": 5.0}, {"do_min": 4.0}), [])

	def test_bands_from_water_band_rows(self):
		rows = [{"parameter": "DO", "min": 4, "max": 0, "unit": "mg/L"}, {"parameter": "pH", "min": 6.5, "max": 8.5, "unit": ""},
				{"parameter": "Ammonia", "min": 0, "max": 0.5, "unit": "mg/L"}]
		b = aqua_logic.bands_from_rows(rows)
		self.assertEqual(b, {"do_min": 4.0, "ph_min": 6.5, "ph_max": 8.5, "ammonia_max": 0.5})

	def test_seeded_bands_match_the_old_tilapia_figures(self):
		crop = frappe.get_doc("Production Crop", "Aquaculture")
		b = aqua_logic.bands_from_rows([r.as_dict() for r in crop.water_bands])
		self.assertEqual(b, {"do_min": 4.0, "ph_min": 6.5, "ph_max": 8.5, "temp_min": 25.0, "temp_max": 30.0,
							 "ammonia_max": 0.5, "nitrite_max": 0.3})
		self.assertEqual(crop.sample_stale_days, 10)
		self.assertEqual([r.feed_type for r in crop.feed_types],
						 ["Starter Crumble", "Grower Pellet 2mm", "Grower Pellet 4mm", "Finisher Pellet 6mm"])

	def test_pond_uses_its_strain_bands_before_the_crop(self):
		pond = frappe.db.get_value("Pond Stocking", {"status": "Growing", "strain": ("is", "set")}, "pond")
		st = frappe.db.get_value("Pond Stocking", {"pond": pond, "status": "Growing", "strain": ("is", "set")}, "name")
		if not st:
			self.skipTest("no growing pond batch with a strain on this site")
		strain = frappe.db.get_value("Pond Stocking", st, "strain")
		self.assertEqual(aqua_logic.bands_for_pond(pond)["do_min"], 4.0)
		v = frappe.get_doc("Production Variety", strain)
		v.set("water_bands", [])
		v.append("water_bands", {"parameter": "DO", "min": 7, "max": 0, "unit": "mg/L"})
		v.save()
		self.assertEqual(aqua_logic.bands_for_pond(pond)["do_min"], 7.0)
		w = aquaculture.water_quality(unit=pond)
		self.assertEqual(w["ponds"][0]["bands"]["do_min"], 7.0)

	def test_payload_limits(self):
		p = aquaculture.pond_batches()
		self.assertEqual(p["sample_stale_days"], 10)
		self.assertIn("Fish survival", p["bands"])
		frappe.db.set_value("Production Crop", "Aquaculture", "sample_stale_days", 4)
		self.assertEqual(aquaculture.pond_batches()["sample_stale_days"], 4)
		self.assertEqual(aquaculture.feeding_mortality()["form"]["feed_types"][0], "Starter Crumble")

	def test_removed_constants(self):
		self.assertNotIn("FEED_TYPES", (ROOT / "api" / "aquaculture.py").read_text())
		src = (ROOT / "production" / "logic" / "aquaculture.py").read_text()
		self.assertNotIn("\nBANDS = ", src)


class TestFvLimits(Isolated):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		fv_seed.ensure_limits()

	def test_weekly_target_variety_then_crop(self):
		crop = "Fruits & Vegetables"
		self.assertEqual(fv.weekly_target_mm(), 25.0)
		frappe.db.set_value("Production Crop", crop, "irrigation_mm_week", 30)
		self.assertEqual(fv.weekly_target_mm(), 30.0)
		variety = frappe.db.get_value("Production Variety", {"crop": crop}, "name")
		frappe.db.set_value("Production Variety", variety, "irrigation_mm_week", 18)
		self.assertEqual(fv.weekly_target_mm(variety), 18.0)
		frappe.db.set_value("Production Variety", variety, "irrigation_mm_week", 0)
		self.assertEqual(fv.weekly_target_mm(variety), 30.0)

	def test_irrigation_payload_target_and_bands(self):
		r = fv.irrigation()
		self.assertEqual(r["target"]["weekly_mm"], 25.0)
		self.assertIn("Irrigation % of target", r["bands"])
		frappe.db.set_value("Production Crop", "Fruits & Vegetables", "irrigation_mm_week", 50)
		self.assertEqual(fv.irrigation()["target"]["weekly_mm"], 50.0)

	def test_slice_target_follows_its_variety(self):
		pivots = [{"name": "PV", "area_ha": 10, "slices": [{"name": "PV-1", "area_ha": 5, "item": "X"}, {"name": "PV-2", "area_ha": 5, "item": "X"}]}]
		from frappe.utils import getdate
		a = fv.compute_irrigation([], pivots, getdate("2026-10-12"), getdate("2026-10-25"), 25.0, {"PV-2": 10.0})
		self.assertEqual(a["target_mm"], 50.0)
		self.assertEqual(a["slice_target_mm"], {"PV-1": 50.0, "PV-2": 20.0})

	def test_grades_from_the_crop_table(self):
		crop = frappe.get_doc("Production Crop", "Fruits & Vegetables")
		grades = fv.grade_rules("Fruits & Vegetables")
		self.assertEqual([g["grade"] for g in grades][:5], ["Class 1", "Class 2", "Ware", "Seed", "Chats"])
		self.assertTrue(fv.is_top_grade("class 1", grades))
		self.assertTrue(fv.is_top_grade("Premium", grades))
		self.assertFalse(fv.is_top_grade("Ware", grades))
		self.assertFalse(fv.is_top_grade("Class 1", []))
		self.assertEqual(fv.grading()["form"]["default_grades"][:3], ["Class 1", "Class 2", "Ware"])
		crop.grades[1].is_top_grade = 1  # Class 2 now counts as top
		crop.save()
		self.assertTrue(fv.is_top_grade("Class 2", fv.grade_rules("Fruits & Vegetables")))

	def test_grading_order_follows_rank(self):
		from frappe.utils import getdate
		logs = [{"unit": "B1", "item": "P", "grading_date": "2026-10-14", "received_kg": 100, "rejects_kg": 0, "reject_reason": None,
				 "lines": [{"grade": "Ware", "kg": 10}, {"grade": "Class 2", "kg": 30}, {"grade": "Class 1", "kg": 60}]}]
		grades = [{"grade": "Class 1", "rank": 1, "is_top": True}, {"grade": "Class 2", "rank": 2, "is_top": False}, {"grade": "Ware", "rank": 3, "is_top": False}]
		g = fv.compute_grading(logs, getdate("2026-10-12"), getdate("2026-10-25"), grades)
		self.assertEqual(g["grades"], ["Class 1", "Class 2", "Ware"])
		self.assertEqual(g["kpis"]["class1_pct"], 60.0)

	def test_removed_constants(self):
		src = (ROOT / "api" / "fv.py").read_text()
		for name in ("DEFAULT_WEEKLY_TARGET_MM", "GRADE_ORDER", "TOP_GRADES", "irrigation_target_mm_week"):
			self.assertNotIn(name, src)
