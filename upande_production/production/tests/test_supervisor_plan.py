from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from upande_production.api import production as desk
from upande_production.mobile import api as mobile
from upande_production.production.logic import plans, supervisors
from upande_production.production.logic.weeks import iso_of, iso_week_bounds
from upande_production.production.tests.labour_mode import use_builtin_labour

ROLES = {"manager": ["Production Manager"], "supervisor": ["Production Supervisor"], "viewer": ["Production Viewer"]}


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


def _user(email, role):
	if not frappe.db.exists("User", email):
		_make("User", email=email, first_name=email.split("@")[0], send_welcome_email=0, roles=[{"role": role}])
	return email


def _employee(first, company, user=None):
	return _make(
		"Employee", first_name=first, gender="Male", date_of_birth="1990-01-01",
		date_of_joining="2020-01-01", company=company, user_id=user,
	)


class TestSupervisorPlan(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		use_builtin_labour(cls)
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make("Farm", farm_name="SP Farm", company=cls.company, abbreviation="SPF",
			farm_type=[{"farm_type": "Has Blocks"}])
		cls.crop = _make("Production Crop", crop_name="SP Crop", crop_key="sp-crop", unit_label="Block", yield_uom="Kg")
		cls.op = _make("Field Operation", crop=cls.crop.name, operation_name="SP Weeding",
			category="Other", work_uom="Kg", default_rate=40)
		cls.spray = _make("Field Operation", crop=cls.crop.name, operation_name="SP Spraying",
			category="Spraying", work_uom="Kg", default_rate=40)
		cls.u1 = _make("Production Unit", unit_name="SP B1", crop=cls.crop.name, farm=cls.farm.name,
			unit_type="Orchard Block", company=cls.company)
		cls.u2 = _make("Production Unit", unit_name="SP B2", crop=cls.crop.name, farm=cls.farm.name,
			unit_type="Orchard Block", company=cls.company)
		cls.sup_user = _user("sp.sup@x.test", "Production Supervisor")
		cls.mgr_user = _user("sp.mgr@x.test", "Production Manager")
		cls.noemp_user = _user("sp.noemp@x.test", "Production Supervisor")
		cls.sup = _employee("SPSup", cls.company, cls.sup_user)
		cls.mgr = _employee("SPMgr", cls.company, cls.mgr_user)
		cls.other = _employee("SPOther", cls.company)
		cls.third = _employee("SPThird", cls.company)
		cls.year, cls.week = iso_of(today())

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		super().tearDownClass()

	def setUp(self):
		# each test starts from the class fixtures only: assignments, plans and tasks go with its savepoint
		frappe.db.savepoint("sp_test")
		self.addCleanup(frappe.db.rollback, save_point="sp_test")

	def assign(self, rows, **kw):
		return supervisors.save_week(self.crop.name, self.farm.name, kw.get("year", self.year), kw.get("week", self.week), rows)

	def plan_with_tasks(self, units=None, ops=None):
		plan = plans.get_or_create_plan(self.crop.name, self.farm.name, self.year, self.week)
		for u in units or [self.u1.name, self.u2.name]:
			for op in ops or [self.op.name]:
				self._add(plan, u, op)
		plan.save()
		return plan

	def _add(self, plan, u, op):
		plan.append("tasks", {"unit": u, "operation": op, "planned_qty": 5, "uom": "Kg", "rate": 40,
			"due_date": today(), "status": "Open"})

	def tasks(self, plan):
		return {t.unit: t for t in frappe.get_doc("Production Work Plan", plan.name).tasks}

	def tasks_by_op(self, plan, unit):
		return {t.operation: t for t in frappe.get_doc("Production Work Plan", plan.name).tasks if t.unit == unit}

	def call(self, fn, payload, user, roles):
		frappe.response.pop("data", None)
		with patch.multiple(frappe, get_roles=lambda u=None: ROLES[roles]), patch.dict(frappe.local.session, {"user": user}), \
				patch.object(frappe.local, "request", SimpleNamespace(get_json=lambda: payload), create=True):
			fn()
		return frappe.response["data"]

	# -- doctype ---------------------------------------------------------------

	def test_one_row_per_block_week_category_supervisor_and_week_start(self):
		a = _make("Production Supervisor Assignment", crop=self.crop.name, unit=self.u1.name,
			supervisor=self.sup.name, plan_year=self.year, plan_week=self.week)
		self.assertEqual(str(a.week_start), str(iso_week_bounds(self.year, self.week)[0]))
		self.assertEqual(a.farm, self.farm.name)
		self.assertEqual(a.supervisor_name, self.sup.employee_name)
		self.assertEqual(a.user, self.sup_user)
		with self.assertRaises(frappe.DuplicateEntryError):
			_make("Production Supervisor Assignment", crop=self.crop.name, unit=self.u1.name,
				supervisor=self.sup.name, plan_year=self.year, plan_week=self.week)
		# the same supervisor under another category, or another supervisor, is fine
		_make("Production Supervisor Assignment", crop=self.crop.name, unit=self.u1.name, category="Spraying",
			supervisor=self.sup.name, plan_year=self.year, plan_week=self.week)
		with self.assertRaises(frappe.DuplicateEntryError):
			_make("Production Supervisor Assignment", crop=self.crop.name, unit=self.u1.name, category="Spraying",
				supervisor=self.sup.name, plan_year=self.year, plan_week=self.week)
		# another week is fine, and one supervisor may hold many blocks
		_make("Production Supervisor Assignment", crop=self.crop.name, unit=self.u1.name,
			supervisor=self.mgr.name, plan_year=self.year, plan_week=self.week + 1 if self.week < 52 else 1)
		_make("Production Supervisor Assignment", crop=self.crop.name, unit=self.u2.name,
			supervisor=self.sup.name, plan_year=self.year, plan_week=self.week)

	def test_block_must_belong_to_crop(self):
		other = _make("Production Crop", crop_name="SP Other", crop_key="sp-other", unit_label="Block", yield_uom="Kg")
		with self.assertRaises(frappe.ValidationError):
			_make("Production Supervisor Assignment", crop=other.name, unit=self.u1.name,
				supervisor=self.sup.name, plan_year=self.year, plan_week=self.week)

	# -- save / copy -----------------------------------------------------------

	def test_save_replaces_the_week(self):
		self.assign([{"unit": self.u1.name, "supervisor": self.sup.name}, {"unit": self.u2.name, "supervisor": self.sup.name}])
		self.assign([{"unit": self.u2.name, "supervisor": self.mgr.name}])
		rows = {a.unit: a.supervisor for a in supervisors.assignments(self.crop.name, self.year, self.week)}
		self.assertEqual(rows, {self.u2.name: self.mgr.name})

	def test_save_refuses_a_non_manager_and_foreign_blocks(self):
		with patch.multiple(frappe, get_roles=lambda u=None: ROLES["supervisor"]), patch.dict(frappe.local.session, {"user": self.sup_user}):
			with self.assertRaises(frappe.PermissionError):
				self.assign([{"unit": self.u1.name, "supervisor": self.sup.name}])
		with self.assertRaises(frappe.ValidationError):
			self.assign([{"unit": "no-such-block", "supervisor": self.sup.name}])
		with self.assertRaises(frappe.ValidationError):
			self.assign([{"unit": self.u1.name, "supervisor": self.sup.name}, {"unit": self.u1.name, "supervisor": self.sup.name}])
		with self.assertRaises(frappe.ValidationError):
			self.assign([{"unit": self.u1.name, "supervisor": self.sup.name, "category": "Nonsense"}])

	def test_copy_last_week_into_an_empty_week(self):
		py, pw = supervisors.previous_week(self.year, self.week)
		self.assign([{"unit": self.u1.name, "supervisor": self.sup.name}], year=py, week=pw)
		res = supervisors.copy_week(self.crop.name, self.farm.name, self.year, self.week)
		self.assertEqual(res["copied"], 1)
		self.assertEqual([a.supervisor for a in supervisors.assignments(self.crop.name, self.year, self.week)], [self.sup.name])
		with self.assertRaises(frappe.ValidationError):  # now not empty
			supervisors.copy_week(self.crop.name, self.farm.name, self.year, self.week)

	def test_copy_refuses_when_last_week_is_empty(self):
		with self.assertRaises(frappe.ValidationError):
			supervisors.copy_week(self.crop.name, self.farm.name, self.year, self.week)

	def test_get_week_lists_blocks_candidates_and_last_week(self):
		for e in (self.sup, self.mgr):
			_make("Production Supervisor", employee=e.name)
		_make("Production Supervisor", employee=self.other.name, active=0)  # inactive, but already assigned below
		py, pw = supervisors.previous_week(self.year, self.week)
		self.assign([{"unit": self.u1.name, "supervisor": self.other.name}], year=py, week=pw)
		self.assign([{"unit": self.u2.name, "supervisor": self.other.name}])
		res = supervisors.get_week(self.crop.name, self.farm.name, self.year, self.week)
		self.assertEqual({u.name for u in res["units"]}, {self.u1.name, self.u2.name})
		names = {s.name for s in res["supervisors"]}
		self.assertTrue({self.sup.name, self.mgr.name, self.other.name} <= names)  # other: already assigned
		self.assertEqual([a.unit for a in res["last_week"]], [self.u1.name])
		self.assertEqual(res["last_week_label"], {"year": py, "week": pw})

	def test_leave_is_a_warning_not_a_block(self):
		start, end = iso_week_bounds(self.year, self.week)
		fake = [frappe._dict(employee=self.sup.name, employee_name="SPSup", from_date=start, to_date=end)]
		real = frappe.get_all
		with patch.object(frappe, "get_all", side_effect=lambda dt, *a, **k: fake if dt == "Leave Application" else real(dt, *a, **k)):
			res = self.assign([{"unit": self.u1.name, "supervisor": self.sup.name}])
		self.assertEqual(res["saved"], 1)
		self.assertEqual(len(res["warnings"]), 1)
		self.assertIn("approved leave", res["warnings"][0]["message"])

	# -- tasks follow the mapping ----------------------------------------------

	def test_generate_style_new_tasks_take_the_weeks_supervisor(self):
		self.assign([{"unit": self.u1.name, "supervisor": self.sup.name}])
		t = self.tasks(self.plan_with_tasks())
		self.assertEqual(t[self.u1.name].supervisor, self.sup.name)
		self.assertEqual(t[self.u1.name].supervisor_from_plan, 1)
		self.assertFalse(t[self.u2.name].supervisor)

	def test_saving_the_supervisor_plan_updates_existing_tasks_and_follows_changes(self):
		plan = self.plan_with_tasks()
		self.assertFalse(self.tasks(plan)[self.u1.name].supervisor)
		res = self.assign([{"unit": self.u1.name, "supervisor": self.sup.name}])
		self.assertEqual(res["tasks_updated"], 1)
		self.assertEqual(self.tasks(plan)[self.u1.name].supervisor, self.sup.name)
		self.assign([{"unit": self.u1.name, "supervisor": self.mgr.name}])
		self.assertEqual(self.tasks(plan)[self.u1.name].supervisor, self.mgr.name)
		self.assign([])  # the block is no longer assigned: the mapped supervisor goes
		t = self.tasks(plan)[self.u1.name]
		self.assertFalse(t.supervisor)
		self.assertEqual(t.supervisor_from_plan, 0)

	def test_a_hand_set_supervisor_is_never_overridden(self):
		plan = self.plan_with_tasks()
		desk.save_plan_tasks(self.crop.name, self.farm.name, self.year, self.week,
			[{"name": next(t.name for t in plan.tasks if t.unit == self.u1.name), "supervisor": self.other.name}])
		t = self.tasks(plan)[self.u1.name]
		self.assertEqual((t.supervisor, t.supervisor_from_plan), (self.other.name, 0))
		self.assign([{"unit": self.u1.name, "supervisor": self.sup.name}])
		self.assertEqual(self.tasks(plan)[self.u1.name].supervisor, self.other.name)

	def test_manager_overriding_a_mapped_supervisor_makes_it_hand_set(self):
		self.assign([{"unit": self.u1.name, "supervisor": self.sup.name}])
		plan = self.plan_with_tasks()
		name = next(t.name for t in plan.tasks if t.unit == self.u1.name)
		desk.save_plan_tasks(self.crop.name, self.farm.name, self.year, self.week, [{"name": name, "supervisor": self.other.name}])
		self.assign([{"unit": self.u1.name, "supervisor": self.mgr.name}])
		t = self.tasks(plan)[self.u1.name]
		self.assertEqual((t.supervisor, t.supervisor_from_plan), (self.other.name, 0))

	def test_added_task_takes_the_mapping(self):
		self.assign([{"unit": self.u2.name, "supervisor": self.sup.name}])
		plan = self.plan_with_tasks([self.u1.name])
		desk.save_plan_tasks(self.crop.name, self.farm.name, self.year, self.week,
			[{"unit": self.u2.name, "operation": self.op.name, "planned_qty": 3, "due_date": str(today())}])
		self.assertEqual(self.tasks(plan)[self.u2.name].supervisor, self.sup.name)

	# -- desk endpoints --------------------------------------------------------

	def test_desk_endpoints_save_and_copy(self):
		res = desk.save_supervisor_plan(self.crop.name, self.farm.name, self.year, self.week,
			[{"unit": self.u1.name, "supervisor": self.sup.name}])
		self.assertEqual(res["saved"], 1)
		self.assertEqual([a["unit"] for a in res["assignments"]], [self.u1.name])
		res = desk.get_supervisor_plan(self.crop.name, self.farm.name, self.year, self.week)
		self.assertTrue(res["can_edit"])
		py, pw = supervisors.previous_week(self.year, self.week + 1 if self.week < 52 else 1)
		self.assertEqual((py, pw), (self.year, self.week))
		res = desk.copy_supervisor_plan(self.crop.name, self.farm.name, *iso_of(add_days(iso_week_bounds(self.year, self.week)[0], 7)))
		self.assertEqual(res["copied"], 1)
		self.assertEqual([a["unit"] for a in res["assignments"]], [self.u1.name])

	# -- the phone: only mine --------------------------------------------------

	def phone_setup(self):
		self.assign([{"unit": self.u1.name, "supervisor": self.sup.name}, {"unit": self.u2.name, "supervisor": self.mgr.name}])
		return self.plan_with_tasks()

	def units_of(self, res):
		return sorted(t["unit"] for t in res["tasks"])

	def test_supervisor_sees_only_their_tasks_even_asking_for_all(self):
		self.phone_setup()
		p = {"crop": self.crop.name, "farm": self.farm.name, "mine": False}
		res = self.call(mobile.productionGetWeekPlan, p, self.sup_user, "supervisor")
		self.assertEqual(self.units_of(res), [self.u1.name])
		self.assertTrue(res["mine"])
		self.assertEqual([u["unit"] for u in res["assignments"]["units"]], [self.u1.name])
		det = self.call(mobile.productionGetPlanDetail, p, self.sup_user, "supervisor")
		self.assertEqual([b["unit"] for b in det["blocks"]], [self.u1.name])
		self.assertEqual(det["tasks_total"], 1)
		lst = self.call(mobile.productionListWeekPlans, p, self.sup_user, "supervisor")
		self.assertEqual(lst["plans"][0]["tasks_total"], 1)

	def test_supervisor_cannot_ask_for_another_block_through_unit(self):
		self.phone_setup()
		det = self.call(mobile.productionGetPlanDetail,
			{"crop": self.crop.name, "farm": self.farm.name, "unit": self.u2.name}, self.sup_user, "supervisor")
		self.assertEqual(det["blocks"], [])

	def test_supervisor_without_an_employee_gets_nothing_and_a_message(self):
		self.phone_setup()
		res = self.call(mobile.productionGetWeekPlan, {"crop": self.crop.name, "farm": self.farm.name}, self.noemp_user, "supervisor")
		self.assertEqual(res["tasks"], [])
		self.assertIn("not linked to an Employee", res["message"])
		det = self.call(mobile.productionGetPlanDetail, {"crop": self.crop.name, "farm": self.farm.name}, self.noemp_user, "supervisor")
		self.assertEqual(det["blocks"], [])
		self.assertIn("not linked to an Employee", det["message"])

	def test_manager_sees_all_by_default_and_mine_on_request(self):
		self.phone_setup()
		p = {"crop": self.crop.name, "farm": self.farm.name}
		res = self.call(mobile.productionGetWeekPlan, p, self.mgr_user, "manager")
		self.assertEqual(self.units_of(res), sorted([self.u1.name, self.u2.name]))
		self.assertEqual([u["unit"] for u in res["assignments"]["units"]], [self.u2.name])
		mine = self.call(mobile.productionGetWeekPlan, {**p, "mine": True}, self.mgr_user, "manager")
		self.assertEqual(self.units_of(mine), [self.u2.name])
		det = self.call(mobile.productionGetPlanDetail, {**p, "mine": True}, self.mgr_user, "manager")
		self.assertEqual([b["unit"] for b in det["blocks"]], [self.u2.name])

	def test_viewer_still_sees_the_whole_plan(self):
		self.phone_setup()
		res = self.call(mobile.productionGetWeekPlan, {"crop": self.crop.name, "farm": self.farm.name}, self.noemp_user, "viewer")
		self.assertEqual(len(res["tasks"]), 2)

	# -- per-activity assignments ---------------------------------------------

	def mk_sup(self, emp, active=1):
		if not frappe.db.exists("Production Supervisor", emp.name):
			_make("Production Supervisor", employee=emp.name, active=active)

	def shared_setup(self):
		"""sup = overseer of u1; mgr and other share Spraying on u1."""
		for e in (self.sup, self.mgr, self.other):
			self.mk_sup(e)
		self.assign([
			{"unit": self.u1.name, "supervisor": self.sup.name},
			{"unit": self.u1.name, "category": "Spraying", "supervisor": self.mgr.name},
			{"unit": self.u1.name, "category": "Spraying", "supervisor": self.other.name},
		])
		return self.plan_with_tasks([self.u1.name], [self.op.name, self.spray.name])

	def test_overseer_only_gets_every_task(self):
		self.mk_sup(self.sup)
		self.assign([{"unit": self.u1.name, "supervisor": self.sup.name}])
		t = self.tasks_by_op(self.plan_with_tasks([self.u1.name], [self.op.name, self.spray.name]), self.u1.name)
		self.assertEqual({t[self.op.name].supervisor, t[self.spray.name].supervisor}, {self.sup.name})

	def test_category_rows_route_to_first_sharer_else_overseer(self):
		t = self.tasks_by_op(self.shared_setup(), self.u1.name)
		self.assertEqual(t[self.spray.name].supervisor, self.mgr.name)
		self.assertEqual(t[self.op.name].supervisor, self.sup.name)
		self.assertEqual(t[self.spray.name].supervisor_from_plan, 1)

	def test_inactive_category_supervisor_is_ignored(self):
		self.mk_sup(self.sup)
		self.mk_sup(self.mgr, active=0)
		self.assign([{"unit": self.u1.name, "supervisor": self.sup.name},
			{"unit": self.u1.name, "category": "Spraying", "supervisor": self.mgr.name}])
		t = self.tasks_by_op(self.plan_with_tasks([self.u1.name], [self.spray.name]), self.u1.name)
		self.assertEqual(t[self.spray.name].supervisor, self.sup.name)

	def test_category_row_without_overseer_leaves_other_tasks_unassigned(self):
		self.mk_sup(self.mgr)
		self.assign([{"unit": self.u1.name, "category": "Spraying", "supervisor": self.mgr.name}])
		t = self.tasks_by_op(self.plan_with_tasks([self.u1.name], [self.op.name, self.spray.name]), self.u1.name)
		self.assertEqual(t[self.spray.name].supervisor, self.mgr.name)
		self.assertFalse(t[self.op.name].supervisor)

	def test_reordering_sharers_changes_who_the_task_goes_to(self):
		plan = self.shared_setup()
		self.assign([
			{"unit": self.u1.name, "supervisor": self.sup.name},
			{"unit": self.u1.name, "category": "Spraying", "supervisor": self.other.name},
			{"unit": self.u1.name, "category": "Spraying", "supervisor": self.mgr.name},
		])
		self.assertEqual(self.tasks_by_op(plan, self.u1.name)[self.spray.name].supervisor, self.other.name)

	def test_copy_week_copies_categories(self):
		self.mk_sup(self.sup)
		self.mk_sup(self.mgr)
		py, pw = supervisors.previous_week(self.year, self.week)
		self.assign([{"unit": self.u1.name, "supervisor": self.sup.name},
			{"unit": self.u1.name, "category": "Spraying", "supervisor": self.mgr.name}], year=py, week=pw)
		supervisors.copy_week(self.crop.name, self.farm.name, self.year, self.week)
		rows = [(a.unit, a.category or "", a.supervisor) for a in supervisors.assignments(self.crop.name, self.year, self.week)]
		self.assertEqual(sorted(rows), sorted([(self.u1.name, "", self.sup.name), (self.u1.name, "Spraying", self.mgr.name)]))

	def test_desk_endpoint_accepts_and_returns_category(self):
		self.mk_sup(self.sup)
		res = desk.save_supervisor_plan(self.crop.name, self.farm.name, self.year, self.week,
			[{"unit": self.u1.name, "supervisor": self.sup.name},
			{"unit": self.u1.name, "category": "Spraying", "supervisor": self.sup.name}])
		self.assertEqual(res["saved"], 2)
		self.assertEqual(sorted((a["category"] or "") for a in res["assignments"]), ["", "Spraying"])

	def phone_units(self, user, roles, **extra):
		res = self.call(mobile.productionGetWeekPlan, {"crop": self.crop.name, "farm": self.farm.name, **extra}, user, roles)
		return sorted(t["operation"] for t in res["tasks"])

	def test_sharers_see_the_spraying_task_overseer_does_not_stranger_nothing(self):
		self.shared_setup()
		for e, u in ((self.sup, self.sup_user), (self.mgr, self.mgr_user), (self.other, "sp.other@x.test")):
			if e.user_id != u:
				frappe.db.set_value("Employee", e.name, "user_id", _user(u, "Production Supervisor"))
		sp, wd = self.spray.name, self.op.name
		self.assertEqual(self.phone_units(self.sup_user, "supervisor"), [wd])
		self.assertEqual(self.phone_units("sp.other@x.test", "supervisor"), [sp])
		frappe.db.set_value("Employee", self.mgr.name, "user_id", self.mgr_user)
		self.assertEqual(self.phone_units(self.mgr_user, "manager", mine=True), [sp])
		self.assertEqual(self.phone_units(self.noemp_user, "supervisor"), [])
		det = self.call(mobile.productionGetPlanDetail, {"crop": self.crop.name, "farm": self.farm.name}, "sp.other@x.test", "supervisor")
		self.assertEqual(det["tasks_total"], 1)
		lst = self.call(mobile.productionListWeekPlans, {"crop": self.crop.name, "farm": self.farm.name}, self.sup_user, "supervisor")
		self.assertEqual(lst["plans"][0]["tasks_total"], 1)

	def test_overseer_sees_the_category_when_no_active_sharer(self):
		self.mk_sup(self.sup)
		self.mk_sup(self.mgr, active=0)
		self.assign([{"unit": self.u1.name, "supervisor": self.sup.name},
			{"unit": self.u1.name, "category": "Spraying", "supervisor": self.mgr.name}])
		self.plan_with_tasks([self.u1.name], [self.op.name, self.spray.name])
		self.assertEqual(self.phone_units(self.sup_user, "supervisor"), sorted([self.op.name, self.spray.name]))

	def test_hand_set_supervisor_sees_their_task(self):
		self.shared_setup()
		plan = frappe.get_doc("Production Work Plan", frappe.db.get_value("Production Work Plan", {"crop": self.crop.name}))
		name = next(t.name for t in plan.tasks if t.operation == self.spray.name)
		desk.save_plan_tasks(self.crop.name, self.farm.name, self.year, self.week, [{"name": name, "supervisor": self.sup.name}])
		self.assertEqual(self.phone_units(self.sup_user, "supervisor"), sorted([self.op.name, self.spray.name]))

	def test_one_overseer_per_block_per_week(self):
		with self.assertRaises(frappe.ValidationError):
			self.assign([{"unit": self.u1.name, "supervisor": self.sup.name}, {"unit": self.u1.name, "supervisor": self.mgr.name}])
		_make("Production Supervisor Assignment", crop=self.crop.name, unit=self.u1.name,
			supervisor=self.sup.name, plan_year=self.year, plan_week=self.week)
		with self.assertRaises(frappe.ValidationError):
			_make("Production Supervisor Assignment", crop=self.crop.name, unit=self.u1.name,
				supervisor=self.mgr.name, plan_year=self.year, plan_week=self.week)

	def test_inactive_overseer_gets_no_tasks_and_no_visibility(self):
		self.mk_sup(self.sup, active=0)
		self.assign([{"unit": self.u1.name, "supervisor": self.sup.name}])
		plan = self.plan_with_tasks([self.u1.name])
		self.assertFalse(self.tasks(plan)[self.u1.name].supervisor)
		self.assertEqual(self.phone_units(self.sup_user, "supervisor"), [])

	def test_active_lookup_is_batched(self):
		self.shared_setup()
		calls = []
		real = frappe.get_all
		def spy(dt, *a, **k):
			calls.append(dt)
			return real(dt, *a, **k)
		with patch.object(frappe, "get_all", side_effect=spy):
			supervisors.visible_to(self.sup.name, [{"unit": self.u1.name, "operation": self.spray.name, "supervisor": None}] * 5,
				supervisors.assignments(self.crop.name, self.year, self.week))
		self.assertEqual(calls.count("Production Supervisor"), 1)

	def test_stranger_on_another_block_sees_nothing(self):
		self.mk_sup(self.other)
		frappe.db.set_value("Employee", self.other.name, "user_id", _user("sp.other@x.test", "Production Supervisor"))
		self.assign([{"unit": self.u1.name, "supervisor": self.sup.name}, {"unit": self.u2.name, "supervisor": self.other.name}])
		self.plan_with_tasks([self.u1.name], [self.op.name, self.spray.name])
		self.assertEqual(self.phone_units("sp.other@x.test", "supervisor"), [])

	def test_legacy_null_category_row_acts_as_overseer(self):
		a = _make("Production Supervisor Assignment", crop=self.crop.name, unit=self.u1.name,
			supervisor=self.sup.name, plan_year=self.year, plan_week=self.week)
		frappe.db.set_value("Production Supervisor Assignment", a.name, "category", None)
		t = self.tasks_by_op(self.plan_with_tasks([self.u1.name], [self.spray.name]), self.u1.name)
		self.assertEqual(t[self.spray.name].supervisor, self.sup.name)
		self.assertEqual(self.phone_units(self.sup_user, "supervisor"), [self.spray.name])

	def test_my_assignments_lists_each_block_once_with_categories(self):
		self.shared_setup()
		self.assign([{"unit": self.u1.name, "supervisor": self.sup.name},
			{"unit": self.u1.name, "category": "Spraying", "supervisor": self.sup.name},
			{"unit": self.u1.name, "category": "Weeding", "supervisor": self.sup.name}])
		res = supervisors.my_assignments(self.sup.name, self.crop.name, self.year, self.week, self.farm.name)
		self.assertEqual(len(res["units"]), 1)
		self.assertEqual(res["units"][0]["unit"], self.u1.name)
		self.assertEqual(sorted(res["units"][0]["categories"]), ["Spraying", "Weeding"])
		self.assertTrue(res["units"][0]["overseer"])

	# -- final review fixes ------------------------------------------------------

	def test_a_supervisor_whose_employee_left_is_inactive(self):
		self.mk_sup(self.sup)
		self.assign([{"unit": self.u1.name, "supervisor": self.sup.name}, {"unit": self.u2.name, "supervisor": self.other.name}])
		rows = supervisors.assignments(self.crop.name, self.year, self.week)
		self.assertEqual(supervisors.active_map(rows), {self.sup.name: True, self.other.name: True})
		frappe.db.set_value("Employee", self.sup.name, "status", "Left")
		frappe.db.set_value("Employee", self.other.name, "status", "Inactive")  # no supervisor record, not Active
		self.assertEqual(supervisors.active_map(rows), {self.sup.name: False, self.other.name: False})

	def test_deactivating_a_supervisor_reroutes_the_current_weeks_open_tasks(self):
		from upande_production.production.logic import supervisor_page
		self.mk_sup(self.sup)
		self.mk_sup(self.mgr)
		self.assign([{"unit": self.u1.name, "supervisor": self.sup.name}, {"unit": self.u1.name, "supervisor": self.mgr.name, "category": "Other"}])
		plan = self.plan_with_tasks([self.u1.name])
		self.assertEqual(self.tasks(plan)[self.u1.name].supervisor, self.mgr.name)
		supervisor_page.save_supervisor({"employee": self.mgr.name, "active": 0})
		self.assertEqual(self.tasks(plan)[self.u1.name].supervisor, self.sup.name)

	def test_finished_tasks_keep_their_supervisor(self):
		self.mk_sup(self.sup)
		self.mk_sup(self.mgr)
		self.assign([{"unit": self.u1.name, "supervisor": self.sup.name}])
		plan = self.plan_with_tasks([self.u1.name], [self.op.name, self.spray.name])
		for t in frappe.get_doc("Production Work Plan", plan.name).tasks:
			frappe.db.set_value("Work Plan Task", t.name, "status", "Done" if t.operation == self.op.name else "Open")
		self.assign([{"unit": self.u1.name, "supervisor": self.mgr.name}])
		by = self.tasks_by_op(plan, self.u1.name)
		self.assertEqual(by[self.op.name].supervisor, self.sup.name)
		self.assertEqual(by[self.spray.name].supervisor, self.mgr.name)

	def test_a_task_with_labour_work_keeps_its_supervisor(self):
		self.mk_sup(self.sup)
		self.mk_sup(self.mgr)
		self.assign([{"unit": self.u1.name, "supervisor": self.sup.name}])
		plan = self.plan_with_tasks([self.u1.name])
		task = frappe.get_doc("Production Work Plan", plan.name).tasks[0]
		with patch.object(supervisors, "worked_tasks", return_value={task.name}):
			self.assign([{"unit": self.u1.name, "supervisor": self.mgr.name}])
		self.assertEqual(self.tasks(plan)[self.u1.name].supervisor, self.sup.name)

	def test_save_week_takes_only_active_supervisors_but_keeps_existing(self):
		self.mk_sup(self.sup, active=0)
		with self.assertRaises(frappe.ValidationError):
			self.assign([{"unit": self.u1.name, "supervisor": self.sup.name}])
		self.mk_sup(self.mgr)
		self.assign([{"unit": self.u1.name, "supervisor": self.mgr.name}])
		frappe.db.set_value("Production Supervisor", self.mgr.name, "active", 0)
		self.assign([{"unit": self.u1.name, "supervisor": self.mgr.name}])  # unchanged on re-save

	def test_my_assignments_drops_an_inactive_supervisor(self):
		self.mk_sup(self.sup)
		self.assign([{"unit": self.u1.name, "supervisor": self.sup.name}])
		frappe.db.set_value("Production Supervisor", self.sup.name, "active", 0)
		res = supervisors.my_assignments(self.sup.name, self.crop.name, self.year, self.week, self.farm.name)
		self.assertEqual(res["units"], [])
