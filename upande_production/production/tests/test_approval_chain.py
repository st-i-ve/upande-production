import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import today

from upande_production.api import production as desk
from upande_production.production.logic import approvals, cycle_setup, plans, settings, task_approval, work
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
		cls.u2 = _make("Production Unit", unit_name="ACH B2", crop=cls.crop.name, farm=cls.farm.name,
			unit_type="Orchard Block", company=cls.company, area_ha=1, plant_count=0)
		cls.mgr = _user("ach.mgr@x.test", "Production Manager")
		cls.sup = _user("ach.sup@x.test", "Production Supervisor")
		cls.asst = _user("ach.asst@x.test", settings.ASSISTANT_ROLE)
		cls.emp = _make("Employee", first_name="ACHEmp", gender="Male", date_of_birth="1990-01-01",
			date_of_joining="2020-01-01", company=cls.company).name
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
		for dt, name in (("Production Unit", cls.u1.name), ("Production Unit", cls.u2.name), ("Production Protocol", cls.protocol),
				("Field Operation", cls.op.name), ("Item", cls.item), ("Production Crop", cls.crop.name),
				("Farm", cls.farm.name)):
			frappe.delete_doc(dt, name, force=True)
		for u in (cls.mgr, cls.sup, cls.asst):
			frappe.delete_doc("User", u, force=True)
		frappe.db.delete("Casual Labour Work", {"employee": cls.emp})
		frappe.delete_doc("Employee", cls.emp, force=True)
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
		frappe.db.delete("Casual Labour Work", {"employee": self.emp})
		frappe.clear_cache(user=self.asst)  # a test may have dropped the role in an uncommitted change
		for p in frappe.get_all("Production Work Plan", filters={"crop": self.crop.name}, pluck="name"):
			frappe.delete_doc("Production Work Plan", p, force=True)
		for c in frappe.get_all("Production Crop Cycle", filters={"unit": self.u1.name}, pluck="name"):
			frappe.delete_doc("Production Crop Cycle", c, force=True)
		frappe.db.commit()

	def add_task(self, user, unit=None):
		frappe.set_user(user)
		res = desk.save_plan_tasks(self.crop.name, self.farm.name, self.year, self.week,
			[{"unit": unit or self.u1.name, "operation": self.op.name, "planned_qty": 5, "due_date": self.start}])
		self.assertNotIn("error", res)
		frappe.set_user("Administrator")
		return frappe.get_all("Work Plan Task", filters={"parent": res["name"], "unit": unit or self.u1.name},
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

	# -- Task 2: awaiting tasks ---------------------------------------------------

	def _plan_with(self, user, step=True, unit=None):
		set_step(step)
		self.add_task(user, unit)
		frappe.set_user("Administrator")
		frappe.db.commit()
		return frappe.db.get_value("Production Work Plan",
			{"crop": self.crop.name, "plan_year": self.year, "plan_week": self.week})

	def _task(self, plan, unit=None):
		return frappe.get_all("Work Plan Task", filters={"parent": plan, "unit": unit or self.u1.name}, pluck="name")[0]

	def _get_plan_tasks(self, user):
		frappe.set_user(user)
		res = desk.get_plan(self.crop.name, self.farm.name, self.year, self.week)
		frappe.set_user("Administrator")
		return res["tasks"]

	def _mobile_tasks(self, user):
		from types import SimpleNamespace
		from unittest.mock import patch

		from upande_production.mobile import api as mobile
		frappe.set_user(user)
		frappe.response.pop("data", None)
		payload = {"crop": self.crop.name, "farm": self.farm.name, "year": self.year, "week": self.week}
		try:
			with patch.object(frappe.local, "request", SimpleNamespace(get_json=lambda: payload), create=True):
				mobile.productionGetWeekPlan()
		finally:
			frappe.set_user("Administrator")
		res = frappe.response["data"]
		self.assertNotIn("error", res)
		return res["tasks"]

	def test_supervisor_does_not_see_awaiting(self):
		self._plan_with(self.asst)
		self.assertEqual(self._get_plan_tasks(self.sup), [])
		self.assertEqual(self._mobile_tasks(self.sup), [])

	def test_manager_and_assistant_see_awaiting(self):
		self._plan_with(self.asst)
		for u in (self.mgr, self.asst):
			rows = self._get_plan_tasks(u)
			self.assertEqual(len(rows), 1, u)
			self.assertEqual(rows[0]["awaiting_approval"], 1)
			self.assertEqual(rows[0]["assigned_by"], self.asst)
		self.assertEqual(len(self._mobile_tasks(self.mgr)), 1)

	def test_record_work_on_awaiting_refused(self):
		plan = self._plan_with(self.asst)
		res = desk.record_task_work(plan, self._task(plan), "Skipped")
		self.assertIn("error", res)
		self.assertIn("This task is waiting for a manager's approval.", res["error"])

	def test_forward_all_and_one(self):
		set_step(True)
		frappe.set_user(self.asst)
		res = desk.save_plan_tasks(self.crop.name, self.farm.name, self.year, self.week, [
			{"unit": self.u1.name, "operation": self.op.name, "planned_qty": 5, "due_date": self.start},
			{"unit": self.u1.name, "operation": self.op.name, "planned_qty": 6, "due_date": self.start}])
		plan = res["name"]
		names = frappe.get_all("Work Plan Task", filters={"parent": plan}, pluck="name", order_by="idx asc")
		frappe.set_user(self.mgr)
		one = desk.forward_plan_tasks(plan, [names[0]])
		self.assertEqual(one["forwarded"], [names[0]])
		row = frappe.db.get_value("Work Plan Task", names[0], ["awaiting_approval", "forwarded_by", "forwarded_on"], as_dict=True)
		self.assertEqual((row.awaiting_approval, row.forwarded_by), (0, self.mgr))
		self.assertTrue(row.forwarded_on)
		self.assertEqual([t["name"] for t in self._get_plan_tasks(self.sup)], [names[0]])
		frappe.set_user(self.mgr)
		self.assertEqual(desk.forward_plan_tasks(plan)["forwarded"], [names[1]])
		self.assertEqual(len(self._get_plan_tasks(self.sup)), 2)

	def test_forward_refused_for_assistant_and_supervisor(self):
		plan = self._plan_with(self.asst)
		for u in (self.asst, self.sup):
			frappe.set_user(u)
			self.assertIn("error", desk.forward_plan_tasks(plan), u)
		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value("Work Plan Task", self._task(plan), "awaiting_approval"), 1)

	def _forwarded(self):
		plan = self._plan_with(self.asst)
		frappe.set_user(self.mgr)
		desk.forward_plan_tasks(plan)
		frappe.set_user("Administrator")
		return plan, self._task(plan)

	def _edit(self, user, name, **vals):
		frappe.set_user(user)
		res = desk.save_plan_tasks(self.crop.name, self.farm.name, self.year, self.week, [{"name": name, **vals}])
		frappe.set_user("Administrator")
		self.assertNotIn("error", res)
		return frappe.db.get_value("Work Plan Task", name, ["awaiting_approval", "forwarded_by", "forwarded_on"], as_dict=True)

	def test_assistant_edit_key_field_reawaits(self):
		plan, name = self._forwarded()
		row = self._edit(self.asst, name, note="just a note")
		self.assertEqual(row.awaiting_approval, 0)
		row = self._edit(self.asst, name, planned_qty=9)
		self.assertEqual(row.awaiting_approval, 1)
		self.assertFalse(row.forwarded_by)
		self.assertFalse(row.forwarded_on)

	def test_same_qty_as_string_does_not_reawait(self):
		plan, name = self._forwarded()
		self.assertEqual(self._edit(self.asst, name, planned_qty="5", rate="40.0").awaiting_approval, 0)

	def test_manager_edit_does_not_reawait(self):
		plan, name = self._forwarded()
		self.assertEqual(self._edit(self.mgr, name, planned_qty=9).awaiting_approval, 0)

	def test_clients_cannot_set_approval_fields(self):
		plan = self._plan_with(self.mgr)
		name = self._task(plan)
		row = self._edit(self.mgr, name, awaiting_approval=1, forwarded_by=self.sup)
		self.assertEqual(row.awaiting_approval, 0)
		self.assertFalse(row.forwarded_by)

	def test_step_off_ignores_awaiting(self):
		plan = self._plan_with(self.asst, step=False)
		frappe.db.set_value("Work Plan Task", self._task(plan), "awaiting_approval", 1)
		frappe.db.commit()
		self.assertEqual(len(self._get_plan_tasks(self.sup)), 1)
		res = desk.record_task_work(plan, self._task(plan), "Skipped")
		self.assertNotIn("error", res)

	def test_manager_can_delete_awaiting(self):
		plan = self._plan_with(self.asst)
		frappe.set_user(self.mgr)
		res = desk.delete_plan_task(plan, self._task(plan), "not needed")
		frappe.set_user("Administrator")
		self.assertNotIn("error", res)
		self.assertEqual(frappe.get_all("Work Plan Task", filters={"parent": plan}), [])

	# -- Task 3: two-step work approval --------------------------------------------

	def _worked(self, assigner, step=True, qty=4, unit=None):
		"""A forwarded task assigned by `assigner` with one supervisor-keyed entry; (plan, task, entry)."""
		plan = self._plan_with(assigner, step=step, unit=unit)
		task_approval.forward(plan)
		frappe.db.commit()
		task = self._task(plan, unit)
		frappe.set_user(self.sup)
		res = work.record_task_work(plan, task, "In Progress", [{"employee": self.emp, "qty": qty}])
		frappe.set_user("Administrator")
		return plan, task, res["work"][0]

	def _t(self, task):
		return frappe.db.get_value("Work Plan Task", task, ["done_qty", "pending_qty", "status"], as_dict=True)

	def _as(self, user, fn, *a, **kw):
		frappe.set_user(user)
		try:
			return fn(*a, **kw)
		finally:
			frappe.set_user("Administrator")

	def _status(self, name):
		return frappe.db.get_value("Casual Labour Work", name, ["docstatus", "approval_status", "checked_by"], as_dict=True)

	def test_work_on_assistant_task_needs_check(self):
		_, _, e = self._worked(self.asst)
		self.assertTrue(approvals.needs_check(frappe.get_doc("Casual Labour Work", e)))
		set_step(False)
		self.assertFalse(approvals.needs_check(frappe.get_doc("Casual Labour Work", e)))

	def test_manager_task_work_single_step(self):
		_, _, e = self._worked(self.mgr)
		self.assertFalse(approvals.needs_check(frappe.get_doc("Casual Labour Work", e)))
		self.assertEqual(self._as(self.mgr, approvals.approve, [e]), {"approved": [e]})

	def test_only_assigner_checks(self):
		_, _, e = self._worked(self.asst)
		other = _user("ach.asst2@x.test", settings.ASSISTANT_ROLE)
		for u in (other, self.sup, self.mgr):
			with self.assertRaises(frappe.PermissionError, msg=u):
				self._as(u, approvals.check, [e])
		self.assertEqual(self._status(e).approval_status, "Pending")
		res = self._as(self.asst, approvals.check, [e])
		self.assertEqual(res, {"checked": [e]})
		s = self._status(e)
		self.assertEqual((s.approval_status, s.checked_by, s.docstatus), ("Checked", self.asst, 0))
		self.assertTrue(frappe.db.get_value("Casual Labour Work", e, "checked_at"))
		with self.assertRaises(frappe.ValidationError):  # already Checked
			self._as(self.asst, approvals.check, [e])

	def test_manager_cannot_approve_unchecked_without_flag(self):
		_, _, e = self._worked(self.asst)
		with self.assertRaises(frappe.ValidationError):
			self._as(self.mgr, approvals.approve, [e])
		self.assertEqual(self._status(e).docstatus, 0)

	def test_unchecked_ok_flag(self):
		_, _, e = self._worked(self.asst)
		self.assertEqual(self._as(self.mgr, approvals.approve, [e], 1), {"approved": [e]})
		s = self._status(e)
		self.assertEqual((s.docstatus, s.approval_status, s.checked_by), (1, "Approved", None))

	def test_manager_approves_checked(self):
		plan, task, e = self._worked(self.asst, qty=4)
		self._as(self.asst, approvals.check, [e])
		self._as(self.mgr, approvals.approve, [e])
		s = self._status(e)
		self.assertEqual((s.docstatus, s.approval_status, s.checked_by), (1, "Approved", self.asst))
		t = self._t(task)
		self.assertEqual((t.done_qty, t.pending_qty), (4, 0))

	def test_checked_counts_as_pending(self):
		plan, task, e = self._worked(self.asst, qty=4)
		self._as(self.asst, approvals.check, [e])
		t = self._t(task)
		self.assertEqual((t.done_qty, t.pending_qty), (0, 4))

	def test_manager_approves_unchecked_when_assistant_gone(self):
		_, _, e = self._worked(self.asst)
		u = frappe.get_doc("User", self.asst)
		u.remove_roles(settings.ASSISTANT_ROLE)
		frappe.clear_cache(user=self.asst)
		self.assertFalse(approvals.needs_check(frappe.get_doc("Casual Labour Work", e)))
		self.assertEqual(self._as(self.mgr, approvals.approve, [e]), {"approved": [e]})

	def test_step_off_checked_approvable(self):
		_, _, e = self._worked(self.asst)
		self._as(self.asst, approvals.check, [e])
		set_step(False)
		self.assertEqual(self._as(self.mgr, approvals.approve, [e]), {"approved": [e]})

	def test_send_back_from_checked_and_resubmit_clears_check(self):
		_, task, e = self._worked(self.asst)
		self._as(self.asst, approvals.check, [e])
		with self.assertRaises(frappe.ValidationError):  # assistant: Pending only
			self._as(self.asst, approvals.send_back, [e], "no")
		self._as(self.mgr, approvals.send_back, [e], "recount")
		self.assertEqual(self._status(e).approval_status, "Sent Back")
		self.assertEqual(self._t(task).pending_qty, 0)
		self._as(self.sup, approvals.resubmit, [e])
		doc = frappe.get_doc("Casual Labour Work", e)
		self.assertEqual((doc.approval_status, doc.checked_by, doc.checked_at), ("Pending", None, None))

	def test_assistant_sends_back_own_pending_only(self):
		_, _, e = self._worked(self.asst)
		_, _, e2 = self._worked(self.mgr, unit=self.u2.name)
		with self.assertRaises(frappe.PermissionError):  # not their task
			self._as(self.asst, approvals.send_back, [e2], "no")
		self.assertEqual(self._as(self.asst, approvals.send_back, [e], "redo"), {"sent_back": [e]})

	def _mine(self):
		return sum(c["pending"] for c in approvals.approval_counts()["crops"] if c["crop"] == self.crop.name)

	def test_queues_and_counts(self):
		_, _, e1 = self._worked(self.asst)
		_, _, e2 = self._worked(self.mgr, unit=self.u2.name)
		frappe.set_user(self.asst)
		q = approvals.list_approvals(queue="check")
		self.assertEqual([n for g in q["groups"] for n in g["names"]], [e1])
		self.assertEqual(approvals.approval_counts()["to_check"], 1)
		frappe.set_user(self.mgr)
		self.assertEqual(approvals.approval_counts()["to_check"], 0)
		self.assertEqual(self._mine(), 1)  # e2 only; e1 waits for the check
		q = approvals.list_approvals(queue="approve")
		flags = {n: g["needs_check"] for g in q["groups"] for n in g["names"] if n in (e1, e2)}
		self.assertEqual(flags, {e1: True, e2: False})
		frappe.set_user("Administrator")
		self._as(self.asst, approvals.check, [e1])
		frappe.set_user(self.mgr)
		self.assertEqual(self._mine(), 2)
		g = [g for g in approvals.list_approvals(queue="approve")["groups"] if e1 in g["names"]][0]
		self.assertEqual((g["status"], g["checked_by"], g["needs_check"]), ("Checked", self.asst, False))
		self.assertEqual(approvals.list_approvals(status="Checked")["counts"]["Checked"], 1)
		frappe.set_user("Administrator")

	def test_protocol_compliance_only_after_approve(self):
		# compliance reads the protocol task's done_qty / status; Checked must not move them
		_, task, e = self._worked(self.asst, qty=5)
		self._as(self.asst, approvals.check, [e])
		self.assertEqual(self._t(task).done_qty, 0)
		self._as(self.mgr, approvals.approve, [e])
		self.assertEqual(self._t(task).done_qty, 5)
