from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

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
			category="Other", work_uom="Kg", default_rate=40,
		)
		cls.emp = _make(
			"Employee", first_name="TMEmp", gender="Male", date_of_birth="1990-01-01",
			date_of_joining="2020-01-01", company=cls.company,
		)
		cls.unit = _make(
			"Production Unit", unit_name="TM Unit", crop=cls.crop.name, farm=cls.farm.name,
			unit_type="Orchard Block", company=cls.company,
		)

	@classmethod
	def tearDownClass(cls):
		# these tests commit (the endpoints commit), so remove every fixture explicitly
		frappe.set_user("Administrator")
		frappe.db.rollback()
		crop = cls.crop.name
		unit = cls.unit.name
		ccs = [c for c in [frappe.db.get_value("Production Unit", unit, "cost_center")] if c]
		ccs += frappe.get_all("Cost Center", filters={"cost_center_name": ("like", f"{crop}%")}, pluck="name")
		for dt in ("Value Adder Work", "Production Harvest", "Yield Sample"):
			for n in frappe.get_all(dt, filters={"unit": unit}, pluck="name"):
				d = frappe.get_doc(dt, n)
				if d.docstatus == 1:
					d.flags.ignore_permissions = True
					d.cancel()
				frappe.delete_doc(dt, n, force=True, ignore_permissions=True)
		for n in frappe.get_all("Production Work Plan", filters={"crop": crop}, pluck="name"):
			frappe.delete_doc("Production Work Plan", n, force=True, ignore_permissions=True)
		for dt, filt in (
			("Production Crop Cycle", {"unit": unit}),
			("Production Protocol", {"crop": crop}),
			("Production Unit", {"name": unit}),
			("Production Operation", {"crop": crop}),
			("Production Crop", {"name": crop}),
			("Employee", {"name": cls.emp.name}),
			("Farm", {"name": cls.farm.name}),
		):
			for n in frappe.get_all(dt, filters=filt, pluck="name"):
				frappe.delete_doc(dt, n, force=True, ignore_permissions=True)
		for n in ccs:
			if frappe.db.exists("Cost Center", n) and not frappe.db.exists("Cost Center", {"parent_cost_center": n}):
				frappe.delete_doc("Cost Center", n, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

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
		self.assertEqual(frappe.db.count("Value Adder Work", {"plan": plan.name, "plan_task": task, "docstatus": 0, "approval_status": "Pending"}), 1)
		self.assertEqual(res["approval_status"], "Pending")
		self.assertEqual(res["task"]["pending_qty"], 10)
		self.assertEqual(res["task"]["done_qty"], 0)
		wk = self._call(api.productionGetWeekPlan, {"crop": self.crop.name, "farm": self.farm.name})
		self.assertEqual(wk["plan"], plan.name)
		t = next(t for t in wk["tasks"] if t["name"] == task)
		self.assertEqual(t["done_qty"], 0)
		self.assertEqual(t["pending_qty"], 10)

	def test_bad_status_returns_error(self):
		res = self._call(api.productionUpdateTask, {"plan": "x", "task": "y", "status": "Bogus"})
		self.assertIn("error", res)
		res = self._call(api.productionUpdateTask, {})
		self.assertIn("error", res)

	def _plan_with_task(self, **task):
		y, w = iso_of(today())
		plan = plans.get_or_create_plan(self.crop.name, self.farm.name, y, w)
		plan.append("tasks", {
			"unit": self.unit.name, "operation": self.op.name, "planned_qty": 10, "uom": "Kg",
			"rate": 40, "due_date": today(), "status": "Open", **task,
		})
		plan.save()
		return plan, plan.tasks[-1].name

	def test_update_task_with_crew_returns_entries(self):
		emp2 = _make(
			"Employee", first_name="TMEmpTwo", gender="Male", date_of_birth="1991-01-01",
			date_of_joining="2020-01-01", company=self.company,
		)
		self.addCleanup(lambda: frappe.delete_doc("Employee", emp2.name, force=True, ignore_permissions=True))
		plan, task = self._plan_with_task()
		res = self._call(api.productionUpdateTask, {
			"plan": plan.name, "task": task, "status": "Partly Done", "note": "rain",
			"entries": [{"employee": self.emp.name, "qty": 4, "hours": 3}, {"employee": emp2.name, "qty": 3}],
		})
		self.assertEqual(len(res["work"]), 2)
		self.assertEqual(res["task"]["pending_qty"], 7)
		self.assertEqual(len(res["entries"]), 2)
		self.assertEqual({e["approval_status"] for e in res["entries"]}, {"Pending"})
		self.assertEqual(res["task"]["note"], "rain")

	def test_plan_list_and_detail(self):
		plan, task = self._plan_with_task(due_date=add_days(today(), -3), supervisor=self.emp.name)
		y, w = iso_of(today())
		lst = self._call(api.productionListWeekPlans, {"crop": self.crop.name, "farm": self.farm.name})
		row = next(p for p in lst["plans"] if p["name"] == plan.name)
		self.assertTrue(row["is_current"])
		self.assertEqual(row["tasks_total"], len(plan.tasks))
		self.assertGreaterEqual(row["tasks_late"], 1)
		self.assertEqual(lst["current_plan"], plan.name)
		self._call(api.productionUpdateTask, {
			"plan": plan.name, "task": task, "status": "Done", "entries": [{"employee": self.emp.name, "qty": 10}],
		})
		det = self._call(api.productionGetPlanDetail, {"crop": self.crop.name, "farm": self.farm.name, "year": y, "week": w})
		self.assertEqual(det["plan"], plan.name)
		self.assertEqual(det["tasks_pending_approval"], 1)
		blk = next(b for b in det["blocks"] if b["unit"] == self.unit.name)
		t = next(t for t in blk["tasks"] if t["name"] == task)
		self.assertEqual(t["pending_qty"], 10)
		self.assertEqual(t["supervisor_name"], self.emp.employee_name)
		self.assertEqual(t["entries"][0]["approval_status"], "Pending")
		other = self._call(api.productionGetPlanDetail, {"crop": self.crop.name, "farm": self.farm.name, "year": y, "week": w, "unit": "nope"})
		self.assertEqual(other["blocks"], [])

	def test_add_task_validates_and_creates(self):
		y, w = iso_of(add_days(today(), 21))
		due = add_days(today(), 21)
		res = self._call(api.productionAddTask, {
			"crop": self.crop.name, "farm": self.farm.name, "year": y, "week": w, "unit": self.unit.name,
			"operation": self.op.name, "planned_qty": 5, "due_date": str(due), "supervisor": self.emp.name,
		})
		self.assertEqual(res["status"], "success")
		self.assertEqual(res["task"]["uom"], "Kg")
		self.assertEqual(res["task"]["status"], "Open")
		bad = self._call(api.productionAddTask, {
			"crop": self.crop.name, "year": y, "week": w, "unit": self.unit.name,
			"operation": self.op.name, "planned_qty": 5, "due_date": str(add_days(due, 30)),
		})
		self.assertIn("Due date", bad["error"])
		self.assertIn("error", self._call(api.productionAddTask, {
			"crop": self.crop.name, "unit": self.unit.name, "operation": self.op.name, "planned_qty": 0,
		}))

	def test_units_and_detail_carry_variety_and_stage_keys(self):
		units = self._call(api.productionListUnits, {"crop": self.crop.name})
		u = next(u for u in units if u["name"] == self.unit.name)
		for k in ("variety", "current_stage", "stage_day", "days_to_harvest", "pre_harvest_days", "in_pre_harvest"):
			self.assertIn(k, u)
		plan, task = self._plan_with_task(due_date=today(), supervisor=self.emp.name)
		y, w = iso_of(today())
		det = self._call(api.productionGetPlanDetail, {"crop": self.crop.name, "farm": self.farm.name, "year": y, "week": w})
		blk = next(b for b in det["blocks"] if b["unit"] == self.unit.name)
		t = next(t for t in blk["tasks"] if t["name"] == task)
		for k in ("variety", "current_stage", "stage_day", "days_to_harvest", "pre_harvest_days", "in_pre_harvest"):
			self.assertIn(k, blk)
			self.assertIn(k, t)

	def test_generate_plan_without_cycles_explains(self):
		res = self._call(api.productionGeneratePlan, {"crop": self.crop.name, "farm": self.farm.name})
		self.assertEqual(res["status"], "success")
		self.assertIsNotNone(res["plan"])

	def test_protocol_check_statuses(self):
		from upande_production.production.logic import analytics

		proto = _make(
			"Production Protocol", protocol_name="TM Proto", crop=self.crop.name, version_status="Active",
			key_activities=[{"operation": self.op.name, "week": 1, "planned_qty": 10}],
			cultural_activities=[{"operation": self.op.name, "schedule": "Interval", "interval_weeks": 1,
				"planned_qty": 5}],
		)
		start = frappe.utils.getdate(today())
		y, w = iso_of(start)
		cycle = _make(
			"Production Crop Cycle", unit=self.unit.name, crop=self.crop.name, start_date=add_days(start, -start.weekday()),
			protocol=proto.name, status="Active",
		)
		def cleanup():
			for dt in ("Value Adder Work",):
				for n in frappe.get_all(dt, filters={"cycle": cycle.name}, pluck="name"):
					d = frappe.get_doc(dt, n)
					if d.docstatus == 1:
						d.cancel()
					frappe.delete_doc(dt, n, force=True, ignore_permissions=True)
			frappe.db.sql("delete from `tabProduction Plan Task` where cycle = %s", cycle.name)
			frappe.delete_doc("Production Crop Cycle", cycle.name, force=True, ignore_permissions=True)
			frappe.delete_doc("Production Protocol", proto.name, force=True, ignore_permissions=True)
			frappe.db.commit()

		self.addCleanup(cleanup)
		res = analytics.protocol_check(self.crop.name, y, w)
		steps = res["blocks"][0]["steps"]
		self.assertEqual(len(steps), 2)
		self.assertEqual({s["status"] for s in steps}, {"not_planned"})
		self.assertEqual(res["totals"]["not_planned"], 2)
		plans.generate_week(plans.get_or_create_plan(self.crop.name, self.farm.name, y, w).name)
		res = self._call(api.productionProtocolCheck, {"crop": self.crop.name, "unit": self.unit.name})
		self.assertEqual(res["totals"]["steps"], 2)
		self.assertNotIn("not_planned", {s["status"] for s in res["blocks"][0]["steps"]})
		plan = frappe.get_doc("Production Work Plan", res["blocks"][0]["steps"][0]["plan"])
		t0 = next(t for t in plan.tasks if t.protocol_ref == res["blocks"][0]["steps"][0]["protocol_ref"])
		self._call(api.productionUpdateTask, {
			"plan": plan.name, "task": t0.name, "status": "Done", "entries": [{"employee": self.emp.name, "qty": 10}],
		})
		res = self._call(api.productionProtocolCheck, {"crop": self.crop.name, "unit": self.unit.name})
		self.assertEqual(res["totals"]["pending_approval"], 1)

	def test_protocol_check_cycleless_crop(self):
		res = self._call(api.productionProtocolCheck, {"crop": "Apiary"}) if frappe.db.exists("Production Crop", "Apiary") else None
		if res is None:
			self.skipTest("no Apiary crop")
		self.assertEqual(res["blocks"], [])
		self.assertTrue(res["reason"])

	def test_value_adder_search(self):
		res = self._call(api.productionListValueAdders, {"search": "zzzz-none", "limit": 5})
		self.assertEqual(res, [])
