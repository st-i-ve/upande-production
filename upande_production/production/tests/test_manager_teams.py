import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import today

from upande_production.api import production as desk
from upande_production.api import supervisors as sup_api
from upande_production.production.logic import approvals, settings, task_approval, teams, work
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


class TestManagerTeams(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		use_builtin_labour(cls)
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make("Farm", farm_name="MT Farm", company=cls.company, abbreviation="MTF",
			farm_type=[{"farm_type": "Has Blocks"}])
		cls.crop = _make("Production Crop", crop_name="MT Crop", crop_key="mt-crop", unit_label="Block",
			yield_uom="Kg", uses_crop_cycles=1)
		cls.op = _make("Field Operation", crop=cls.crop.name, operation_name="MT Weeding",
			category="Other", work_uom="Kg", default_rate=40)
		cls.unit = _make("Production Unit", unit_name="MT B1", crop=cls.crop.name, farm=cls.farm.name,
			unit_type="Orchard Block", company=cls.company, area_ha=1, plant_count=0)
		cls.mA, cls.mB, cls.mC = (_user(f"mt.m{x}@x.test", "Production Manager") for x in "abc")
		cls.a, cls.b, cls.lone = (_user(f"mt.{x}@x.test", settings.ASSISTANT_ROLE) for x in ("a", "b", "lone"))
		cls.sup = _user("mt.sup@x.test", "Production Supervisor")
		cls.emps = {}
		for key, user in (("mA", cls.mA), ("mB", cls.mB), ("mC", cls.mC)):
			cls.emps[key] = cls._employee(key, user)
		cls.emps["a"] = cls._employee("a", cls.a, cls.emps["mA"])
		cls.emps["b"] = cls._employee("b", cls.b, cls.emps["mB"])
		cls.emps["lone"] = cls._employee("lone", cls.lone)
		cls.worker = cls._employee("worker")
		cls.year, cls.week = iso_of(today())
		cls.start, cls.end = iso_week_bounds(cls.year, cls.week)
		frappe.db.commit()

	@classmethod
	def _employee(cls, first, user=None, reports_to=None):
		return _make("Employee", first_name="MT" + first, gender="Male", date_of_birth="1990-01-01",
			date_of_joining="2020-01-01", company=cls.company, user_id=user, reports_to=reports_to).name

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		cls._wipe()
		for dt, name in (("Production Unit", cls.unit.name), ("Field Operation", cls.op.name),
				("Production Crop", cls.crop.name), ("Farm", cls.farm.name)):
			frappe.delete_doc(dt, name, force=True)
		for e in cls.emps.values():
			frappe.db.set_value("Employee", e, "reports_to", None)
		for e in [*cls.emps.values(), cls.worker]:
			frappe.delete_doc("Employee", e, force=True)
		for u in (cls.mA, cls.mB, cls.mC, cls.a, cls.b, cls.lone, cls.sup):
			frappe.delete_doc("User", u, force=True)
		frappe.db.commit()
		super().tearDownClass()

	@classmethod
	def _wipe(cls):
		frappe.db.delete("Casual Labour Work", {"employee": cls.worker})
		for p in frappe.get_all("Production Work Plan", filters={"crop": cls.crop.name}, pluck="name"):
			frappe.delete_doc("Production Work Plan", p, force=True)
		frappe.db.commit()

	def setUp(self):
		frappe.set_user("Administrator")
		teams.clear_cache()
		self.addCleanup(self._clean)

	def _clean(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		frappe.db.set_value("Employee", self.emps["lone"], "reports_to", None)
		self._wipe()
		teams.clear_cache()

	# -- helpers -------------------------------------------------------------------

	def _as(self, user, fn, *a, **kw):
		frappe.set_user(user)
		teams.clear_cache()
		try:
			return fn(*a, **kw)
		finally:
			frappe.set_user("Administrator")

	def _task(self, user):
		"""A task planned by `user`; (plan, task name)."""
		frappe.set_user(user)
		res = desk.save_plan_tasks(self.crop.name, self.farm.name, self.year, self.week,
			[{"unit": self.unit.name, "operation": self.op.name, "planned_qty": 5, "due_date": self.start}])
		frappe.set_user("Administrator")
		self.assertNotIn("error", res)
		names = frappe.get_all("Work Plan Task", filters={"parent": res["name"], "assigned_by": user}, pluck="name")
		frappe.db.commit()
		return res["name"], names[0]

	def _worked(self, user, qty=4):
		"""A forwarded task planned by `user` with one entry; (plan, task, entry)."""
		plan, task = self._task(user)
		self._as("Administrator", task_approval.forward, plan, [task], 1)
		frappe.db.commit()
		frappe.set_user(self.sup)
		res = work.record_task_work(plan, task, "In Progress", [{"employee": self.worker, "qty": qty}])
		frappe.set_user("Administrator")
		frappe.db.commit()
		return plan, task, res["work"][0]

	def _queue(self, user, **kw):
		res = self._as(user, approvals.list_approvals, queue="approve", **kw)
		mine = {g["crop"] for g in res["groups"]} and self.crop.name  # other data may sit in the queue: only our crop
		return {n for g in res["groups"] if g["crop"] == mine for n in g["names"]}

	def _awaiting(self, user, **kw):
		return {t["name"] for t in self._as(user, task_approval.awaiting_tasks, **kw)["tasks"]}

	# -- tests ---------------------------------------------------------------------

	def test_manager_of_and_team_of(self):
		self.assertEqual(teams.manager_of(self.a), self.mA)
		self.assertEqual(teams.manager_of(self.b), self.mB)
		self.assertIsNone(teams.manager_of(self.lone))
		self.assertEqual(teams.team_of(self.mA), {self.a})
		self.assertEqual(teams.team_of(self.mC), set())

	def test_reports_to_a_non_manager_has_no_manager(self):
		frappe.db.set_value("Employee", self.emps["lone"], "reports_to", self.emps["a"])  # a is not a manager
		teams.clear_cache()
		self.assertIsNone(teams.manager_of(self.lone))

	def test_step_is_always_on(self):
		self.assertTrue(settings.assistant_step_on())

	def test_awaiting_tasks_follow_the_team(self):
		_, ta = self._task(self.a)
		_, tb = self._task(self.b)
		self.assertEqual(self._awaiting(self.mA), {ta})
		self.assertEqual(self._awaiting(self.mB), {tb})
		self.assertEqual(self._awaiting(self.mC), set())
		self.assertEqual(self._awaiting(self.mC, all_teams=1), {ta, tb})

	def test_checked_work_in_team_queue_and_counts(self):
		_, _, ea = self._worked(self.a)
		_, _, eb = self._worked(self.b)
		self._as(self.a, approvals.check, [ea])
		self._as(self.b, approvals.check, [eb])
		self.assertEqual(self._queue(self.mA), {ea})
		self.assertEqual(self._queue(self.mB), {eb})
		self.assertEqual(self._queue(self.mC), set())
		self.assertEqual(self._queue(self.mC, all_teams=1), {ea, eb})
		ca, cb, cc = (self._as(m, approvals.approval_counts) for m in (self.mA, self.mB, self.mC))
		def mine(c, key="team_pending"):
			return next((x[key] for x in c["crops"] if x["crop"] == self.crop.name), 0)
		self.assertEqual((mine(ca), mine(cb), mine(cc)), (1, 1, 0))
		self.assertEqual(mine(ca, "pending"), 2)  # crops[].pending stays everything
		self.assertLessEqual(ca["team_total"], ca["all_total"])
		self.assertEqual(ca["total"], ca["team_total"])  # a manager's badge follows the team
		self.assertEqual(self._as(self.mC, approvals.approval_counts, all_teams=1)["total"], cc["all_total"])

	def test_pending_work_waits_for_the_check(self):
		_, _, ea = self._worked(self.a)
		self.assertEqual(self._queue(self.mA), {ea})  # listed (flagged needs_check), but not in the counts
		c = self._as(self.mA, approvals.approval_counts)
		self.assertEqual(next((x["pending"] for x in c["crops"] if x["crop"] == self.crop.name), 0), 0)

	def test_other_manager_needs_confirm_to_approve(self):
		_, _, ea = self._worked(self.a)
		self._as(self.a, approvals.check, [ea])
		with self.assertRaises(teams.OtherTeam) as cm:
			self._as(self.mB, approvals.approve, [ea])
		self.assertIn("team. Confirm to approve it anyway.", str(cm.exception))
		self.assertIn("This belongs to", str(cm.exception))
		self.assertEqual(frappe.db.get_value("Casual Labour Work", ea, "docstatus"), 0)
		res = self._as(self.mB, approvals.approve, [ea], 0, 1)
		self.assertEqual(res, {"approved": [ea]})
		self.assertEqual(frappe.db.get_value("Casual Labour Work", ea, "docstatus"), 1)

	def test_own_manager_needs_no_confirm(self):
		_, _, ea = self._worked(self.a)
		self._as(self.a, approvals.check, [ea])
		self.assertEqual(self._as(self.mA, approvals.approve, [ea]), {"approved": [ea]})

	def test_send_back_other_team_needs_confirm(self):
		_, _, ea = self._worked(self.a)
		self._as(self.a, approvals.check, [ea])
		with self.assertRaises(teams.OtherTeam):
			self._as(self.mB, approvals.send_back, [ea], "recount")
		self.assertEqual(self._as(self.mB, approvals.send_back, [ea], "recount", 1), {"sent_back": [ea]})

	def test_forward_other_team_needs_confirm(self):
		plan, ta = self._task(self.a)
		with self.assertRaises(teams.OtherTeam):
			self._as(self.mB, task_approval.forward, plan, [ta])
		self.assertEqual(frappe.db.get_value("Work Plan Task", ta, "awaiting_approval"), 1)
		res = self._as(self.mB, task_approval.forward, plan, [ta], 1)
		self.assertEqual((res["forwarded"], res["other_team"]), ([ta], [ta]))

	def test_desk_envelope_flags_needs_confirm(self):
		plan, ta = self._task(self.a)
		frappe.set_user(self.mB)
		res = desk.forward_plan_tasks(plan, [ta])
		frappe.set_user("Administrator")
		self.assertTrue(res.get("needs_confirm"))
		self.assertIn("Confirm to approve it anyway", res["error"])

	def test_manager_without_assistants_own_tasks_need_no_approval(self):
		plan, tc = self._task(self.mC)
		row = frappe.db.get_value("Work Plan Task", tc, ["awaiting_approval", "assigned_by"], as_dict=True)
		self.assertEqual((row.awaiting_approval, row.assigned_by), (0, self.mC))
		frappe.set_user(self.sup)
		res = work.record_task_work(plan, tc, "In Progress", [{"employee": self.worker, "qty": 3}])
		frappe.set_user("Administrator")
		e = res["work"][0]
		for m in (self.mA, self.mB, self.mC):  # no team: in every manager's queue, no confirm
			self.assertEqual(self._queue(m), {e}, m)
		self.assertEqual(self._as(self.mA, approvals.approve, [e]), {"approved": [e]})

	def test_assistant_without_manager_goes_to_every_manager(self):
		plan, tl = self._task(self.lone)
		for m in (self.mA, self.mB, self.mC):
			self.assertIn(tl, self._awaiting(m), m)
		self._as("Administrator", task_approval.forward, plan, [tl], 1)
		frappe.db.commit()
		frappe.set_user(self.sup)
		el = work.record_task_work(plan, tl, "In Progress", [{"employee": self.worker, "qty": 4}])["work"][0]
		frappe.set_user("Administrator")
		self._as(self.lone, approvals.check, [el])
		for m in (self.mA, self.mB, self.mC):
			self.assertIn(el, self._queue(m), m)
		self.assertEqual(self._as(self.mB, approvals.approve, [el]), {"approved": [el]})  # no confirm needed

	def test_assistants_without_manager_listed(self):
		got = {r["user"]: r for r in self._as(self.mA, sup_api.supervisor_page.assistants_without_manager)}
		self.assertIn(self.lone, got)
		self.assertNotIn(self.a, got)
		self.assertEqual(got[self.lone]["reason"], "no_reports_to")
