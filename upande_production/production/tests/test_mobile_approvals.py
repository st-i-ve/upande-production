from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import today

from upande_production.api import production as desk
from upande_production.mobile import access, api, approvals as mobile
from upande_production.production.logic import settings, task_approval, work
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


class TestMobileApprovals(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		use_builtin_labour(cls)
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make("Farm", farm_name="MAP Farm", company=cls.company, abbreviation="MAP",
			farm_type=[{"farm_type": "Has Blocks"}])
		cls.crop = _make("Production Crop", crop_name="MAP Crop", crop_key="map-crop", unit_label="Block", yield_uom="Kg")
		cls.op = _make("Field Operation", crop=cls.crop.name, operation_name="MAP Weeding",
			category="Other", work_uom="Kg", default_rate=40)
		cls.u1 = _make("Production Unit", unit_name="MAP B1", crop=cls.crop.name, farm=cls.farm.name,
			unit_type="Orchard Block", company=cls.company, area_ha=1, plant_count=0)
		cls.mgr = _user("map.mgr@x.test", "Production Manager")
		cls.sup = _user("map.sup@x.test", "Production Supervisor")
		cls.asst = _user("map.asst@x.test", settings.ASSISTANT_ROLE)
		cls.emp = _make("Employee", first_name="MAPEmp", gender="Male", date_of_birth="1990-01-01",
			date_of_joining="2020-01-01", company=cls.company).name
		cls.year, cls.week = iso_of(today())
		cls.start, cls.end = iso_week_bounds(cls.year, cls.week)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		set_step(False)
		cls._wipe()
		for dt, name in (("Production Unit", cls.u1.name), ("Field Operation", cls.op.name),
				("Production Crop", cls.crop.name), ("Farm", cls.farm.name)):
			frappe.delete_doc(dt, name, force=True)
		for u in (cls.mgr, cls.sup, cls.asst):
			frappe.delete_doc("User", u, force=True)
		frappe.delete_doc("Employee", cls.emp, force=True)
		frappe.db.commit()
		super().tearDownClass()

	@classmethod
	def _wipe(cls):
		frappe.db.delete("Casual Labour Work", {"employee": cls.emp})
		for p in frappe.get_all("Production Work Plan", filters={"crop": cls.crop.name}, pluck="name"):
			frappe.delete_doc("Production Work Plan", p, force=True)
		frappe.db.commit()

	def setUp(self):
		frappe.set_user("Administrator")
		set_step(True)
		self.addCleanup(self._clean)

	def _clean(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		set_step(False)
		self._wipe()

	# -- helpers -------------------------------------------------------------------

	def _call(self, user, fn, payload=None):
		frappe.set_user(user)
		frappe.response.pop("data", None)
		try:
			with patch.object(frappe.local, "request", SimpleNamespace(get_json=lambda: payload or {}), create=True):
				fn()
			return frappe.response["data"]
		finally:
			frappe.set_user("Administrator")

	def _plan(self, assigner):
		frappe.set_user(assigner)
		res = desk.save_plan_tasks(self.crop.name, self.farm.name, self.year, self.week,
			[{"unit": self.u1.name, "operation": self.op.name, "planned_qty": 5, "due_date": self.start}])
		frappe.set_user("Administrator")
		frappe.db.commit()
		return res["name"], frappe.get_all("Work Plan Task", filters={"parent": res["name"]}, pluck="name")[0]

	def _worked(self, assigner=None, qty=4):
		"""plan, task, entry: a forwarded task assigned by `assigner` with one supervisor-keyed entry."""
		assigner = assigner or self.asst
		plan, task = self._plan(assigner)
		task_approval.forward(plan)
		frappe.db.commit()
		frappe.set_user(self.sup)
		res = work.record_task_work(plan, task, "In Progress", [{"employee": self.emp, "qty": qty}])
		frappe.set_user("Administrator")
		frappe.db.commit()
		return plan, task, res["work"][0]

	def _state(self, e):
		return frappe.db.get_value("Casual Labour Work", e, ["docstatus", "approval_status"], as_dict=True)

	# -- tests ---------------------------------------------------------------------

	def test_capabilities_per_role(self):
		roles = {"asst": [settings.ASSISTANT_ROLE], "mgr": ["Production Manager"], "sup": ["Production Supervisor"]}
		def caps(k):
			with patch.multiple(frappe, get_roles=lambda user=None: roles[k]), patch.dict(
					frappe.local.session, {"user": self.asst if k == "asst" else f"{k}@x.test"}):
				return access.capabilities()
		a, m, s = caps("asst"), caps("mgr"), caps("sup")
		self.assertEqual((a["plan_view"], a["plan_manage"], a["plan_check"]), (True, True, True))
		self.assertEqual((a["plan_tick_off"], a["plan_approve"], a["any"]), (False, False, True))
		self.assertTrue(m["plan_approve"])
		self.assertFalse(s["plan_approve"] or s["plan_check"])

	def test_supervisor_does_not_see_awaiting(self):
		self._plan(self.asst)
		payload = {"crop": self.crop.name, "farm": self.farm.name, "year": self.year, "week": self.week}
		self.assertEqual(self._call(self.sup, api.productionGetWeekPlan, payload)["tasks"], [])
		det = self._call(self.sup, api.productionGetPlanDetail, payload)
		self.assertEqual([t for b in det["blocks"] for t in b["tasks"]], [])

	def test_assistant_add_task_awaits(self):
		res = self._call(self.asst, api.productionAddTask, {
			"crop": self.crop.name, "farm": self.farm.name, "unit": self.u1.name, "operation": self.op.name,
			"planned_qty": 3, "year": self.year, "week": self.week})
		self.assertNotIn("error", res)
		row = frappe.get_all("Work Plan Task", filters={"unit": self.u1.name, "operation": self.op.name,
			"parenttype": "Production Work Plan"}, fields=["awaiting_approval", "assigned_by"])[0]
		self.assertEqual((row.awaiting_approval, row.assigned_by), (1, self.asst))

	def test_forward_tasks_accepts_json_string_and_rejects_other_types(self):
		plan, task = self._plan(self.asst)
		for bad in (5, {"a": 1}, "not json", '{"a": 1}', [1]):
			self.assertIn("error", self._call(self.mgr, mobile.productionForwardTasks, {"plan": plan, "tasks": bad}), bad)
		self.assertEqual(frappe.db.get_value("Work Plan Task", task, "awaiting_approval"), 1)
		res = self._call(self.mgr, mobile.productionForwardTasks, {"plan": plan, "tasks": f'["{task}"]'})
		self.assertEqual(res["forwarded"], [task])

	def test_counts_refused_for_supervisor(self):
		self.assertIn("error", self._call(self.sup, mobile.productionApprovalCounts))

	def test_phone_tasks_carry_awaiting(self):
		plan, task = self._plan(self.asst)
		payload = {"crop": self.crop.name, "farm": self.farm.name, "year": self.year, "week": self.week}
		res = self._call(self.mgr, api.productionGetWeekPlan, payload)
		self.assertEqual(res["tasks"][0]["awaiting_approval"], 1)
		det = self._call(self.asst, api.productionGetPlanDetail, payload)
		self.assertEqual(det["blocks"][0]["tasks"][0]["awaiting_approval"], 1)

	def test_phone_check_then_approve(self):
		_, _, e = self._worked()
		self.assertEqual(self._state(e).approval_status, "Pending")
		res = self._call(self.asst, mobile.productionCheckWork, {"names": [e]})
		self.assertEqual(res["status"], "success")
		self.assertEqual(res["checked"], [e])
		self.assertEqual(self._state(e).approval_status, "Checked")
		res = self._call(self.mgr, mobile.productionApproveWork, {"names": [e]})
		self.assertEqual((res["status"], res["approved"]), ("success", [e]))
		s = self._state(e)
		self.assertEqual((s.docstatus, s.approval_status), (1, "Approved"))

	def test_check_and_approve_guards(self):
		_, _, e = self._worked()
		for user, fn in ((self.sup, mobile.productionCheckWork), (self.mgr, mobile.productionCheckWork),
				(self.asst, mobile.productionApproveWork), (self.sup, mobile.productionApproveWork)):
			res = self._call(user, fn, {"names": [e]})
			self.assertIn("error", res, (user, fn.__name__))
		self.assertEqual(self._state(e).approval_status, "Pending")

	def test_phone_unchecked_approve_needs_flag(self):
		_, _, e = self._worked()
		res = self._call(self.mgr, mobile.productionApproveWork, {"names": [e]})
		self.assertIn("error", res)
		self.assertEqual(self._state(e).docstatus, 0)
		res = self._call(self.mgr, mobile.productionApproveWork, {"names": [e], "unchecked_ok": 1})
		self.assertEqual(res["status"], "success")
		self.assertEqual(self._state(e).docstatus, 1)

	def test_phone_send_back_needs_note(self):
		_, _, e = self._worked()
		res = self._call(self.asst, mobile.productionSendBackWork, {"names": [e]})
		self.assertIn("error", res)
		res = self._call(self.asst, mobile.productionSendBackWork, {"names": [e], "note": "  "})
		self.assertIn("error", res)
		self.assertEqual(self._state(e).approval_status, "Pending")
		res = self._call(self.asst, mobile.productionSendBackWork, {"names": [e], "note": "wrong block"})
		self.assertEqual((res["status"], res["sent_back"]), ("success", [e]))
		self.assertEqual(self._state(e).approval_status, "Sent Back")
		res = self._call(self.sup, mobile.productionSendBackWork, {"names": [e], "note": "x"})
		self.assertIn("error", res)

	def test_phone_forward_manager_only(self):
		plan, task = self._plan(self.asst)
		for u in (self.asst, self.sup):
			self.assertIn("error", self._call(u, mobile.productionForwardTasks, {"plan": plan}))
		self.assertEqual(frappe.db.get_value("Work Plan Task", task, "awaiting_approval"), 1)
		res = self._call(self.mgr, mobile.productionForwardTasks, {"plan": plan, "tasks": [task]})
		self.assertEqual((res["status"], res["forwarded"]), ("success", [task]))
		self.assertEqual(frappe.db.get_value("Work Plan Task", task, "awaiting_approval"), 0)
		self.assertIn("error", self._call(self.mgr, mobile.productionForwardTasks, {}))

	def test_phone_lists_by_queue(self):
		_, _, e = self._worked()
		chk = self._call(self.asst, mobile.productionListApprovals, {"crop": self.crop.name, "queue": "check"})
		self.assertEqual(chk["status"], "success")
		self.assertEqual([n for g in chk["groups"] for n in g["names"]], [e])
		self.assertEqual(chk["counts"]["queue"], 1)
		self.assertIn("error", self._call(self.mgr, mobile.productionListApprovals, {"queue": "check"}))
		self.assertIn("error", self._call(self.asst, mobile.productionListApprovals, {"queue": "approve"}))
		self.assertIn("error", self._call(self.mgr, mobile.productionListApprovals, {"queue": "bogus"}))
		apr = self._call(self.mgr, mobile.productionListApprovals, {"crop": self.crop.name, "queue": "approve"})
		self.assertEqual(apr["status"], "success")

	def test_phone_lists_strip_pay(self):
		_, _, e = self._worked()
		self._call(self.asst, mobile.productionCheckWork, {"names": [e]})
		args = {"crop": self.crop.name, "queue": "approve"}
		g = self._call(self.mgr, mobile.productionListApprovals, args)["groups"][0]
		self.assertEqual(g["entries"][0]["rate"], 40)
		self.assertEqual(g["total_pay"], 160)
		with patch.object(api, "can_see_pay", lambda: False):
			g = self._call(self.mgr, mobile.productionListApprovals, args)["groups"][0]
		self.assertIsNone(g["total_pay"])
		self.assertIsNone(g["entries"][0]["rate"])
		self.assertIsNone(g["entries"][0]["pay_value"])

	def test_phone_counts(self):
		before = self._call(self.mgr, mobile.productionApprovalCounts)  # the site may hold other pending work
		_, _, e = self._worked()
		a = self._call(self.asst, mobile.productionApprovalCounts)
		self.assertEqual((a["status"], a["to_check"], a["to_approve"]), ("success", 1, before["to_approve"]))
		self._call(self.asst, mobile.productionCheckWork, {"names": [e]})
		m = self._call(self.mgr, mobile.productionApprovalCounts)
		self.assertEqual((m["to_check"], m["to_approve"]), (0, before["to_approve"] + 1))
