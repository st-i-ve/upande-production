import frappe
from frappe.tests import IntegrationTestCase

from upande_production.api import labourers as lab_api
from upande_production.api import production as desk
from upande_production.patches import create_production_supervisors
from upande_production.production.logic import labourers, supervisors


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


def _user(email, role):
	if not frappe.db.exists("User", email):
		_make("User", email=email, first_name=email.split("@")[0], send_welcome_email=0, roles=[{"role": role}])
	return email


def _employee(first, company, user=None):
	return _make("Employee", first_name=first, gender="Male", date_of_birth="1990-01-01",
		date_of_joining="2020-01-01", company=company, user_id=user)


class TestSupervisorRecords(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make("Farm", farm_name="SR Farm", company=cls.company, abbreviation="SRF",
			farm_type=[{"farm_type": "Has Blocks"}])
		cls.crop = _make("Production Crop", crop_name="SR Crop", crop_key="sr-crop", unit_label="Block", yield_uom="Kg")
		cls.other_crop = _make("Production Crop", crop_name="SR Other", crop_key="sr-other", unit_label="Block", yield_uom="Kg")
		cls.unit = _make("Production Unit", unit_name="SR B1", crop=cls.crop.name, farm=cls.farm.name,
			unit_type="Orchard Block", company=cls.company)
		cls.mgr_user = _user("sr.mgr@x.test", "Production Manager")
		cls.sup_user = _user("sr.sup@x.test", "Production Supervisor")

	def setUp(self):
		self.a = _employee("SRA", self.company, self.sup_user)
		self.b = _employee("SRB", self.company)
		self.c = _employee("SRC", self.company)
		self.d = _employee("SRD", self.company)
		self.addCleanup(self._clean)

	def _clean(self):
		frappe.set_user("Administrator")
		emps = [e.name for e in (self.a, self.b, self.c, self.d)]
		for dt, f in (("Production Supervisor Assignment", "supervisor"), ("Casual Labourer", "employee")):
			for n in frappe.get_all(dt, filters={f: ("in", emps)}, pluck="name"):
				frappe.delete_doc(dt, n, force=True)
		for n in frappe.get_all("Production Supervisor", filters={"employee": ("in", emps)}, pluck="name"):
			frappe.delete_doc("Production Supervisor", n, force=True)
		for e in emps:
			frappe.delete_doc("Employee", e, force=True)

	def names(self, **kw):
		return {s["name"] for s in supervisors.supervisor_options(**kw)}

	def test_patch_creates_records_for_used_employees_and_is_idempotent(self):
		_make("Production Supervisor Assignment", crop=self.crop.name, unit=self.unit.name, supervisor=self.b.name,
			plan_year=2031, plan_week=3)
		_make("Casual Labourer", employee=self.d.name, active=1)
		frappe.db.set_value("Casual Labourer", self.d.name, "supervisor", self.c.name)
		self.assertFalse(frappe.db.exists("Production Supervisor", self.b.name))
		create_production_supervisors.execute()
		create_production_supervisors.execute()
		self.assertTrue(frappe.db.get_value("Production Supervisor", self.b.name, "active"))
		self.assertTrue(frappe.db.exists("Production Supervisor", self.c.name))
		self.assertEqual(frappe.db.count("Production Supervisor", {"employee": self.b.name}), 1)
		self.assertFalse(frappe.db.exists("Production Supervisor", self.a.name))  # never used

	def test_options_only_active_supervisors(self):
		_make("Production Supervisor", employee=self.a.name)
		inactive = _make("Production Supervisor", employee=self.b.name, active=0)
		names = self.names()
		self.assertIn(self.a.name, names)
		self.assertNotIn(inactive.name, names)
		row = next(s for s in supervisors.supervisor_options() if s["name"] == self.a.name)
		self.assertEqual(row["user"], self.sup_user)
		self.assertEqual(row["employee_name"], self.a.employee_name)
		self.assertEqual({r["name"] for r in supervisors.candidates()}, names)

	def test_options_extra_keeps_an_inactive_one_already_assigned(self):
		_make("Production Supervisor", employee=self.b.name, active=0)
		self.assertIn(self.b.name, {s["name"] for s in supervisors.supervisor_options(extra=[self.b.name])})

	def test_options_crop_filter(self):
		_make("Production Supervisor", employee=self.a.name, crops=[{"crop": self.crop.name}])
		_make("Production Supervisor", employee=self.b.name)  # no crops = all
		self.assertEqual({self.a.name, self.b.name} - self.names(crop=self.crop.name), set())
		n = self.names(crop=self.other_crop.name)
		self.assertNotIn(self.a.name, n)
		self.assertIn(self.b.name, n)

	def test_endpoint_returns_options(self):
		_make("Production Supervisor", employee=self.a.name)
		frappe.set_user(self.mgr_user)
		try:
			res = desk.get_supervisor_options()
			res2 = lab_api.get_supervisor_options()
		finally:
			frappe.set_user("Administrator")
		self.assertIn(self.a.name, {r["name"] for r in res})
		self.assertEqual(res, res2)

	def test_labourer_supervisor_must_be_a_production_supervisor(self):
		_make("Production Supervisor", employee=self.a.name)
		with self.assertRaises(frappe.ValidationError) as ctx:
			_make("Casual Labourer", employee=self.d.name, active=1, supervisor=self.c.name)
		self.assertIn("Choose a Production Supervisor.", str(ctx.exception))
		doc = _make("Casual Labourer", employee=self.d.name, active=1, supervisor=self.a.name)
		self.assertEqual(doc.supervisor, self.a.name)
		# an old non-supervisor value that is not being changed still saves
		frappe.db.set_value("Casual Labourer", doc.name, "supervisor", self.c.name)
		doc = frappe.get_doc("Casual Labourer", doc.name)
		doc.crew = "X"
		doc.save()
		# inactive supervisors cannot be newly chosen
		frappe.db.set_value("Production Supervisor", self.a.name, "active", 0)
		doc.supervisor = self.a.name
		with self.assertRaises(frappe.ValidationError):
			doc.save()

	def test_patch_registers_a_left_employee_as_inactive(self):
		_make("Production Supervisor Assignment", crop=self.crop.name, unit=self.unit.name, supervisor=self.c.name,
			plan_year=2031, plan_week=4)
		frappe.db.set_value("Employee", self.c.name, "status", "Left")
		create_production_supervisors.execute()
		self.assertEqual(frappe.db.get_value("Production Supervisor", self.c.name, "active"), 0)
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc("Production Supervisor", self.c.name).update({"active": 1}).save()

	def test_a_non_active_employee_cannot_have_an_active_record(self):
		for status in ("Inactive", "Suspended", "Left"):
			frappe.db.set_value("Employee", self.d.name, "status", status)
			with self.assertRaises(frappe.ValidationError):
				_make("Production Supervisor", employee=self.d.name, active=1)

	def test_employee_leaving_deactivates_the_supervisor(self):
		_make("Production Supervisor", employee=self.b.name, active=1)
		emp = frappe.get_doc("Employee", self.b.name)
		emp.status = "Inactive"
		emp.save()
		self.assertEqual(frappe.db.get_value("Production Supervisor", self.b.name, "active"), 0)

	def test_patch_registers_an_inactive_employee_as_inactive(self):
		_make("Production Supervisor Assignment", crop=self.crop.name, unit=self.unit.name, supervisor=self.d.name,
			plan_year=2031, plan_week=5)
		frappe.db.set_value("Employee", self.d.name, "status", "Suspended")
		create_production_supervisors.execute()
		self.assertEqual(frappe.db.get_value("Production Supervisor", self.d.name, "active"), 0)

	def test_get_week_passes_the_crop(self):
		_make("Production Supervisor", employee=self.a.name, crops=[{"crop": self.other_crop.name}])
		_make("Production Supervisor", employee=self.b.name, crops=[{"crop": self.crop.name}])
		names = {s["name"] for s in supervisors.get_week(self.crop.name, self.farm.name, 2031, 5)["supervisors"]}
		self.assertIn(self.b.name, names)
		self.assertNotIn(self.a.name, names)

	def test_add_labourers_with_unregistered_supervisor_refused(self):
		with self.assertRaises(frappe.ValidationError):
			labourers.add_labourers([self.d.name], supervisor=self.c.name)
		self.assertFalse(frappe.db.exists("Casual Labourer", self.d.name))

	def test_options_current_and_link_query(self):
		_make("Production Supervisor", employee=self.a.name)
		res = desk.get_supervisor_options(current=self.c.name)
		self.assertIn(self.c.name, {r["name"] for r in res})
		hits = supervisors.supervisor_query("Employee", "SRA", "name", 0, 20, {})
		self.assertEqual([h[0] for h in hits], [self.a.name])

	def test_mulching_category_accepted(self):
		op = _make("Field Operation", crop=self.crop.name, operation_name="SR Mulch", category="Mulching",
			work_uom="Kg", default_rate=10)
		self.assertEqual(op.category, "Mulching")

	def test_permissions(self):
		rec = _make("Production Supervisor", employee=self.a.name)
		try:
			frappe.set_user(self.mgr_user)
			self.assertTrue(frappe.has_permission("Production Supervisor", "create"))
			self.assertTrue(frappe.has_permission("Production Supervisor", "write", rec.name))
			frappe.set_user(self.sup_user)
			self.assertTrue(frappe.has_permission("Production Supervisor", "read", rec.name))
			self.assertFalse(frappe.has_permission("Production Supervisor", "create"))
			self.assertFalse(frappe.has_permission("Production Supervisor", "write", rec.name))
		finally:
			frappe.set_user("Administrator")
