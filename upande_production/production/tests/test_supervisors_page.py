from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from upande_production.api import supervisors as api
from upande_production.production.logic import plans, supervisors
from upande_production.production.logic.weeks import iso_of
from upande_production.production.tests.labour_mode import use_builtin_labour


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


def _user(email, role):
	if not frappe.db.exists("User", email):
		_make("User", email=email, first_name=email.split("@")[0], send_welcome_email=0, roles=[{"role": role}])
	return email


def _employee(first, company, **kw):
	return _make("Employee", first_name=first, gender="Male", date_of_birth="1990-01-01",
		date_of_joining="2020-01-01", company=company, **kw)


class TestSupervisorsPage(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		use_builtin_labour(cls)
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make("Farm", farm_name="SPG Farm", company=cls.company, abbreviation="SPG",
			farm_type=[{"farm_type": "Has Blocks"}])
		cls.crop = _make("Production Crop", crop_name="SPG Crop", crop_key="spg-crop", unit_label="Block", yield_uom="Kg")
		cls.op = _make("Field Operation", crop=cls.crop.name, operation_name="SPG Weeding", category="Other", work_uom="Kg", default_rate=40)
		cls.spray = _make("Field Operation", crop=cls.crop.name, operation_name="SPG Spray", category="Spraying", work_uom="Kg", default_rate=40)
		cls.u1 = _make("Production Unit", unit_name="SPG B1", crop=cls.crop.name, farm=cls.farm.name, unit_type="Orchard Block", company=cls.company)
		cls.u2 = _make("Production Unit", unit_name="SPG B2", crop=cls.crop.name, farm=cls.farm.name, unit_type="Orchard Block", company=cls.company)
		cls.mgr_user = _user("spg.mgr@x.test", "Production Manager")
		cls.sup_user = _user("spg.sup@x.test", "Production Supervisor")
		cls.year, cls.week = iso_of(today())

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		super().tearDownClass()

	def setUp(self):
		frappe.db.savepoint("spg_test")
		self.addCleanup(lambda: frappe.db.sql("rollback to savepoint spg_test"))
		self.addCleanup(frappe.set_user, "Administrator")
		# endpoints roll back on error, which would also drop the class fixtures and this savepoint
		patcher = patch.object(frappe.db, "rollback")
		patcher.start()
		self.addCleanup(patcher.stop)
		self.a = _employee("SPGA", self.company, cell_number="0700111222")
		self.b = _employee("SPGB", self.company)
		self.psa = _make("Production Supervisor", employee=self.a.name)
		self.psb = _make("Production Supervisor", employee=self.b.name)

	def _plan(self):
		supervisors.save_week(self.crop.name, self.farm.name, self.year, self.week, [
			{"unit": self.u1.name, "supervisor": self.a.name, "category": ""},
			{"unit": self.u2.name, "supervisor": self.a.name, "category": "Spraying"},
			{"unit": self.u2.name, "supervisor": self.b.name, "category": ""}])
		plan = plans.get_or_create_plan(self.crop.name, self.farm.name, self.year, self.week)
		for unit, op, due, status in ((self.u1, self.op, today(), "Done"), (self.u1, self.op, today(), "Open"),
				(self.u2, self.spray, add_days(today(), -30), "Open"), (self.u2, self.op, today(), "Open")):
			plan.append("tasks", {"unit": unit.name, "operation": op.name, "planned_qty": 5, "uom": "Kg", "rate": 40,
				"due_date": due, "status": status})
		plan.save()
		return plan

	def _labourer(self, emp, sup, active=1):
		return _make("Casual Labourer", employee=emp.name, active=active, supervisor=sup.name)

	def _row(self, emp, **kw):
		rows = api.list_supervisors(crop=self.crop.name, year=self.year, week=self.week, **kw)
		return next((r for r in rows if r["employee"] == emp.name), None)

	def test_list_card_fields_and_blocks(self):
		self._plan()
		row = self._row(self.a)
		self.assertEqual(row["employee_name"], self.a.employee_name)
		self.assertEqual(row["phone"], "0700111222")
		self.assertTrue(row["active"])
		self.assertEqual(row["kpis"]["blocks"], 2)
		self.assertEqual(self._row(self.b)["kpis"]["blocks"], 1)

	def test_task_counts_done_open_late(self):
		self._plan()
		k = self._row(self.a)["kpis"]["tasks"]
		self.assertEqual((k["done"], k["late"], k["open"]), (1, 1, 1))  # u1 done+open; u2 spray overdue (a shares it)
		self.assertEqual(k["total"], 3)

	def test_crew_counts_active_labourers_only(self):
		x, y, z = (_employee(n, self.company) for n in ("SPGX", "SPGY", "SPGZ"))
		self._labourer(x, self.a)
		self._labourer(y, self.a)
		self._labourer(z, self.a, active=0)
		self.assertEqual(self._row(self.a)["kpis"]["crew"], 2)

	def test_pending_entries_of_crew(self):
		self._plan()
		x = _employee("SPGX", self.company)
		self._labourer(x, self.a)
		frappe.db.sql("""insert into `tabCasual Labour Work` (name, employee, crop, docstatus, approval_status, creation, modified, owner, modified_by)
			values ('SPGW-1', %s, %s, 0, 'Pending', now(), now(), 'Administrator', 'Administrator'),
			('SPGW-2', %s, %s, 0, 'Approved', now(), now(), 'Administrator', 'Administrator')""",
			(x.name, self.crop.name, x.name, self.crop.name))
		self.assertEqual(self._row(self.a)["kpis"]["pending"], 1)
		self.assertEqual(self._row(self.b)["kpis"]["pending"], 0)

	def test_inactive_listed_with_flag_and_crop_scope(self):
		other = _make("Production Crop", crop_name="SPG Other", crop_key="spg-other", unit_label="Block", yield_uom="Kg")
		scoped = _employee("SPGS", self.company)
		_make("Production Supervisor", employee=scoped.name, crops=[{"crop": other.name}])
		self.assertIsNone(self._row(scoped))
		self.psb.active = 0
		self.psb.save()
		self.assertFalse(self._row(self.b)["active"])

	def test_get_supervisor_detail(self):
		self._plan()
		x = _employee("SPGX", self.company, image="/files/x.png")
		self._labourer(x, self.a)
		d = api.get_supervisor(self.a.name, crop=self.crop.name, year=self.year, week=self.week)
		blocks = {b["unit"]: b for b in d["blocks"]}
		self.assertTrue(blocks[self.u1.name]["overseer"])
		self.assertEqual(blocks[self.u2.name]["categories"], ["Spraying"])
		self.assertFalse(blocks[self.u2.name]["overseer"])
		self.assertEqual(d["tasks"]["done"], 1)
		lab = d["labourers"][0]
		self.assertEqual((lab["employee"], lab["image"], lab["active"]), (x.name, "/files/x.png", 1))
		self.assertEqual(d["supervisor"]["employee"], self.a.name)
		self.assertIn("can_edit", d)

	def test_get_supervisor_unknown(self):
		self.assertIn("error", api.get_supervisor("NOPE-1"))

	def test_save_supervisor_create_defaults_and_edit(self):
		e = _employee("SPGN", self.company, cell_number="0711", image="/files/n.png")
		res = api.save_supervisor({"employee": e.name, "farm": self.farm.name, "crops": [self.crop.name], "notes": "hi"})
		self.assertEqual(res["employee"], e.name)
		doc = frappe.get_doc("Production Supervisor", e.name)
		self.assertEqual((doc.phone, doc.image, doc.notes), ("0711", "/files/n.png", "hi"))
		self.assertEqual([c.crop for c in doc.crops], [self.crop.name])
		res = api.save_supervisor({"employee": e.name, "active": 0, "crops": []})
		doc.reload()
		self.assertEqual((doc.active, len(doc.crops), doc.notes), (0, 0, "hi"))

	def test_save_supervisor_manager_only(self):
		e = _employee("SPGM", self.company)
		frappe.set_user(self.sup_user)
		res = api.save_supervisor({"employee": e.name})
		self.assertIn("error", res)
		self.assertFalse(frappe.db.exists("Production Supervisor", e.name))
		frappe.set_user(self.mgr_user)
		self.assertNotIn("error", api.save_supervisor({"employee": e.name}))
		self.assertTrue(frappe.db.exists("Production Supervisor", e.name))

	def test_list_visible_to_supervisor_role(self):
		frappe.set_user(self.sup_user)
		rows = api.list_supervisors(crop=self.crop.name)
		self.assertIsInstance(rows, list)
