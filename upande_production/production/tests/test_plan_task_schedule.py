import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, today

from upande_production.api import production as desk
from upande_production.production.logic import plans
from upande_production.production.logic.weeks import iso_of, iso_week_bounds
from upande_production.production.tests.labour_mode import use_builtin_labour


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


def _user(email, *roles):
	if not frappe.db.exists("User", email):
		_make("User", email=email, first_name=email.split("@")[0], send_welcome_email=0,
			roles=[{"role": r} for r in roles])
	return email


class TestPlanTaskSchedule(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		use_builtin_labour(cls)
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make("Farm", farm_name="PTS Farm", company=cls.company, abbreviation="PTS",
			farm_type=[{"farm_type": "Has Blocks"}])
		cls.crop = _make("Production Crop", crop_name="PTS Crop", crop_key="pts-crop", unit_label="Block", yield_uom="Kg")
		cls.op = _make("Field Operation", crop=cls.crop.name, operation_name="PTS Weeding",
			category="Other", work_uom="Kg", default_rate=40)
		cls.u1 = _make("Production Unit", unit_name="PTS B1", crop=cls.crop.name, farm=cls.farm.name,
			unit_type="Orchard Block", company=cls.company)
		cls.u2 = _make("Production Unit", unit_name="PTS B2", crop=cls.crop.name, farm=cls.farm.name,
			unit_type="Orchard Block", company=cls.company)
		cls.mgr = _user("pts.mgr@x.test", "Production Manager")
		cls.sup = _user("pts.sup@x.test", "Production Supervisor")
		cls.editor = _user("pts.editor@x.test", "Production Supervisor", "Production Plan Editor")
		cls.employee = _make("Employee", first_name="PTSEmp", gender="Male", date_of_birth="1990-01-01",
			date_of_joining="2020-01-01", company=cls.company)
		cls.year, cls.week = iso_of(today())
		cls.start, cls.end = iso_week_bounds(cls.year, cls.week)
		frappe.db.commit()  # the API envelope rolls back on an error; committed fixtures survive that

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		for p in frappe.get_all("Production Work Plan", filters={"crop": cls.crop.name}, pluck="name"):
			frappe.delete_doc("Production Work Plan", p, force=True)
		for dt, doc in (("Employee", cls.employee), ("Production Unit", cls.u2), ("Production Unit", cls.u1),
				("Field Operation", cls.op), ("Production Crop", cls.crop), ("Farm", cls.farm)):
			frappe.delete_doc(dt, doc.name, force=True)
		for u in (cls.mgr, cls.sup, cls.editor):
			frappe.delete_doc("User", u, force=True)
		frappe.db.commit()
		super().tearDownClass()

	def setUp(self):
		frappe.set_user("Administrator")
		plan = plans.get_or_create_plan(self.crop.name, self.farm.name, self.year, self.week)
		plan.append("tasks", {"unit": self.u1.name, "operation": self.op.name, "planned_qty": 5, "uom": "Kg",
			"rate": 40, "due_date": self.start, "status": "Open"})
		plan.save()
		frappe.db.commit()
		self.plan = plan.name
		self.task = plan.tasks[0].name
		self.addCleanup(self._clean)

	def _clean(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		for n in frappe.get_all("Casual Labour Work", filters={"plan": self.plan}, pluck="name"):
			frappe.delete_doc("Casual Labour Work", n, force=True)
		frappe.delete_doc("Production Work Plan", self.plan, force=True)
		frappe.db.commit()

	def save(self, tasks, user):
		frappe.set_user(user)
		return desk.save_plan_tasks(self.crop.name, self.farm.name, self.year, self.week, tasks)

	def row(self):
		return frappe.db.get_value("Work Plan Task", self.task, ["due_date", "original_due_date"], as_dict=True)

	def test_bootstrap_flag(self):
		for user, expected in ((self.mgr, True), (self.sup, False), (self.editor, True)):
			frappe.set_user(user)
			self.assertEqual(desk.get_bootstrap()["can_reschedule"], expected, user)

	def test_supervisor_cannot_delete_via_save(self):
		res = self.save([{"name": self.task, "_delete": 1}], self.sup)
		self.assertIn("error", res)
		self.assertTrue(frappe.db.exists("Work Plan Task", self.task))

	def test_supervisor_cannot_redate_via_save(self):
		res = self.save([{"name": self.task, "due_date": add_days(self.start, 1)}], self.sup)
		self.assertIn("error", res)
		self.assertEqual(getdate(self.row().due_date), getdate(self.start))

	def test_editor_can_redate_via_save(self):
		res = self.save([{"name": self.task, "due_date": add_days(self.start, 1)}], self.editor)
		self.assertNotIn("error", res)
		row = self.row()
		self.assertEqual(getdate(row.due_date), getdate(add_days(self.start, 1)))
		self.assertEqual(getdate(row.original_due_date), getdate(self.start))

	def test_save_refuses_delete_with_work(self):
		_make("Casual Labour Work", work_date=today(), employee=self.employee.name, unit=self.u1.name,
			operation=self.op.name, qty=5, uom="Kg", plan=self.plan, plan_task=self.task)
		frappe.db.commit()
		res = self.save([{"name": self.task, "_delete": 1}], self.mgr)
		self.assertIn("error", res)
		self.assertIn("Skip", res["error"])
		self.assertTrue(frappe.db.exists("Work Plan Task", self.task))

	def test_adding_tasks_unchanged(self):
		res = self.save([{"unit": self.u2.name, "operation": self.op.name, "planned_qty": 3,
			"due_date": add_days(self.start, 2)}], self.sup)
		self.assertNotIn("error", res)
		self.assertEqual(frappe.db.count("Work Plan Task", {"parent": self.plan}), 2)
