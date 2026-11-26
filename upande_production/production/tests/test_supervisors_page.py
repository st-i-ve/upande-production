from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from upande_production.api import supervisors as api
from upande_production.production.logic import plans, supervisor_page, supervisors
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
		cls.asst_user = _user("spg.asst@x.test", "Production Assistant Manager")
		cls.view_user = _user("spg.view@x.test", "Production Viewer")
		cls.year, cls.week = iso_of(today())

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		super().tearDownClass()

	def setUp(self):
		frappe.db.savepoint("spg_test")
		self.addCleanup(frappe.db.rollback, save_point="spg_test")
		self.addCleanup(frappe.set_user, "Administrator")
		self.a = _employee("SPGA", self.company, cell_number="0700111222")
		self.b = _employee("SPGB", self.company)
		self.psa = _make("Production Supervisor", employee=self.a.name)
		self.psb = _make("Production Supervisor", employee=self.b.name)
		self.me = _employee("SPGMe", self.company, user_id=self.sup_user)
		self.psme = _make("Production Supervisor", employee=self.me.name)

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
		rows = supervisor_page.list_supervisors(crop=self.crop.name, year=self.year, week=self.week, **kw)
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

	def test_tasks_follow_the_sharing_rule_not_the_stored_supervisor(self):
		plan = self._plan()
		frappe.db.sql("update `tabWork Plan Task` set supervisor = NULL where parent = %s", plan.name)
		k = self._row(self.a)["kpis"]["tasks"]
		self.assertEqual((k["done"], k["late"], k["open"]), (1, 1, 1))
		self.assertEqual(self._row(self.b)["kpis"]["tasks"]["total"], 1)  # u2's weeding; spraying is a's
		d = supervisor_page.get_supervisor(self.a.name, crop=self.crop.name, year=self.year, week=self.week)
		self.assertEqual(d["tasks"]["total"], 3)

	def test_inactive_supervisor_holds_no_blocks(self):
		self._plan()
		self.psa.active = 0
		self.psa.save()
		row = self._row(self.a)
		self.assertEqual(row["kpis"]["blocks"], 0)
		self.assertEqual(row["kpis"]["tasks"]["total"], 0)
		d = supervisor_page.get_supervisor(self.a.name, crop=self.crop.name, year=self.year, week=self.week)
		self.assertEqual(d["blocks"], [])

	def _crew_with_pending(self, sup):
		x = _employee("SPGX", self.company, image="/files/x.png")
		self._labourer(x, sup)
		frappe.db.sql("""insert into `tabCasual Labour Work` (name, employee, crop, docstatus, approval_status, creation, modified, owner, modified_by)
			values ('SPGW-9', %s, %s, 0, 'Pending', now(), now(), 'Administrator', 'Administrator')""", (x.name, self.crop.name))
		return x

	def _as(self, user, fn, *a, **kw):
		frappe.set_user(user)
		try:
			return fn(*a, **kw)
		finally:
			frappe.set_user("Administrator")

	def test_managers_and_assistants_see_every_crew_and_pending(self):
		x = self._crew_with_pending(self.a)
		for user in (self.mgr_user, self.asst_user):
			rows = self._as(user, api.list_supervisors, crop=self.crop.name, year=self.year, week=self.week)
			self.assertEqual(next(r for r in rows if r["employee"] == self.a.name)["kpis"]["pending"], 1, user)
			d = self._as(user, api.get_supervisor, self.a.name, crop=self.crop.name)
			self.assertEqual([l["employee"] for l in d["labourers"]], [x.name], user)
			self.assertFalse(d["crew_hidden"])

	def test_plain_supervisor_sees_own_crew_but_not_others(self):
		self._crew_with_pending(self.a)
		mine = self._crew_with_pending_for_me()
		rows = self._as(self.sup_user, api.list_supervisors, crop=self.crop.name, year=self.year, week=self.week)
		by = {r["employee"]: r for r in rows}
		self.assertIsNone(by[self.a.name]["kpis"]["pending"])
		self.assertEqual(by[self.a.name]["kpis"]["crew"], 1)  # the count stays
		self.assertEqual(by[self.me.name]["kpis"]["pending"], 1)
		other = self._as(self.sup_user, api.get_supervisor, self.a.name, crop=self.crop.name)
		self.assertEqual(other["labourers"], [])
		self.assertTrue(other["crew_hidden"])
		self.assertIsNone(other["pending"])
		own = self._as(self.sup_user, api.get_supervisor, self.me.name, crop=self.crop.name)
		self.assertEqual([l["employee"] for l in own["labourers"]], [mine.name])
		self.assertFalse(own["crew_hidden"])

	def _crew_with_pending_for_me(self):
		y = _employee("SPGY", self.company)
		self._labourer(y, self.me)
		frappe.db.sql("""insert into `tabCasual Labour Work` (name, employee, crop, docstatus, approval_status, creation, modified, owner, modified_by)
			values ('SPGW-8', %s, %s, 0, 'Checked', now(), now(), 'Administrator', 'Administrator')""", (y.name, self.crop.name))
		return y

	def test_viewer_gets_cards_without_crew_or_pending(self):
		self._crew_with_pending(self.a)
		rows = self._as(self.view_user, api.list_supervisors, crop=self.crop.name, year=self.year, week=self.week)
		self.assertIsNone(next(r for r in rows if r["employee"] == self.a.name)["kpis"]["pending"])
		d = self._as(self.view_user, api.get_supervisor, self.a.name, crop=self.crop.name)
		self.assertEqual(d["labourers"], [])
		self.assertFalse(d["can_edit"])

	def test_crop_is_required(self):
		with self.assertRaises(frappe.ValidationError):
			supervisor_page.list_supervisors(None)
		with self.assertRaises(frappe.ValidationError):
			supervisor_page.get_supervisor(self.a.name, None)

	def test_get_supervisor_detail(self):
		self._plan()
		x = _employee("SPGX", self.company, image="/files/x.png")
		self._labourer(x, self.a)
		d = supervisor_page.get_supervisor(self.a.name, crop=self.crop.name, year=self.year, week=self.week)
		blocks = {b["unit"]: b for b in d["blocks"]}
		self.assertTrue(blocks[self.u1.name]["overseer"])
		self.assertEqual(blocks[self.u2.name]["categories"], ["Spraying"])
		self.assertFalse(blocks[self.u2.name]["overseer"])
		self.assertEqual(d["tasks"]["done"], 1)
		lab = d["labourers"][0]
		self.assertEqual((lab["employee"], lab["image"], lab["active"]), (x.name, "/files/x.png", 1))
		self.assertEqual(d["supervisor"]["employee"], self.a.name)
		self.assertTrue(d["can_edit"])

	def test_get_supervisor_unknown(self):
		with self.assertRaises(frappe.ValidationError):
			supervisor_page.get_supervisor("NOPE-1", self.crop.name)

	def test_save_supervisor_create_defaults_and_edit(self):
		e = _employee("SPGN", self.company, cell_number="0711", image="/files/n.png")
		res = api.save_supervisor({"employee": e.name, "farm": self.farm.name, "crops": [self.crop.name], "notes": "hi"})
		self.assertEqual(res["employee"], e.name)
		doc = frappe.get_doc("Production Supervisor", e.name)
		self.assertEqual((doc.phone, doc.image, doc.notes), ("0711", "/files/n.png", "hi"))
		self.assertEqual([c.crop for c in doc.crops], [self.crop.name])
		api.save_supervisor({"employee": e.name, "active": 0, "crops": []})
		doc.reload()
		self.assertEqual((doc.active, len(doc.crops), doc.notes), (0, 0, "hi"))

	def test_save_supervisor_manager_only(self):
		e = _employee("SPGM", self.company)
		frappe.set_user(self.sup_user)
		with self.assertRaises(frappe.PermissionError):
			supervisor_page.save_supervisor({"employee": e.name})
		self.assertFalse(frappe.db.exists("Production Supervisor", e.name))
		frappe.set_user(self.mgr_user)
		self.assertNotIn("error", api.save_supervisor({"employee": e.name}))
		self.assertTrue(frappe.db.exists("Production Supervisor", e.name))

	def test_save_supervisor_validates_crops_and_left_employee(self):
		e = _employee("SPGL", self.company)
		with self.assertRaises(frappe.ValidationError):
			supervisor_page.save_supervisor({"employee": e.name, "crops": "avocado"})
		frappe.db.set_value("Employee", e.name, "status", "Left")
		with self.assertRaises(frappe.ValidationError):
			supervisor_page.save_supervisor({"employee": e.name})
		self.assertNotIn("error", {"x": 1} | supervisor_page.save_supervisor({"employee": e.name, "active": 0}))

	def test_manager_limited_to_a_crop_cannot_edit_all_crop_supervisors(self):
		e = _employee("SPGX", self.company)
		with patch.object(supervisor_page, "crop_allowed", side_effect=lambda c: False), \
				patch.object(supervisor_page, "avocado_only_crop_keys", return_value={"avocado"}):
			with self.assertRaises(frappe.PermissionError):
				supervisor_page.save_supervisor({"employee": e.name})  # empty crops = every crop
			with self.assertRaises(frappe.PermissionError):
				supervisor_page.save_supervisor({"employee": e.name, "crops": [self.crop.name]})
		with patch.object(supervisor_page, "crop_allowed", side_effect=lambda c: True):
			supervisor_page.save_supervisor({"employee": e.name, "crops": [self.crop.name]})

	def test_counts_hide_awaiting_tasks_from_supervisors(self):
		self._plan()
		plan = frappe.get_all("Production Work Plan", filters={"crop": self.crop.name}, pluck="name")[0]
		for n in frappe.get_all("Work Plan Task", filters={"parent": plan}, pluck="name"):
			frappe.db.set_value("Work Plan Task", n, "awaiting_approval", 1)
		with patch.object(supervisor_page.task_approval, "visible_filter", return_value={"awaiting_approval": 0}):
			wk = supervisor_page._Week(self.crop.name, self.year, self.week)
		self.assertEqual(wk.tasks, [])

	def test_avocado_only_manager_can_create_for_avocado_not_for_all_or_others(self):
		avo = frappe.db.get_value("Production Crop", {"crop_key": "avocado"}) or _make(
			"Production Crop", crop_name="SPG Avocado", crop_key="avocado", unit_label="Block", yield_uom="Kg").name
		e = _employee("SPGAv", self.company)
		with patch.multiple(frappe, get_roles=lambda u=None: ["Avocado Production Manager"]), \
				patch.dict(frappe.local.session, {"user": "spg.avo@x.test"}):
			with self.assertRaises(frappe.PermissionError):
				supervisor_page.save_supervisor({"employee": e.name, "crops": []})
			with self.assertRaises(frappe.PermissionError):
				supervisor_page.save_supervisor({"employee": e.name, "crops": [self.crop.name]})
			supervisor_page.save_supervisor({"employee": e.name, "crops": [avo]})
			self.assertTrue(frappe.db.exists("Production Supervisor", e.name))
			# a record that also serves another crop is not theirs to edit
			doc = frappe.get_doc("Production Supervisor", e.name)
			doc.set("crops", [{"crop": avo}, {"crop": self.crop.name}])
			doc.save(ignore_permissions=True)
			with self.assertRaises(frappe.PermissionError):
				supervisor_page.save_supervisor({"employee": e.name, "notes": "x"})
