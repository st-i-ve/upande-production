from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import today

from upande_production.mobile import api
from upande_production.production.logic import plans
from upande_production.production.logic.weeks import iso_of


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


class TestMobileApi(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make(
			"Farm", farm_name="TM Farm", company=cls.company, abbreviation="TMF",
			farm_type=[{"farm_type": "Has Blocks"}],
		)
		cls.crop = _make(
			"Production Crop", crop_name="TM Crop", crop_key="tm-crop", unit_label="Block", yield_uom="Kg"
		)
		cls.op = _make(
			"Production Operation", crop=cls.crop.name, operation_name="TM Weeding",
			category="Field Care", work_uom="Kg", default_rate=40,
		)
		cls.emp = _make(
			"Employee", first_name="TMEmp", gender="Male", date_of_birth="1990-01-01",
			date_of_joining="2020-01-01", company=cls.company,
		)
		cls.unit = _make(
			"Production Unit", unit_name="TM Unit", crop=cls.crop.name, farm=cls.farm.name,
			unit_type="Orchard Block", company=cls.company,
		)

	def _call(self, fn, payload):
		frappe.response.pop("data", None)
		with patch.object(frappe.local, "request", SimpleNamespace(get_json=lambda: payload), create=True):
			fn()
		return frappe.response["data"]

	def test_update_task_via_mobile(self):
		y, w = iso_of(today())
		plan = plans.get_or_create_plan(self.crop.name, self.farm.name, y, w)
		plan.append("tasks", {
			"unit": self.unit.name, "operation": self.op.name, "planned_qty": 10,
			"uom": "Kg", "rate": 40, "due_date": today(), "status": "Open",
		})
		plan.save()
		task = plan.tasks[-1].name
		res = self._call(api.productionUpdateTask, {
			"plan": plan.name, "task": task, "status": "Done",
			"entries": [{"employee": self.emp.name, "qty": 10}],
		})
		self.assertEqual(res["task"]["status"], "Done")
		self.assertEqual(len(res["work"]), 1)
		self.assertEqual(frappe.db.count("Value Adder Work", {"plan": plan.name, "plan_task": task, "docstatus": 1}), 1)
		wk = self._call(api.productionGetWeekPlan, {"crop": self.crop.name, "farm": self.farm.name})
		self.assertEqual(wk["plan"], plan.name)
		self.assertEqual(wk["tasks"][0]["done_qty"], 10)

	def test_bad_status_returns_error(self):
		res = self._call(api.productionUpdateTask, {"plan": "x", "task": "y", "status": "Bogus"})
		self.assertIn("error", res)
		res = self._call(api.productionUpdateTask, {})
		self.assertIn("error", res)
