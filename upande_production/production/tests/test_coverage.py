import json

import frappe
from frappe.tests import IntegrationTestCase

from upande_production.api import coverage
from upande_production.api.coverage import progress_pct, unit_state


def _t(planned, done, status="Open", pending=0, late=False, uom="Kg"):
	return {"planned_qty": planned, "done_qty": done, "pending_qty": pending, "remaining_qty": max(planned - done, 0) if status != "Skipped" else 0,
		"status": status, "late": late, "uom": uom}


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


class TestCoveragePure(IntegrationTestCase):
	def test_states(self):
		self.assertEqual(unit_state([]), "no_work")
		self.assertEqual(unit_state([_t(5, 0, "Skipped")]), "no_work")
		self.assertEqual(unit_state([_t(5, 5, "Done"), _t(3, 0, "Skipped")]), "done")
		self.assertEqual(unit_state([_t(5, 0)]), "not_started")
		self.assertEqual(unit_state([_t(5, 2)]), "partial")
		self.assertEqual(unit_state([_t(5, 0, "In Progress")]), "partial")
		self.assertEqual(unit_state([_t(5, 0, pending=5)]), "pending_approval")
		self.assertEqual(unit_state([_t(5, 5, "Done"), _t(5, 1, late=True, pending=2)]), "late")

	def test_progress_caps_and_averages(self):
		self.assertEqual(progress_pct([_t(10, 5), _t(4, 8)]), 75.0)
		self.assertEqual(progress_pct([]), 0.0)


class TestCoverageMap(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		for u in ("Kg", "Bed"):
			if not frappe.db.exists("UOM", u):
				_make("UOM", uom_name=u)
		cls.crop = _make("Production Crop", crop_name="Cov Crop", crop_key="cov-crop", unit_label="Block", yield_uom="Kg")
		cls.op1 = _make("Production Operation", crop=cls.crop.name, operation_name="Cov Weeding", category="Other", work_uom="Kg", default_rate=1)
		cls.op2 = _make("Production Operation", crop=cls.crop.name, operation_name="Cov Spraying", category="Spraying", work_uom="Bed", default_rate=1)
		gj = {"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": [[[36.7, 0.0], [36.8, 0.0], [36.8, 0.1], [36.7, 0.0]]]}}
		cls.units = {}
		for n in ("A", "B", "C", "D", "E"):
			cls.units[n] = _make(
				"Production Unit", unit_name=f"Cov {n}", crop=cls.crop.name, unit_type="Orchard Block",
				company=cls.company, area_ha=1, geojson=json.dumps(gj) if n == "A" else None,
			).name

	def _plan(self, year, week, tasks):
		return _make("Production Work Plan", crop=self.crop.name, plan_year=year, plan_week=week, tasks=tasks)

	def _row(self, unit, op, planned, done, status, due, uom="Kg"):
		return {"unit": unit, "operation": op.name, "planned_qty": planned, "done_qty": done, "status": status, "due_date": due, "uom": uom}

	def test_states_and_remaining(self):
		U = self.units
		self._plan(2020, 10, [  # whole week is long past: unfinished work is late
			self._row(U["A"], self.op1, 10, 10, "Done", "2020-03-04"),
			self._row(U["B"], self.op1, 10, 4, "Partly Done", "2020-03-05"),
			self._row(U["B"], self.op2, 6, 0, "Open", "2020-03-05", "Bed"),
			self._row(U["C"], self.op1, 8, 0, "Skipped", "2020-03-05"),
		])
		res = coverage.coverage_map(self.crop.name, 2020, 10)
		self.assertNotIn("error", res)
		by = {u["name"]: u for u in res["units"]}
		self.assertEqual(by[U["A"]]["state"], "done")
		self.assertEqual(by[U["B"]]["state"], "late")
		self.assertEqual(by[U["B"]]["remaining_qty"], {"Kg": 6.0, "Bed": 6.0})
		self.assertEqual(by[U["B"]]["progress_pct"], 20.0)  # (0.4 + 0) / 2
		self.assertEqual(by[U["C"]]["state"], "no_work")
		self.assertEqual(by[U["D"]]["state"], "no_work")
		t = res["totals"]
		self.assertEqual(t["blocks"], 5)
		self.assertEqual(t["late"], 1)
		self.assertEqual(t["planned"], {"Kg": 20.0, "Bed": 6.0})
		self.assertEqual(t["done"], {"Kg": 14.0, "Bed": 0.0})
		self.assertEqual(t["remaining"], {"Kg": 6.0, "Bed": 6.0})
		self.assertEqual({o["operation_name"] for o in res["operations"]}, {"Cov Weeding", "Cov Spraying"})
		self.assertEqual(by[U["A"]]["geojson"]["type"], "Feature")
		self.assertIsNone(by[U["B"]]["geojson"])
		self.assertEqual(res["bounds"], [[36.7, 0.0], [36.8, 0.1]])

	def test_future_week_not_late_and_filters(self):
		U = self.units
		self._plan(2099, 10, [
			self._row(U["A"], self.op1, 10, 0, "Open", "2099-03-04"),
			self._row(U["B"], self.op1, 10, 3, "In Progress", "2099-03-04"),
			self._row(U["B"], self.op2, 6, 0, "Open", "2099-03-05", "Bed"),
		])
		res = coverage.coverage_map(self.crop.name, 2099, 10)
		by = {u["name"]: u["state"] for u in res["units"]}
		self.assertEqual((by[U["A"]], by[U["B"]]), ("not_started", "partial"))
		self.assertEqual(res["totals"]["late"], 0)
		res = coverage.coverage_map(self.crop.name, 2099, 10, status="partial")
		self.assertEqual([u["name"] for u in res["units"]], [U["B"]])
		res = coverage.coverage_map(self.crop.name, 2099, 10, operation=self.op2.name)
		by = {u["name"]: u for u in res["units"]}
		self.assertEqual(by[U["A"]]["state"], "no_work")
		self.assertEqual(by[U["B"]]["remaining_qty"], {"Bed": 6.0})
		self.assertEqual(len(res["operations"]), 2)  # filter list ignores the operation filter

	def test_pending_approval_when_field_present(self):
		if not frappe.get_meta("Production Plan Task").has_field("pending_qty"):
			self.skipTest("pending_qty not added yet")
		U = self.units
		plan = self._plan(2099, 11, [self._row(U["E"], self.op1, 10, 4, "In Progress", "2099-03-11")])
		frappe.db.set_value("Production Plan Task", plan.tasks[0].name, "pending_qty", 6)
		res = coverage.coverage_map(self.crop.name, 2099, 11)
		e = next(u for u in res["units"] if u["name"] == U["E"])
		self.assertEqual(e["state"], "pending_approval")
		self.assertEqual(e["tasks"][0]["pending_qty"], 6.0)
		self.assertEqual(res["totals"]["pending"], {"Kg": 6.0})
