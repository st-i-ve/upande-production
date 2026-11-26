import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import today

from upande_production.api import production as desk
from upande_production.production.logic import cycle_setup, plans, settings
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


def set_step(on):
	frappe.db.set_single_value("Production Settings", "assistant_manager_step", 1 if on else 0)
	frappe.clear_document_cache("Production Settings", "Production Settings")
	frappe.db.commit()


class TestApprovalChain(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		use_builtin_labour(cls)
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make("Farm", farm_name="ACH Farm", company=cls.company, abbreviation="ACH",
			farm_type=[{"farm_type": "Has Blocks"}])
		cls.crop = _make("Production Crop", crop_name="ACH Crop", crop_key="ach-crop", unit_label="Block", yield_uom="Kg", uses_crop_cycles=1)
		cls.op = _make("Field Operation", crop=cls.crop.name, operation_name="ACH Weeding",
			category="Other", work_uom="Kg", default_rate=40)
		cls.item = _make("Item", item_code="ACH Tomato", item_name="ACH Tomato", item_group="All Item Groups",
			stock_uom="Kg", is_stock_item=1).name
		cls.protocol = _make("Production Protocol", protocol_name="ACH Proto", crop=cls.crop.name,
			version_status="Active", key_activities=[{"operation": cls.op.name, "week": w, "planned_qty": 1} for w in (1, 2, 3)]).name
		cls.u1 = _make("Production Unit", unit_name="ACH B1", crop=cls.crop.name, farm=cls.farm.name,
			unit_type="Orchard Block", company=cls.company, area_ha=1, plant_count=0)
		cls.mgr = _user("ach.mgr@x.test", "Production Manager")
		cls.sup = _user("ach.sup@x.test", "Production Supervisor")
		cls.asst = _user("ach.asst@x.test", settings.ASSISTANT_ROLE)
		cls.year, cls.week = iso_of(today())
		cls.start, cls.end = iso_week_bounds(cls.year, cls.week)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		set_step(False)
		for p in frappe.get_all("Production Work Plan", filters={"crop": cls.crop.name}, pluck="name"):
			frappe.delete_doc("Production Work Plan", p, force=True)
		for c in frappe.get_all("Production Crop Cycle", filters={"unit": cls.u1.name}, pluck="name"):
			frappe.delete_doc("Production Crop Cycle", c, force=True)
		for dt, name in (("Production Unit", cls.u1.name), ("Production Protocol", cls.protocol),
				("Field Operation", cls.op.name), ("Item", cls.item), ("Production Crop", cls.crop.name),
				("Farm", cls.farm.name)):
			frappe.delete_doc(dt, name, force=True)
		for u in (cls.mgr, cls.sup, cls.asst):
			frappe.delete_doc("User", u, force=True)
		frappe.db.commit()
		super().tearDownClass()

	def setUp(self):
		frappe.set_user("Administrator")
		set_step(False)
		self.addCleanup(self._clean)

	def _clean(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		set_step(False)
		for p in frappe.get_all("Production Work Plan", filters={"crop": self.crop.name}, pluck="name"):
			frappe.delete_doc("Production Work Plan", p, force=True)
		for c in frappe.get_all("Production Crop Cycle", filters={"unit": self.u1.name}, pluck="name"):
			frappe.delete_doc("Production Crop Cycle", c, force=True)
		frappe.db.commit()

	def add_task(self, user):
		frappe.set_user(user)
		res = desk.save_plan_tasks(self.crop.name, self.farm.name, self.year, self.week,
			[{"unit": self.u1.name, "operation": self.op.name, "planned_qty": 5, "due_date": self.start}])
		self.assertNotIn("error", res)
		frappe.set_user("Administrator")
		return frappe.get_all("Work Plan Task", filters={"parent": res["name"]},
			fields=["assigned_by", "awaiting_approval"])[0]

	def test_bootstrap_flags(self):
		set_step(True)
		for user, asst in ((self.asst, True), (self.mgr, False), (self.sup, False)):
			frappe.set_user(user)
			b = desk.get_bootstrap()
			self.assertEqual(b["is_assistant_manager"], asst, user)
			self.assertTrue(b["assistant_step"])
		set_step(False)
		frappe.set_user(self.asst)
		self.assertFalse(desk.get_bootstrap()["assistant_step"])

	def test_assigned_by_stamped_for_any_creator(self):
		set_step(True)
		row = self.add_task(self.mgr)
		self.assertEqual(row.assigned_by, self.mgr)
		self.assertEqual(row.awaiting_approval, 0)

	def test_assistant_task_awaits_when_step_on(self):
		set_step(True)
		row = self.add_task(self.asst)
		self.assertEqual(row.assigned_by, self.asst)
		self.assertEqual(row.awaiting_approval, 1)

	def test_assistant_task_not_awaiting_when_step_off(self):
		row = self.add_task(self.asst)
		self.assertEqual(row.assigned_by, self.asst)
		self.assertEqual(row.awaiting_approval, 0)

	def test_generated_tasks_stamped(self):
		set_step(True)
		cycle = cycle_setup.create_cycle({"unit": self.u1.name, "item": self.item, "existing": 1,
			"planting_date": today(), "protocol": self.protocol})["name"]
		self.assertTrue(cycle)
		plan = plans.get_or_create_plan(self.crop.name, self.farm.name, self.year, self.week)
		frappe.db.commit()
		frappe.set_user(self.asst)
		res = plans.generate_week_detail(plan.name)
		frappe.set_user("Administrator")
		self.assertGreater(res["created"], 0)
		rows = frappe.get_all("Work Plan Task", filters={"parent": plan.name}, fields=["assigned_by", "awaiting_approval"])
		self.assertTrue(rows)
		for r in rows:
			self.assertEqual((r.assigned_by, r.awaiting_approval), (self.asst, 1))

	def test_assistant_can_plan_and_see_pay(self):
		frappe.set_user(self.asst)
		b = desk.get_bootstrap()
		self.assertTrue(b["can_plan"])
		self.assertTrue(b["can_see_pay"])

	def test_helpers(self):
		self.assertTrue(settings.is_manager_user("Administrator"))
		self.assertTrue(settings.is_manager_user(self.mgr))
		self.assertFalse(settings.is_manager_user(self.asst))
		self.assertTrue(settings.is_assistant_manager(self.asst))
		self.assertFalse(settings.is_assistant_manager(self.mgr))
