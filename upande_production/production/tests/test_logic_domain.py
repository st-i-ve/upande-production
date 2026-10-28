import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, get_datetime, getdate, now_datetime, today

from upande_production.production.logic import approvals, plans, units, work
from upande_production.production.logic.weeks import iso_of


def _monday(d):
	d = getdate(d)
	return add_days(d, -d.weekday())


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


class TestLogicDomain(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		if not frappe.db.exists("Item Group", "Products"):
			_make("Item Group", item_group_name="Products", parent_item_group="All Item Groups")
		cls.item = _make("Item", item_code="TC-Item", item_name="TC Item", item_group="Products", stock_uom="Kg")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make(
			"Farm", farm_name="TC Farm", company=cls.company, abbreviation="TCF",
			farm_type=[{"farm_type": "Has Blocks"}],
		)
		cls.crop = _make(
			"Production Crop", crop_name="Test Crop", crop_key="test-crop", unit_label="Block", yield_uom="Kg"
		)
		cls.op = _make(
			"Production Operation", crop=cls.crop.name, operation_name="TC Weeding",
			category="Other", work_uom="Kg", default_rate=40,
		)
		cls.emps = [
			_make(
				"Employee", first_name=f"TC{i}", gender="Male", date_of_birth="1990-01-01",
				date_of_joining="2020-01-01", company=cls.company,
			)
			for i in range(2)
		]

	def _unit(self, name, **kw):
		return _make(
			"Production Unit", unit_name=name, crop=self.crop.name, farm=self.farm.name,
			unit_type=kw.pop("unit_type", "Orchard Block"), company=self.company, **kw,
		)

	def _plan_with_task(self, due, planned=10):
		unit = self._unit(frappe.generate_hash(length=6))
		iso_y, iso_w = iso_of(due)
		plan = plans.get_or_create_plan(self.crop.name, self.farm.name, iso_y, iso_w)
		plan.append("tasks", {
			"unit": unit.name, "operation": self.op.name, "planned_qty": planned,
			"uom": "Kg", "rate": 40, "due_date": due, "status": "Open",
		})
		plan.save()
		return plan, plan.tasks[-1]

	def test_unit_cost_center_tree(self):
		pivot = self._unit("TC Pivot", unit_type="Pivot", is_group=1)
		b1 = self._unit("TC B1", parent_production_unit=pivot.name)
		b2 = self._unit("TC B2", parent_production_unit=pivot.name)
		pcc = frappe.db.get_value("Production Unit", pivot.name, "cost_center")
		self.assertTrue(pcc)
		self.assertEqual(frappe.db.get_value("Cost Center", pcc, "is_group"), 1)
		for b in (b1, b2):
			cc = frappe.db.get_value("Production Unit", b.name, "cost_center")
			self.assertEqual(frappe.db.get_value("Cost Center", cc, "parent_cost_center"), pcc)
		self.assertEqual(set(units.subtree(pivot.name)), {pivot.name, b1.name, b2.name})

	def test_generate_week_idempotent(self):
		unit = self._unit("TC GenUnit")
		proto = _make(
			"Production Protocol", protocol_name="TC Proto", version_status="Active", crop=self.crop.name,
			steps=[{"operation": self.op.name, "day_offset": 3, "repeat_every_days": 7, "repeat_count": 4}],
		)
		w_monday = _monday(today())
		start = add_days(w_monday, -7)
		_make(
			"Production Crop Cycle", unit=unit.name, crop=self.crop.name, start_date=start,
			protocol=proto.name, status="Active",
		)
		iso_y, iso_w = iso_of(w_monday)
		plan = plans.get_or_create_plan(self.crop.name, self.farm.name, iso_y, iso_w)
		self.assertEqual(plans.generate_week(plan.name), 1)
		self.assertEqual(plans.generate_week(plan.name), 0)
		plan.reload()
		gen = next(t for t in plan.tasks if t.protocol_ref)
		self.assertEqual(str(gen.due_date), str(add_days(w_monday, 3)))

	def test_record_twice_sums_not_duplicates(self):
		plan, task = self._plan_with_task(today())
		e = self.emps[0].name
		work.record_task_work(plan.name, task.name, "In Progress", [{"employee": e, "qty": 6}])
		res = work.record_task_work(plan.name, task.name, "Done", [{"employee": self.emps[1].name, "qty": 4}])
		self.assertEqual(res["task"]["done_qty"], 0)
		self.assertEqual(res["task"]["pending_qty"], 10)
		approvals.approve(frappe.get_all("Value Adder Work", filters={"plan": plan.name, "plan_task": task.name}, pluck="name"))
		plan.reload()
		self.assertEqual(next(t for t in plan.tasks if t.name == task.name).done_qty, 10)
		self.assertEqual(next(t for t in plan.tasks if t.name == task.name).pending_qty, 0)
		vaws = frappe.get_all(
			"Value Adder Work", filters={"plan": plan.name, "plan_task": task.name, "docstatus": 1},
			fields=["qty", "rate", "pay_value"],
		)
		self.assertEqual(len(vaws), 2)
		for v in vaws:
			self.assertEqual(v.pay_value, v.qty * v.rate)

	def test_cancel_recounts_done_qty(self):
		plan, task = self._plan_with_task(today())
		work.record_task_work(plan.name, task.name, "In Progress", [{"employee": self.emps[0].name, "qty": 6}])
		res = work.record_task_work(plan.name, task.name, "Done", [{"employee": self.emps[1].name, "qty": 4}])
		approvals.approve(frappe.get_all("Value Adder Work", filters={"plan": plan.name, "plan_task": task.name}, pluck="name"))
		plan.reload()
		self.assertEqual(next(t for t in plan.tasks if t.name == task.name).done_qty, 10)
		frappe.get_doc("Value Adder Work", res["work"][0]).cancel()
		plan.reload()
		self.assertEqual(next(t for t in plan.tasks if t.name == task.name).done_qty, 6)

	def test_status_only_creates_no_work(self):
		plan, task = self._plan_with_task(today())
		res = work.record_task_work(plan.name, task.name, "In Progress", [])
		self.assertEqual(res["work"], [])
		self.assertEqual(frappe.db.count("Value Adder Work", {"plan": plan.name, "plan_task": task.name}), 0)
		self.assertTrue(res["task"]["started_at"])

	def test_late_flag_on_plan_save(self):
		plan, task = self._plan_with_task(add_days(today(), -3))
		res = work.record_task_work(plan.name, task.name, "Done", [{"employee": self.emps[0].name, "qty": 10}])
		self.assertEqual(res["task"]["deviation"], "Partial")
		self.assertEqual(res["task"]["done_qty"], 0)  # deviation maths stay on approved qty
		approvals.approve(res["work"])
		plan.reload()
		self.assertEqual(next(t for t in plan.tasks if t.name == task.name).deviation, "Late")

	def test_sample_estimate(self):
		unit = self._unit("TC SampleUnit", plant_count=400)
		ys = _make(
			"Yield Sample", sample_date=today(), unit=unit.name, sample_basis="Trees",
			sample_size=10, sampled_yield=50, uom="Kg",
		)
		self.assertEqual(ys.unit_population, 400)
		self.assertEqual(ys.est_unit_yield, 2000)
