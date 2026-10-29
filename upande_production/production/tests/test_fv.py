import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate

from upande_production.api import fv

PIVOTS = [{"name": "PV", "area_ha": 10, "slices": [{"name": "PV-1", "area_ha": 5, "item": "X"}, {"name": "PV-2", "area_ha": 5, "item": "X"}]}]


def _run(start, hours, depth, slices=None, fault="None"):
	return {"unit": "PV", "start_time": start, "end_time": start, "hours": hours, "depth_mm": depth, "fault": fault, "slices": slices or []}


class TestFvPure(IntegrationTestCase):
	def test_irrigation_rollup(self):
		frm, to = getdate("2026-10-12"), getdate("2026-10-25")  # two weeks
		runs = [_run("2026-10-13 06:00:00", 10, 12), _run("2026-10-20 06:00:00", 6, 8, ["PV-1"], "Pressure drop")]
		a = fv.compute_irrigation(runs, PIVOTS, frm, to, 25.0)
		self.assertEqual(a["target_mm"], 50.0)
		self.assertEqual(a["mm_by_slice"], {"PV-1": 20.0, "PV-2": 12.0})  # no slices listed = whole pivot
		self.assertEqual(a["per_pivot"]["PV"]["runs"], 2)
		self.assertEqual(a["per_pivot"]["PV"]["faults"], 1)
		self.assertEqual(a["per_pivot"]["PV"]["hours"], 16)
		self.assertEqual(a["weekly"]["2026-10-12"]["runs"], 1)

	def test_grading_rollup(self):
		logs = [
			{"unit": "B1", "item": "Potatoes", "grading_date": "2026-10-14", "received_kg": 1000, "rejects_kg": 50,
			 "reject_reason": "Rot", "lines": [{"grade": "Class 1", "kg": 600}, {"grade": "Class 2", "kg": 350}]},
			{"unit": "B2", "item": "Potatoes", "grading_date": "2026-10-21", "received_kg": 500, "rejects_kg": 25,
			 "reject_reason": "Greening", "lines": [{"grade": "Class 1", "kg": 200}, {"grade": "Ware", "kg": 275}]},
		]
		grades = [{"grade": "Class 1", "rank": 1, "is_top": True}, {"grade": "Class 2", "rank": 2, "is_top": False},
				  {"grade": "Ware", "rank": 3, "is_top": False}]
		g = fv.compute_grading(logs, getdate("2026-10-12"), getdate("2026-10-25"), grades)
		k = g["kpis"]
		self.assertEqual(k["graded_kg"], 1425.0)
		self.assertEqual(k["class1_pct"], round(800 / 1425 * 100, 1))
		self.assertEqual(k["reject_pct"], 5.0)
		self.assertEqual(k["top_reject_reason"], "Rot")
		self.assertEqual(g["grades"], ["Class 1", "Class 2", "Ware"])
		self.assertEqual(g["by_item"][0]["grades"]["Class 1"], 800.0)
		self.assertEqual([s["graded_kg"] for s in g["series"]], [950.0, 475.0])


class TestFvDocs(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.pivot = frappe.db.get_value("Production Unit", {"unit_type": "Pivot"}, "name")
		cls.slice = frappe.db.get_value("Production Unit", {"parent_production_unit": cls.pivot}, "name")

	def test_run_hours_and_validation(self):
		if not self.pivot:
			self.skipTest("no pivot on this site")
		data = {"unit": self.pivot, "start_time": "2026-10-20 06:00:00", "end_time": "2026-10-20 14:30:00", "depth_mm": 12, "slices": [self.slice]}
		doc = fv.build_run(data)
		doc.insert()
		self.assertEqual(doc.hours, 8.5)
		with self.assertRaises(frappe.ValidationError):
			fv.build_run({**data, "end_time": "2026-10-20 05:00:00"}).insert()
		with self.assertRaises(frappe.ValidationError):
			fv.build_run({**data, "slices": ["Pond 1"]}).insert()
		with self.assertRaises(frappe.ValidationError):
			fv.build_run({"unit": self.pivot}).insert()

	def test_grading_validation(self):
		if not self.slice:
			self.skipTest("no block on this site")
		data = {"unit": self.slice, "grading_date": "2026-10-20", "received_kg": 1000, "rejects_kg": 40, "reject_reason": "Rot",
				"lines": [{"grade": "Class 1", "kg": 700, "crates": 14}, {"grade": "Class 2", "kg": 250}]}
		doc = fv.build_grading(data)
		doc.insert()
		self.assertEqual(doc.graded_kg, 950)
		with self.assertRaises(frappe.ValidationError):  # more graded than received
			fv.build_grading({**data, "received_kg": 900}).insert()
		with self.assertRaises(frappe.ValidationError):  # rejects need a reason
			fv.build_grading({**data, "reject_reason": None}).insert()
		with self.assertRaises(frappe.ValidationError):  # no lines
			fv.build_grading({**data, "lines": []}).insert()

	def test_endpoints_return_shape(self):
		i = fv.irrigation("2026-09-01", "2026-10-28")
		self.assertNotIn("error", i)
		self.assertIn("kpis", i)
		g = fv.grading("2026-09-01", "2026-10-28")
		self.assertNotIn("error", g)
		self.assertIn("by_item", g)
