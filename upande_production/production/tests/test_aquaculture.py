from unittest import mock

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, nowdate

from upande_production.api import aquaculture as api
from upande_production.production.logic import aquaculture as logic


def _batch(**kw):
	b = {"stocked": 1000, "w0_g": 10, "start": "2026-01-01", "deaths": [], "samples": [], "feeds": [],
		 "harvested": 0, "harvest_date": None, "harvest_kg": 0}
	b.update(kw)
	return b


class TestAquaculturePure(IntegrationTestCase):
	def test_survival(self):
		self.assertEqual(logic.survival_pct(1000, 50), 95.0)
		self.assertEqual(logic.survival_pct(1000, 0), 100.0)
		self.assertIsNone(logic.survival_pct(0, 0))

	def test_fcr(self):
		# 1000 fish x 10 g = 10 kg start; now 900 x 110 g = 99 kg: gain 89 kg; 133.5 kg feed -> 1.5
		self.assertEqual(logic.fcr(133.5, 99, 10), 1.5)
		self.assertIsNone(logic.fcr(100, 10, 10))   # no gain yet
		self.assertIsNone(logic.fcr(0, 99, 10))     # no feed recorded

	def test_state_counts_live_fish(self):
		b = _batch(deaths=[("2026-01-05", 40), ("2026-02-01", 10)], samples=[("2026-01-20", 50.0), ("2026-02-10", 110.0)],
				   feeds=[("2026-01-02", 20), ("2026-02-02", 30)])
		s = logic.state_at(b, "2026-01-31")
		self.assertEqual((s["live"], s["dead"], s["avg_weight_g"], s["feed_kg"]), (960, 40, 50.0, 20))
		s = logic.state_at(b, "2026-03-01")
		self.assertEqual((s["live"], s["survival_pct"], s["biomass_kg"], s["feed_kg"]), (950, 95.0, 104.5, 50))

	def test_harvested_fish_leave_the_live_count_not_survival(self):
		b = _batch(deaths=[("2026-01-05", 100)], harvested=900, harvest_date="2026-03-01", harvest_kg=270)
		self.assertEqual(logic.state_at(b, "2026-02-28")["live"], 900)
		s = logic.state_at(b, "2026-03-02")
		self.assertEqual((s["live"], s["harvested"], s["survival_pct"]), (0, 900, 90.0))
		self.assertEqual(s["harvest_kg"], 270)

	def test_growth_and_projection(self):
		b = _batch(samples=[("2026-01-08", 17.0), ("2026-01-15", 24.0)], target_g=45, target_date="2026-02-20")
		m = logic.batch_metrics(b, "2026-01-15")
		self.assertEqual(m["growth_g_day"], 1.0)
		self.assertEqual(m["days_to_target"], 21)
		self.assertEqual(m["projected_harvest_date"], "2026-02-05")
		self.assertTrue(m["on_track"])
		self.assertEqual(m["projected_weight_g"], 60.0)
		self.assertEqual(m["days_in_water"], 14)

	def test_bands(self):
		ok = {"dissolved_oxygen_mg_l": 4.0, "ph": 6.5, "temperature_c": 30.0, "ammonia_mg_l": 0.49}
		self.assertEqual(logic.reading_flags(ok), [])
		bad = {"dissolved_oxygen_mg_l": 3.9, "ph": 8.6, "temperature_c": 24.9, "ammonia_mg_l": 0.5}
		self.assertEqual({f["metric"] for f in logic.reading_flags(bad)}, {"do", "ph", "temp", "ammonia"})
		self.assertEqual(logic.reading_flags({"dissolved_oxygen_mg_l": None}), [])


class TestAquacultureApi(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		if not frappe.db.exists("Production Crop", "Aquaculture"):
			frappe.get_doc({"doctype": "Production Crop", "crop_name": "Aquaculture", "crop_key": "aquaculture",
							"unit_label": "Pond", "yield_uom": "Kg"}).insert()
		cls.pond = frappe.get_doc({"doctype": "Production Unit", "unit_name": "TEST Pond A", "crop": "Aquaculture",
								   "unit_type": "Pond", "status": "Active"}).insert().name

	def setUp(self):
		# `run` rolls back on a refusal; keep the rest of the test's uncommitted rows (rolled back at class end).
		p = mock.patch.object(frappe.db, "rollback")
		p.start()
		self.addCleanup(p.stop)
		for dt in ("Pond Stocking", "Water Quality Reading", "Pond Feeding Log", "Fish Mortality Log", "Fish Sampling Log", "Production Harvest"):
			frappe.db.delete(dt, {"pond" if dt != "Production Harvest" else "unit": self.pond})

	def test_batch_end_to_end(self):
		start = add_days(nowdate(), -20)
		r = api.save_stocking({"pond": self.pond, "species": "Tilapia", "stocking_date": start,
							   "fingerlings_count": 1000, "avg_weight_g": 10, "target_harvest_weight_g": 400,
							   "target_harvest_date": add_days(start, 180)})
		self.assertTrue(r["ok"])
		again = api.save_stocking({"pond": self.pond, "species": "Tilapia", "stocking_date": start,
								   "fingerlings_count": 10, "avg_weight_g": 10})
		self.assertIn("already has a growing batch", again["error"])
		api.save_feeding({"pond": self.pond, "feed_date": add_days(start, 5), "kg_fed": 60, "feeding_times": "06:00, 12:00"})
		api.save_feeding({"pond": self.pond, "feed_date": add_days(start, 10), "kg_fed": 75})
		api.save_mortality({"pond": self.pond, "mortality_date": add_days(start, 6), "dead_count": 50, "cause": "Low DO"})
		api.save_sampling({"pond": self.pond, "sample_date": add_days(start, 15), "sample_size": 30, "avg_weight_g": 110})
		b = [x for x in api.pond_batches(unit=self.pond)["batches"] if x["name"] == r["name"]][0]
		self.assertEqual((b["live"], b["survival_pct"], b["feed_kg"]), (950, 95.0, 135))
		self.assertEqual(b["biomass_kg"], 104.5)
		self.assertEqual(b["fcr"], 1.43)   # 135 / (104.5 - 10)
		self.assertEqual(b["days_in_water"], 20)
		self.assertEqual(len(b["growth_curve"]), 2)
		fm = api.feeding_mortality(unit=self.pond, from_date=start, to_date=nowdate())
		self.assertEqual(fm["causes"], [{"cause": "Low DO", "count": 50}])
		self.assertEqual(fm["ponds"][0]["feed_kg"], 135)

	def test_logs_link_to_the_growing_batch_and_validate(self):
		bad = api.save_mortality({"pond": self.pond, "dead_count": 0})
		self.assertIn("more than zero", bad["error"])
		avocado = frappe.db.get_value("Production Unit", {"crop": ("!=", "Aquaculture")}, "name")
		if avocado:
			self.assertIn("not an aquaculture pond", api.save_feeding({"pond": avocado, "kg_fed": 1})["error"])

	def test_water_reading_flags_and_alerts(self):
		ok = api.save_water_reading({"pond": self.pond, "dissolved_oxygen_mg_l": 6, "ph": 7.5, "temperature_c": 27, "ammonia_mg_l": 0.1})
		self.assertFalse(ok["out_of_band"])
		low = api.save_water_reading({"pond": self.pond, "dissolved_oxygen_mg_l": 2.5, "ph": 7.5})
		self.assertTrue(low["out_of_band"])
		self.assertIn("Dissolved oxygen", low["flags"])
		self.assertIn("at least one", api.save_water_reading({"pond": self.pond})["error"])
		w = api.water_quality(unit=self.pond)
		self.assertEqual(w["ponds"][0]["readings"], 2)
		self.assertEqual(w["ponds"][0]["status"], "alert")
		self.assertEqual([a["metric"] for a in w["alerts"]], ["do"])
		self.assertEqual(w["kpis"]["lowest_do_mg_l"]["value"], 2.5)

	def test_harvest_goes_to_production_harvest(self):
		start = add_days(nowdate(), -30)
		r = api.save_stocking({"pond": self.pond, "species": "Tilapia", "stocking_date": start,
							   "fingerlings_count": 500, "avg_weight_g": 10})
		h = api.save_fish_harvest({"stocking": r["name"], "harvest_date": nowdate(), "count": 500, "qty_kg": 150})
		self.assertEqual(h["status"], "Harvested")
		self.assertEqual(frappe.db.get_value("Production Harvest", {"unit": self.pond, "crop": "Aquaculture"}, "qty"), 150)
		b = [x for x in api.pond_batches(unit=self.pond)["batches"] if x["name"] == r["name"]][0]
		self.assertEqual((b["live"], b["harvest_kg"]), (0, 150))
