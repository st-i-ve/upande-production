"""Apiary desk + mobile endpoints, run against production/demo/apiary_seed.py (idempotent)."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, flt, nowdate

from upande_production.api import apiary as api
from upande_production.production.demo import apiary_seed
from upande_production.production.demo.apiary_seed import DEMO

NORTH, SOUTH = "Hive Group North", "Hive Group South"


def _rng():
	return str(add_days(nowdate(), -400)), nowdate()


class TestApiary(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		apiary_seed.run(commit=False)

	def test_inspection_kpis_and_groups(self):
		r = api.hive_inspections(*_rng())
		self.assertNotIn("error", r)
		k = r["kpis"]
		per_group = DEMO["inspection_weeks"] * 7 // DEMO["inspection_every_days"] + 1
		self.assertEqual(k["inspections"], per_group * len(DEMO["groups"]))
		self.assertEqual(r["threshold"], 3.0)
		by = {g["unit"]: g for g in r["groups"]}
		self.assertEqual(by[NORTH]["mite_status"], "high")  # rising mites ends over 3
		self.assertEqual(by[SOUTH]["mite_status"], "ok")
		self.assertEqual(k["colonies_above_threshold"], DEMO["groups"][NORTH]["colonies"])
		self.assertEqual(len(by[NORTH]["trend"]), per_group)
		self.assertGreater(by[NORTH]["trend"][-1]["mites"], by[NORTH]["trend"][0]["mites"])
		self.assertEqual(k["disease_flags"], len(DEMO["groups"][NORTH]["disease"]))

	def test_queenless_event_is_visible_in_the_trend(self):
		r = api.hive_inspections(*_rng(), unit=SOUTH)
		pcts = [t["queenright_pct"] for t in r["groups"][0]["trend"]]
		self.assertLess(min(pcts), 100)
		self.assertEqual(pcts[-1], 100.0)
		self.assertEqual(len(r["groups"]), 1)

	def test_weekly_series_has_no_holes(self):
		r = api.hive_inspections(str(add_days(nowdate(), -84)), nowdate())
		weeks = [s["week"] for s in r["series"]]
		self.assertEqual(len(weeks), len(set(weeks)))
		for a, b in zip(weeks, weeks[1:]):
			self.assertEqual(str(add_days(a, 7)), b)

	def test_save_inspection_validates(self):
		unit = frappe.db.get_value("Production Unit", {"unit_name": NORTH}, "name")
		bad = api.save_hive_inspection({"unit": unit, "colonies_inspected": 5, "colonies_queenright": 6})
		self.assertIn("queenright", bad["error"])
		self.assertIn("error", api.save_hive_inspection({"unit": unit, "colonies_inspected": 0}))
		self.assertIn("error", api.save_hive_inspection({"unit": unit, "colonies_inspected": 5,
														 "inspection_date": str(add_days(nowdate(), 3))}))
		self.assertIn("error", api.save_hive_inspection({"unit": "Nope", "colonies_inspected": 5}))
		ok = api.save_hive_inspection({"unit": unit, "colonies_inspected": 4, "colonies_queenright": 4,
									   "varroa_per_100": "2.5", "inspection_date": nowdate()})
		self.assertTrue(ok["ok"])
		self.assertEqual(flt(frappe.db.get_value("Hive Inspection Log", ok["name"], "varroa_per_100")), 2.5)

	def test_honey_kpis_match_seed(self):
		r = api.honey_harvest(*_rng())
		total = sum(h[3] for rows in DEMO["harvests"].values() for h in rows)
		self.assertAlmostEqual(r["kpis"]["kg"], total, places=1)
		colonies = sum(g["colonies"] for g in DEMO["groups"].values())
		self.assertAlmostEqual(r["kpis"]["kg_per_hive"], total / colonies, places=1)
		self.assertTrue(0 < r["kpis"]["grade_a_pct"] < 100)
		self.assertAlmostEqual(sum(s["kg"] for s in api.honey_harvest(str(add_days(nowdate(), -300)), nowdate())["series"]), total, places=1)
		self.assertEqual({g["unit"] for g in r["groups"]}, {NORTH, SOUTH})

	def test_honey_agrees_with_production_harvest(self):
		r = api.honey_harvest(*_rng())
		ph = frappe.db.sql(
			"select sum(qty) from `tabProduction Harvest` where crop='Apiary' and harvest_date between %s and %s",
			_rng(),
		)[0][0]
		self.assertAlmostEqual(flt(ph), r["kpis"]["kg"], places=1)

	def test_save_harvest_mirrors_edits_and_deletes(self):
		unit = frappe.db.get_value("Production Unit", {"unit_name": SOUTH}, "name")
		ok = api.save_honey_harvest({"unit": unit, "honey_kg": 12.5, "moisture_pct": 18, "grade": "B"})
		doc = frappe.get_doc("Honey Harvest Log", ok["name"])
		ph = frappe.get_doc("Production Harvest", doc.production_harvest)
		self.assertEqual((ph.crop, ph.qty, ph.uom), ("Apiary", 12.5, "Kg"))
		doc.honey_kg = 20
		doc.save()
		self.assertEqual(frappe.db.get_value("Production Harvest", ph.name, "qty"), 20)
		doc.delete()
		self.assertFalse(frappe.db.exists("Production Harvest", ph.name))

	def test_save_harvest_validates(self):
		unit = frappe.db.get_value("Production Unit", {"unit_name": SOUTH}, "name")
		self.assertIn("error", api.save_honey_harvest({"unit": unit, "honey_kg": 0}))
		self.assertIn("error", api.save_honey_harvest({"unit": unit, "honey_kg": 5, "moisture_pct": 70}))

	def test_viewer_cannot_write(self):
		user = "apiary-viewer@example.com"
		if not frappe.db.exists("User", user):
			frappe.get_doc({"doctype": "User", "email": user, "first_name": "Viewer",
							"roles": [{"role": "Production Viewer"}]}).insert(ignore_permissions=True)
		frappe.set_user(user)
		try:
			self.assertNotIn("error", api.hive_inspections(*_rng()))
			unit = frappe.db.get_value("Production Unit", {"unit_name": SOUTH}, "name")
			self.assertIn("error", api.save_honey_harvest({"unit": unit, "honey_kg": 5}))
		finally:
			frappe.set_user("Administrator")

	def test_mobile_endpoints(self):
		from unittest import mock

		from upande_production.mobile import apiary as m

		unit = frappe.db.get_value("Production Unit", {"unit_name": NORTH}, "name")
		with mock.patch.object(m, "_payload", return_value={"unit": unit, "colonies_inspected": 3,
															"colonies_queenright": 3}), \
				mock.patch.object(frappe.db, "commit"):
			m.apiaryRecordInspection()
			self.assertEqual(frappe.response["data"]["status"], "success")
		with mock.patch.object(m, "_payload", return_value={"unit": unit}):
			m.apiaryRecordHarvest()
			self.assertIn("error", frappe.response["data"])
		m.apiaryListHiveGroups()
		self.assertEqual(len(frappe.response["data"]["groups"]), 2)
