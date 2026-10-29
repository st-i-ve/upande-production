"""Shape and key numbers for the avocado page endpoints (api/avocado.py).

Runs against the demo data from production/demo/avocado_seed.py, which is idempotent:
setUpClass calls it without committing, so a fresh site gets it for the length of
the run and a seeded site is left as it was. Numbers are asserted against the seed's
own DEMO dict, not against literals. The blocks are the surveyed Phase 1 / Phase 2 units; the
bearing ones ("active") carry the history, harvests, dry matter and counts.
"""

import contextlib
from unittest import mock

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import nowdate

from upande_production.api import avocado as api
from upande_production.production.demo import avocado_seed
from upande_production.production.demo.avocado_seed import DEMO


def _active():
	"""Codes of the blocks with a delivered history (the seed's active, bearing blocks)."""
	return set(DEMO["history"])


def _batch_kg():
	"""Estimated kg that Harvest Batches on avocado blocks (the harvest app) wrote into the logs this season."""
	return sum(r.total_kg for r in frappe.get_all("Avocado Harvest Log", filters={"client_ref": ("like", "harvest-batch:%"),
		"harvest_date": ("between", [f"{DEMO['season']}-01-01", f"{DEMO['season']}-12-31"])},
		fields=["total_kg", "orchard_block"]) if r.orchard_block in DEMO["blocks"])  # retired blocks never show


def _early_total():
	return sum(parts[(DEMO["season"], "Early")][0]
			   for parts in DEMO["history"].values() if (DEMO["season"], "Early") in parts)


@contextlib.contextmanager
def _scratch_block(code="ZT"):
	"""A throwaway block for write tests, so the seeded blocks' numbers never move."""
	doc = frappe.get_doc({"doctype": "Avocado Yield Block", "block_code": code, "farm": DEMO["farm"],
						  "status": "Active", "planting_year": 2024, "area_ha": 1, "live_trees": 10}).insert(
		ignore_permissions=True)
	try:
		yield doc.name
	finally:
		for dt, field in avocado_seed.BLOCK_CHILDREN.items():
			for n in frappe.get_all(dt, filters={field: doc.name}, pluck="name"):
				frappe.delete_doc(dt, n, force=True, ignore_permissions=True)
		frappe.delete_doc("Avocado Yield Block", doc.name, force=True, ignore_permissions=True)


class TestAvocadoApi(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		avocado_seed.run(commit=False)

	def setUp(self):
		# save_readings commits on its own; the run's writes must stay uncommitted so the
		# class rollback removes them. Writes go to block C (young, never forecasts), so
		# the other tests' numbers do not depend on test order.
		patcher = mock.patch.object(frappe.db, "commit", lambda *a, **k: None)
		patcher.start()
		self.addCleanup(patcher.stop)

	def test_production_forecast_shape_and_numbers(self):
		r = api.production_forecast()
		self.assertNotIn("error", r)
		self.assertEqual(r["season"], DEMO["season"])
		self.assertEqual(set(r["views"]), {"manual", "automatic"})
		auto, manual = r["views"]["automatic"], r["views"]["manual"]
		self.assertEqual(
			[c["key"] for c in auto["cards"]],
			["forecast", "grade_1", "value", "bearing", "counted_blocks", "next_6_weeks", "losing"])
		self.assertEqual(manual["cards"][4]["key"], "manual_entries")
		self.assertGreater(auto["total_kg"], 0)
		self.assertAlmostEqual(auto["total_value_kes"], auto["total_kg"] * r["price_per_kg"], delta=1)
		self.assertAlmostEqual(auto["grade_1_share"], DEMO["harvest"]["grade_1"], delta=0.05)
		# typed forecasts: one per active block
		self.assertEqual(manual["manual_entries"], len(DEMO["typed_forecasts"]))
		self.assertEqual(manual["total_kg"], sum(DEMO["typed_forecasts"].values()))
		# season budget is the sum of its months
		self.assertTrue(r["budget"]["set"])
		self.assertEqual(r["budget"]["budget_kg"], sum(m["budget_kg"] for m in r["budget"]["months"]))
		self.assertEqual(r["budget"]["months_total_kg"], r["budget"]["budget_kg"])
		self.assertEqual(manual["vs_budget"]["diff_kg"], manual["total_kg"] - r["budget"]["budget_kg"])
		# the automatic forecast is the late crop only: budget is compared with delivered + on the trees
		vb = auto["vs_budget"]
		self.assertEqual(vb["delivered_kg"], _early_total())
		self.assertEqual(vb["outturn_kg"], _early_total() + auto["total_kg"])
		self.assertEqual(vb["diff_kg"], vb["outturn_kg"] - r["budget"]["budget_kg"])
		# months come from the harvest logs minus the mis-keyed row, so they sum to the delivered figure
		# plus any Harvest Batch estimates (the harvest app writes a log row per batch)
		self.assertEqual(sum(m["delivered_kg"] for m in r["budget"]["months"]), _early_total() + _batch_kg())
		# estimate vs delivered scored per block off the early crop
		e = r["estimate_vs_delivered"]
		self.assertEqual(e["basis"], "block")
		self.assertEqual(e["delivered_kg"], _early_total())
		self.assertEqual(e["estimated_kg"], sum(DEMO["early_estimates"].values()))
		self.assertIn(e["best"]["block"], _active())
		self.assertIn(e["weakest"]["block"], _active())
		self.assertGreaterEqual(e["best"]["pct_of_estimate"], e["weakest"]["pct_of_estimate"])
		years = {y["planting_year"]: y for y in r["by_planting_year"]}
		planted = {}
		for code in _active():
			y = DEMO["blocks"][code]["planting_year"]
			planted[y] = planted.get(y, 0) + 1
		self.assertEqual(set(years), set(planted))
		for y, n in planted.items():
			self.assertEqual(years[y]["blocks_picked"], n)
		# yield curve measured for the 7-9 band from the harvest logs
		band = next(c for c in r["yield_curve"] if c["label"] == "7-9")
		self.assertEqual(band["basis"], "harvested")
		# schedule, losses, maturity, gaps
		self.assertGreater(r["schedule"]["next_6_weeks_kg"], 0)
		self.assertEqual(r["schedule"]["unscheduled"], [])
		self.assertTrue(r["losses"]["rows"])
		self.assertEqual(r["losses"]["lost_kg"], sum(x["lost_kg"] for x in r["losses"]["rows"]))
		by_block = {b["block"]: b for b in r["maturity"]["blocks"]}
		self.assertEqual(set(by_block), set(DEMO["dry_matter"]))  # the sampled blocks
		self.assertTrue(any(b["ready"] for b in by_block.values()))
		self.assertFalse(all(b["ready"] for b in by_block.values()))

	def test_farm_filter_and_unknown_farm(self):
		r = api.production_forecast(farm=DEMO["farm"])
		self.assertEqual(r["header"]["blocks"], len(DEMO["blocks"]))
		empty = api.production_forecast(farm="No Such Farm")
		self.assertEqual(empty["header"]["blocks"], 0)
		self.assertEqual(empty["views"]["automatic"]["total_kg"], 0)

	def test_season_outlook(self):
		r = api.season_outlook(crew_available=DEMO["crew_available"])
		self.assertNotIn("error", r)
		self.assertEqual([k["key"] for k in r["kpis"]],
						 ["season_crop", "crop_value", "ready_to_pick", "crew_next_week",
						  "estimate_accuracy", "stale_readings"])
		k = {x["key"]: x for x in r["kpis"]}
		self.assertEqual(k["season_crop"]["delivered_kg"], _early_total())
		ready = api.dry_matter()["summary"]["ready"]
		self.assertGreater(ready, 0)
		self.assertEqual(k["ready_to_pick"]["value"], ready)  # the blocks at or over the floor
		self.assertEqual(k["stale_readings"]["value"], 0)
		self.assertEqual(k["crew_next_week"]["crew_available"], DEMO["crew_available"])
		# timeline: picked early-crop weeks then forecast weeks, gaps filled
		weeks = r["timeline"]["weeks"]
		self.assertGreater(sum(w["picked_kg"] for w in weeks), 0)
		self.assertGreater(sum(w["forecast_kg"] for w in weeks), 0)
		self.assertEqual(r["timeline"]["picked_kg"], sum(w["picked_kg"] for w in weeks))
		# cohort: the 2018 planting is the sampled blocks planted that year, near the floor on average
		c = next(c for c in r["dry_matter"]["cohorts"] if c["planting_year"] == 2018)
		self.assertEqual(sorted(c["blocks"]), sorted(b for b in DEMO["dry_matter"] if DEMO["blocks"][b]["planting_year"] == 2018))
		self.assertTrue(21 < c["dry_matter_pct"] < 26, c["dry_matter_pct"])
		self.assertEqual(r["treemap"]["with_crop"], len(_active()))
		self.assertEqual(r["treemap"]["without_crop"], len(DEMO["blocks"]) - len(_active()))  # young blocks
		self.assertEqual(len(r["treemap"]["bands"]), 5)
		self.assertEqual({b["block"] for b in r["map"]["blocks"]}, set(DEMO["blocks"]))  # outlines copied from the units
		self.assertEqual(r["map"]["without_boundary"], 0)
		self.assertTrue(r["pickers"]["rows"])
		self.assertEqual(api.season_outlook(crew_available=500)["pickers"]["weeks_short"], 0)  # a big crew covers the peak
		self.assertGreater(api.season_outlook(crew_available=4)["pickers"]["weeks_short"], 0)
		self.assertLessEqual(len(r["alerts"]), 5)
		self.assertEqual(r["undated"]["blocks"], [])

	def test_harvest_calendar(self):
		r = api.harvest_calendar()
		self.assertNotIn("error", r)
		self.assertEqual(r["kg_per_crate"], frappe.db.get_value("Production Crop", "Avocado", "avg_kg_per_crate"))
		states = {b["block"]: b["state"] for b in r["blocks"]}
		self.assertEqual(set(states), _active())
		self.assertTrue({"ready", "waiting"} <= set(states.values()))
		a = next(b for b in r["blocks"] if b["state"] == "ready")
		self.assertEqual(len(a["cells"]), len(r["weeks"]))
		self.assertAlmostEqual(a["row_kg"], a["expected_kg"], delta=len(r["weeks"]))
		locked = [b for b in r["blocks"] if b["state"] == "waiting" and b["cells"][0]["kind"] == "locked"]
		self.assertTrue(locked)  # under 24% until it crosses
		ready = sum(1 for s in states.values() if s == "ready")
		self.assertEqual(r["kpis"]["pickable_now"], {"blocks": ready, "of": len(states), "minimum_pct": 24.0})
		self.assertEqual(r["no_pick_date"], [])
		# the young plantings bear nothing yet, so they carry no forecast
		self.assertEqual({x["block"] for x in r["no_forecast"]}, set(DEMO["blocks"]) - _active())
		self.assertTrue(all(x["reason"] == "not_bearing" for x in r["no_forecast"]))
		self.assertEqual(sum(w["kg"] for w in r["weeks"]), r["summary"]["total_kg"])
		self.assertEqual(sum(1 for w in r["weeks"] if w["is_peak"]), 1)
		# filters
		only = api.harvest_calendar(planting_year=2018)
		self.assertEqual({x["block"] for x in only["blocks"]},
						 {c for c in _active() if DEMO["blocks"][c]["planting_year"] == 2018})
		self.assertEqual(only["filters"]["planting_years"], r["filters"]["planting_years"])
		self.assertEqual(only["no_forecast"], [])

	def test_picking_plan(self):
		r = api.picking_plan(crew_available=DEMO["crew_available"])
		self.assertNotIn("error", r)
		self.assertTrue(r["weeks"])
		self.assertEqual(r["kpis"]["weeks_short"]["weeks"], sum(1 for w in r["weeks"] if w["status"] == "short"))
		w = r["week_detail"]
		self.assertEqual(w["week"], r["focus_week"])
		self.assertAlmostEqual(sum(b["kg"] for b in w["by_block"]), w["kg"], delta=len(w["by_block"]))
		self.assertTrue(all(b["measured"] for b in w["by_block"]))
		lo, hi = 450, 650
		for rate in r["rates"]["blocks"]:
			self.assertTrue(lo <= rate["kg_per_picker_day"] <= hi, rate)
		self.assertEqual(len(r["rejected_records"]), 1)
		self.assertEqual(r["unscheduled"], [])
		# a chosen week opens that week
		last = r["weeks"][-1]["week"]
		self.assertEqual(api.picking_plan(week=last)["focus_week"], last)

	def test_dry_matter(self):
		r = api.dry_matter()
		self.assertNotIn("error", r)
		s = r["summary"]
		self.assertEqual(s["blocks"], len(DEMO["blocks"]))
		self.assertEqual(s["ready"] + s["rising"] + s["stale"] + s["never_sampled"], s["blocks"])
		self.assertEqual(s["never_sampled"], len(DEMO["blocks"]) - len(DEMO["dry_matter"]))  # sampled blocks only
		sampled = [b for b in r["blocks"] if b["state"] != "never_sampled"]
		self.assertEqual({b["block"] for b in sampled}, set(DEMO["dry_matter"]))
		a = next(b for b in r["blocks"] if b["state"] == "ready")
		self.assertGreaterEqual(a["dry_matter_pct"], 24.0)
		self.assertEqual(len(a["trend"]), DEMO["dm_visits"])
		self.assertLess(a["trend"][0]["dry_matter_pct"], a["trend"][-1]["dry_matter_pct"])
		b = next(b for b in r["blocks"] if b["state"] == "rising")
		self.assertGreater(b["weeks_to_minimum"], 0)
		self.assertTrue(r["recent_visits"])
		self.assertEqual(r["form"]["sizes"][0]["count"], 14)
		first = next(iter(DEMO["dry_matter"]))
		one = api.dry_matter(block=first)
		self.assertTrue(all(v["where"] == first for v in one["recent_visits"]))
		# the cycle's stage on each test, and which blocks are due for sampling
		self.assertTrue(all("stage" in v for v in r["recent_visits"]))
		self.assertEqual(s["due"], sum(1 for b in r["blocks"] if b["sampling"] == "due"))
		young = next(b for b in r["blocks"] if b["block"] not in DEMO["history"])
		self.assertEqual(young["sampling"], "no_cycle")  # a young planting has no open cycle
		for b in sampled:
			self.assertIsNotNone(b["stage"], b["block"])
			self.assertEqual(b["sample_from_stage"], "Maturity")

	def test_dry_matter_preview_and_save(self):
		p = api.dry_matter_preview([{"count_size": 14, "moisture": 0.77}, {"count_size": 16, "moisture": 70}])
		self.assertEqual([s["dry_matter_pct"] for s in p["sizes"]], [23.0, 30.0])
		self.assertEqual([s["window"] for s in p["sizes"]], ["under", "in"])
		self.assertEqual(p["average_dry_matter_pct"], 26.5)
		with _scratch_block() as code:
			saved = api.save_dry_matter(
				readings=[{"count_size": 14, "moisture": 0.75}, {"count_size": 16, "moisture": ""}],
				orchard_block=code, week_number=44, test_date=nowdate())
			self.assertNotIn("error", saved)
			self.assertEqual(len(saved["saved"]), 1)
			self.assertEqual(saved["saved"][0]["dry_matter_pct"], 25.0)
			self.assertIn("error", api.save_dry_matter(readings=[], orchard_block=code, week_number=44))

	def test_writes(self):
		self.assertEqual(api.set_forecast_mode("auto")["mode"], "automatic")
		self.assertEqual(api.production_forecast()["mode"], "automatic")
		self.assertEqual(api.set_forecast_mode("manual")["mode"], "manual")
		# the price is the estate's: saved on the crop, not per user
		self.assertEqual(api.save_price_per_kg(110)["price_per_kg"], 110)
		self.assertEqual(frappe.db.get_value("Production Crop", "Avocado", "price_per_kg"), 110)
		self.assertEqual(api.production_forecast()["price_per_kg"], 110)
		self.assertEqual(api.production_forecast(price_per_kg=120)["price_per_kg"], 120)  # a session try
		self.assertEqual(frappe.db.get_value("Production Crop", "Avocado", "price_per_kg"), 110)
		# manual forecast upserts: a second save for the same block updates, not duplicates
		with _scratch_block() as code:
			first = api.save_manual_forecast(code, 1234, season=DEMO["season"], crop="Whole Season")
			again = api.save_manual_forecast(code, 2345, season=DEMO["season"], crop="Whole Season")
		self.assertTrue(first["created"])
		self.assertFalse(again["created"])
		self.assertEqual(first["name"], again["name"])
		bud = api.save_season_budget(2031, months=[{"month": "May", "budget_kg": 1000},
												   {"month": "June", "budget_kg": 2500}],
									 budget_price_per_kg=100)
		self.assertEqual(bud["budget_kg"], 3500)
		self.assertEqual(api.production_forecast(season=2031)["budget"]["budget_value"], 350000)
		# refusals come last: the envelope rolls the transaction back on an error
		self.assertIn("error", api.save_price_per_kg("abc"))
		self.assertIn("error", api.save_manual_forecast("ZZ", 10))
		self.assertIn("error", api.save_season_budget(2031, months=[]))

	def test_permission_envelope(self):
		frappe.set_user("Guest")
		try:
			for fn in (api.production_forecast, api.season_outlook, api.harvest_calendar,
					   api.picking_plan, api.dry_matter):
				self.assertIn("error", fn())
			self.assertIn("error", api.save_manual_forecast("A", 1))
		finally:
			frappe.set_user("Administrator")
