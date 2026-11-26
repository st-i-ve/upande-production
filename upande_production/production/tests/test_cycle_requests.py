import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, today

from upande_production.api import cycle_setup as api
from upande_production.api import production as desk
from upande_production.production.logic import approvals, cycle_requests as cr, cycle_setup, plans, settings
from upande_production.production.logic.weeks import iso_of
from upande_production.production.tests.labour_mode import use_builtin_labour

CYCLE = "Production Crop Cycle"
CCR = "Production Cycle Change Request"
PENDING_MSG = "A change to this cycle is already waiting for approval."
GUARD_MSG = "Changes to a cycle's setup need a manager's approval; use Edit cycle to send a request."


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


def _user(email, *roles):
	if not frappe.db.exists("User", email):
		_make("User", email=email, first_name=email.split("@")[0], send_welcome_email=0,
			roles=[{"role": r} for r in roles])
	return email


class TestCycleRequests(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		use_builtin_labour(cls)
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make("Farm", farm_name="CCR Farm", company=cls.company, abbreviation="CCR",
			farm_type=[{"farm_type": "Has Blocks"}])
		cls.crop = _make("Production Crop", crop_name="CCR Crop", crop_key="ccr-crop", unit_label="Block", yield_uom="Kg", uses_crop_cycles=1)
		cls.op = _make("Field Operation", crop=cls.crop.name, operation_name="CCR Weeding",
			category="Other", work_uom="Kg", default_rate=40)
		cls.item = _make("Item", item_code="CCR Tomato", item_name="CCR Tomato", item_group="All Item Groups",
			stock_uom="Kg", is_stock_item=1).name
		cls.protocol = _make("Production Protocol", protocol_name="CCR Proto", crop=cls.crop.name,
			version_status="Active", key_activities=[{"operation": cls.op.name, "week": w, "planned_qty": 1} for w in (1, 2, 3)]).name
		cls.u1 = _make("Production Unit", unit_name="CCR B1", crop=cls.crop.name, farm=cls.farm.name,
			unit_type="Orchard Block", company=cls.company, area_ha=5, plant_count=0)
		cls.mgr = _user("ccr.mgr@x.test", "Production Manager")
		cls.sup = _user("ccr.sup@x.test", "Production Supervisor")
		cls.sup2 = _user("ccr.sup2@x.test", "Production Supervisor")
		cls.asst = _user("ccr.asst@x.test", settings.ASSISTANT_ROLE)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		cls._wipe()
		for dt, name in (("Production Unit", cls.u1.name), ("Production Protocol", cls.protocol),
				("Field Operation", cls.op.name), ("Item", cls.item), ("Production Crop", cls.crop.name),
				("Farm", cls.farm.name)):
			frappe.delete_doc(dt, name, force=True)
		for u in (cls.mgr, cls.sup, cls.sup2, cls.asst):
			frappe.delete_doc("User", u, force=True)
		frappe.db.commit()
		super().tearDownClass()

	@classmethod
	def _wipe(cls):
		frappe.db.delete(CCR, {"cycle": ("in", frappe.get_all(CYCLE, filters={"unit": cls.u1.name}, pluck="name") or [""])})
		for p in frappe.get_all("Production Work Plan", filters={"crop": cls.crop.name}, pluck="name"):
			frappe.delete_doc("Production Work Plan", p, force=True)
		for c in frappe.get_all(CYCLE, filters={"unit": cls.u1.name}, pluck="name"):
			frappe.delete_doc(CYCLE, c, force=True)

	def setUp(self):
		frappe.set_user("Administrator")
		self.addCleanup(self._clean)
		self.cycle = cycle_setup.create_cycle({"unit": self.u1.name, "item": self.item, "existing": 1,
			"planting_date": today(), "area_ha": 2, "protocol": self.protocol})["name"]
		frappe.db.commit()

	def _clean(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		self._wipe()
		frappe.db.commit()

	def val(self, field):
		return frappe.db.get_value(CYCLE, self.cycle, field)

	def as_user(self, user, fn, *a, **kw):
		frappe.set_user(user)
		try:
			return fn(*a, **kw)
		finally:
			frappe.set_user("Administrator")

	def request(self, user=None, **data):
		data = {"area_ha": 3, "reason": "Re-measured", **data}
		data = {k: v for k, v in data.items() if v is not None}
		return self.as_user(user or self.sup, cr.request_edit, self.cycle, data, data.pop("reason"))

	def test_manager_edits_directly(self):
		res = self.as_user(self.mgr, api.update_cycle, self.cycle, {"area_ha": 3})
		self.assertEqual(res["name"], self.cycle)
		self.assertEqual(self.val("area_ha"), 3)
		self.assertFalse(frappe.db.exists(CCR, {"cycle": self.cycle}))

	def test_supervisor_protected_edit_makes_request(self):
		res = self.as_user(self.sup, api.update_cycle, self.cycle, {"area_ha": "3", "notes": "n", "reason": "Re-measured"})
		self.assertEqual(res["pending"], True)
		self.assertEqual(self.val("area_ha"), 2)
		self.assertFalse(self.val("notes"))
		r = frappe.get_doc(CCR, res["request"])
		self.assertEqual((r.status, r.action, r.requested_by, r.reason), ("Pending", "Edit", self.sup, "Re-measured"))
		self.assertEqual(frappe.parse_json(r.changes), {"area_ha": {"old": 2, "new": 3}, "notes": {"old": None, "new": "n"}})
		self.assertEqual(frappe.parse_json(r.payload), {"area_ha": 3, "notes": "n"})

	def test_unchanged_values_are_not_a_diff(self):
		start = str(getdate(self.val("start_date")))
		d = cr.diff(frappe.get_doc(CYCLE, self.cycle), {"area_ha": "2.0", "start_date": start, "notes": "", "reason": "x"})
		self.assertEqual(d, {})

	def test_reason_required(self):
		res = self.as_user(self.sup, api.update_cycle, self.cycle, {"area_ha": 3})
		self.assertIn("reason", res["error"].lower())
		self.assertFalse(frappe.db.exists(CCR, {"cycle": self.cycle}))

	def test_notes_only_edit_applies_directly(self):
		res = self.as_user(self.sup, api.update_cycle, self.cycle, {"notes": "hello"})
		self.assertNotIn("pending", res)
		self.assertEqual(self.val("notes"), "hello")
		self.assertFalse(frappe.db.exists(CCR, {"cycle": self.cycle}))

	def test_one_pending_per_cycle(self):
		self.request()
		with self.assertRaises(frappe.ValidationError) as e:
			self.request(self.asst, area_ha=4)
		self.assertEqual(str(e.exception), PENDING_MSG)
		with self.assertRaises(frappe.ValidationError) as e:
			self.as_user(self.sup, cr.request_delete, self.cycle, "x")
		self.assertEqual(str(e.exception), PENDING_MSG)

	def test_approve_applies_payload(self):
		new_start = str(add_days(today(), 3))
		name = self.request(area_ha=4, plant_count=12, start_date=new_start, notes="n")["request"]
		res = self.as_user(self.mgr, cr.approve, name)
		self.assertEqual((self.val("area_ha"), self.val("plant_count"), self.val("notes")), (4, 12, "n"))
		self.assertEqual(str(self.val("start_date")), new_start)
		r = frappe.get_doc(CCR, name)
		self.assertEqual((r.status, r.reviewed_by, r.stale), ("Approved", self.mgr, 0))
		self.assertTrue(r.reviewed_at)
		self.assertIsNone(frappe.flags.cycle_change_request)
		self.assertTrue(res)

	def test_stale_needs_apply_anyway(self):
		name = self.request(area_ha=4)["request"]
		frappe.db.set_value(CYCLE, self.cycle, "area_ha", 9)
		with self.assertRaises(frappe.ValidationError) as e:
			self.as_user(self.mgr, cr.approve, name)
		self.assertIn("area_ha", str(e.exception))
		self.assertEqual(self.val("area_ha"), 9)
		self.as_user(self.mgr, cr.approve, name, 1)
		self.assertEqual(self.val("area_ha"), 4)
		self.assertEqual(frappe.db.get_value(CCR, name, "stale"), 1)

	def test_non_manager_cannot_review(self):
		name = self.request()["request"]
		for fn, args in ((cr.approve, (name,)), (cr.reject, (name, "no")), (cr.send_back, (name, "no"))):
			with self.assertRaises(frappe.PermissionError):
				self.as_user(self.sup, fn, *args)

	def test_send_back_resubmit_withdraw(self):
		name = self.request()["request"]
		self.as_user(self.mgr, cr.send_back, name, "Check the figure")
		r = frappe.get_doc(CCR, name)
		self.assertEqual((r.status, r.review_note, r.reviewed_by), ("Sent Back", "Check the figure", self.mgr))
		with self.assertRaises(frappe.PermissionError):
			self.as_user(self.sup2, cr.resubmit, name, {"area_ha": 5})
		self.as_user(self.sup, cr.resubmit, name, {"area_ha": 5}, "Measured twice")
		r.reload()
		self.assertEqual((r.status, r.reason), ("Pending", "Measured twice"))
		self.assertEqual(frappe.parse_json(r.payload), {"area_ha": 5})
		self.assertEqual(frappe.parse_json(r.changes), {"area_ha": {"old": 2, "new": 5}})
		self.as_user(self.mgr, cr.send_back, name, "again")
		self.as_user(self.sup, cr.withdraw, name)
		r.reload()
		self.assertEqual((r.status, r.review_note), ("Rejected", "Withdrawn"))
		self.assertEqual(self.val("area_ha"), 2)
		self.request()  # a withdrawn request frees the cycle

	def test_reject_needs_note(self):
		name = self.request()["request"]
		with self.assertRaises(frappe.ValidationError):
			self.as_user(self.mgr, cr.reject, name, " ")
		with self.assertRaises(frappe.ValidationError):
			self.as_user(self.mgr, cr.send_back, name, "")
		self.as_user(self.mgr, cr.reject, name, "No")
		self.assertEqual(frappe.db.get_value(CCR, name, "status"), "Rejected")
		self.assertEqual(self.val("area_ha"), 2)

	def test_delete_manager_direct(self):
		res = self.as_user(self.mgr, api.delete_cycle, self.cycle, "")
		self.assertEqual(res, {"deleted": self.cycle})
		self.assertFalse(frappe.db.exists(CYCLE, self.cycle))

	def test_delete_request_then_approve(self):
		res = self.as_user(self.sup, api.delete_cycle, self.cycle, "Planted wrong block")
		self.assertTrue(res["pending"])
		self.assertTrue(frappe.db.exists(CYCLE, self.cycle))
		r = frappe.get_doc(CCR, res["request"])
		self.assertEqual((r.action, r.status), ("Delete", "Pending"))
		self.as_user(self.mgr, cr.approve, res["request"])
		self.assertFalse(frappe.db.exists(CYCLE, self.cycle))
		self.assertEqual(frappe.db.get_value(CCR, res["request"], "status"), "Approved")

	def _record(self):
		plan = plans.get_or_create_plan(self.crop.name, self.farm.name, *iso_of(today()))
		frappe.db.commit()
		self.assertGreater(plans.generate_week_detail(plan.name)["created"], 0)
		self.assertTrue(frappe.db.exists("Work Plan Task", {"cycle": self.cycle}))
		frappe.db.commit()  # the API envelope rolls back on an error

	def test_delete_refused_when_recorded(self):
		self._record()
		for user in (self.mgr, self.sup):
			res = self.as_user(user, api.delete_cycle, self.cycle, "x")
			self.assertIn("error", res)
		self.assertTrue(frappe.db.exists(CYCLE, self.cycle))
		self.assertFalse(frappe.db.exists(CCR, {"cycle": self.cycle}))

	def test_approve_delete_refused_when_recorded(self):
		name = self.as_user(self.sup, cr.request_delete, self.cycle, "x")["request"]
		self._record()
		with self.assertRaises(frappe.ValidationError):
			self.as_user(self.mgr, cr.approve, name)
		self.assertTrue(frappe.db.exists(CYCLE, self.cycle))
		self.assertEqual(frappe.db.get_value(CCR, name, "status"), "Pending")

	def test_back_door_refused(self):
		frappe.set_user(self.sup)
		doc = frappe.get_doc(CYCLE, self.cycle)
		doc.plant_count = 7
		with self.assertRaises(frappe.PermissionError) as e:
			doc.save()
		self.assertEqual(str(e.exception), GUARD_MSG)
		frappe.set_user("Administrator")
		self.assertEqual(self.val("plant_count"), 0)
		res = self.as_user(self.sup, desk.save_cycle, {"name": self.cycle, "plant_count": 7})
		self.assertEqual(res["error"], GUARD_MSG)
		self.assertEqual(self.val("plant_count"), 0)
		# closing counts; moving to Harvesting does not
		frappe.set_user(self.sup)
		doc = frappe.get_doc(CYCLE, self.cycle)
		doc.status = "Closed"
		with self.assertRaises(frappe.PermissionError):
			doc.save()
		doc = frappe.get_doc(CYCLE, self.cycle)
		doc.status = "Harvesting"
		doc.save()

	def test_manager_form_save_allowed(self):
		frappe.set_user(self.mgr)
		doc = frappe.get_doc(CYCLE, self.cycle)
		doc.plant_count = 6
		doc.save()
		self.assertEqual(self.val("plant_count"), 6)

	def test_auto_fields_not_guarded_and_not_overwritten(self):
		# a supervisor's non-protected save, and a system save of actuals, are not blocked
		self.as_user(self.sup, api.update_cycle, self.cycle, {"notes": "n1"})
		name = self.request(area_ha=None, plant_count=40)["request"]
		frappe.db.set_value(CYCLE, self.cycle, "status", "Harvesting")  # an automatic move after the request
		frappe.set_user(self.sup)
		doc = frappe.get_doc(CYCLE, self.cycle)
		doc.actual_harvest_start = today()
		doc.save()
		frappe.set_user("Administrator")
		self.as_user(self.mgr, cr.approve, name)
		self.assertEqual((self.val("plant_count"), self.val("status")), (40, "Harvesting"))

	def test_requests_visible_to_owner_only(self):
		name = self.request()["request"]
		self.assertEqual([r["name"] for r in self.as_user(self.sup, cr.list_requests)], [name])
		self.assertEqual(self.as_user(self.sup2, cr.list_requests), [])
		self.assertEqual([r["name"] for r in self.as_user(self.mgr, cr.list_requests, "Pending")], [name])
		self.assertEqual(self.as_user(self.mgr, cr.list_requests, "Approved"), [])
		self.assertEqual(len(self.as_user(self.mgr, cr.list_requests, None, self.crop.name)), 1)
		res = self.as_user(self.sup, api.list_cycle_changes)
		self.assertEqual(len(res["rows"]), 1)

	def test_counts_include_cycle_changes(self):
		self.assertEqual(self.as_user(self.mgr, approvals.approval_counts)["cycle_changes"], 0)
		self.request()
		self.assertEqual(self.as_user(self.mgr, approvals.approval_counts)["cycle_changes"], 1)
		self.assertEqual(self.as_user(self.sup, approvals.approval_counts)["cycle_changes"], 0)

	def test_edit_info_and_list_cycles_show_pending(self):
		self.assertIsNone(self.as_user(self.sup, cycle_setup.edit_info, self.cycle)["pending_request"])
		name = self.request()["request"]
		p = self.as_user(self.sup, cycle_setup.edit_info, self.cycle)["pending_request"]
		self.assertEqual((p["name"], p["requested_by"], p["action"]), (name, self.sup, "Edit"))
		self.assertIn("area_ha", p["changes"])
		rows = self.as_user(self.sup, desk.list_cycles, self.crop.name)["cycles"]
		row = [r for r in rows if r["name"] == self.cycle][0]
		self.assertEqual(row["pending_request"]["name"], name)

	def test_approve_closing_request(self):
		name = self.as_user(self.asst, api.update_cycle, self.cycle, {"status": "Closed", "reason": "Season over"})["request"]
		self.assertNotEqual(self.val("status"), "Closed")
		self.as_user(self.mgr, cr.approve, name)
		self.assertEqual(self.val("status"), "Closed")

	def test_assistant_manager_raises_edit_and_delete_requests(self):
		res = self.as_user(self.asst, api.update_cycle, self.cycle, {"plant_count": 9, "reason": "Recount"})
		self.assertTrue(res["pending"])
		self.assertEqual(frappe.db.get_value(CCR, res["request"], "requested_by"), self.asst)
		self.assertEqual(self.val("plant_count"), 0)
		self.as_user(self.mgr, cr.reject, res["request"], "no")
		res = self.as_user(self.asst, api.delete_cycle, self.cycle, "Wrong block")
		self.assertTrue(res["pending"])
		self.assertEqual(frappe.db.get_value(CCR, res["request"], "action"), "Delete")

	def test_area_back_door_is_inert(self):
		frappe.set_user(self.sup)
		doc = frappe.get_doc(CYCLE, self.cycle)
		doc.area_ha = 9
		doc.save()  # not refused, but the block's area is fetched back on every save
		frappe.set_user("Administrator")
		self.assertNotEqual(self.val("area_ha"), 9)

	def test_request_written_only_through_logic(self):
		name = self.request()["request"]
		frappe.set_user(self.sup)
		doc = frappe.get_doc(CCR, name)
		doc.status, doc.reviewed_by = "Approved", self.sup
		with self.assertRaises(frappe.PermissionError):
			doc.save()
		with self.assertRaises(frappe.PermissionError):
			frappe.delete_doc(CCR, name)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc({"doctype": CCR, "cycle": self.cycle, "action": "Edit", "reason": "x", "status": "Approved",
				"requested_by": self.sup}).insert()
		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value(CCR, name, "status"), "Pending")
		self.assertIsNone(frappe.flags.get(cr.LOGIC_FLAG) or None)
		# the logic paths still work for the requester
		self.as_user(self.mgr, cr.send_back, name, "again")
		self.as_user(self.sup, cr.resubmit, name, {"area_ha": 6})
		self.as_user(self.sup, cr.withdraw, name)
		self.assertEqual(frappe.db.get_value(CCR, name, "status"), "Rejected")
		n2 = self.as_user(self.sup, api.update_cycle, self.cycle, {"area_ha": 8, "reason": "x"})["request"]
		self.as_user(self.mgr, cr.send_back, n2, "again")
		res = self.as_user(self.sup, api.resubmit_cycle_change, n2, {"area_ha": 7})
		self.assertTrue(res["pending"])
		self.assertEqual(self.as_user(self.sup, api.withdraw_cycle_change, n2)["status"], "Rejected")

	def test_approve_request_of_deleted_cycle_gate(self):
		name = self.request()["request"]
		frappe.db.set_value(CCR, name, "cycle", self.cycle)  # unchanged; the cycle is removed next
		frappe.delete_doc(CYCLE, self.cycle, force=True)
		res = self.as_user(self.mgr, api.reject_cycle_change, name, "gone")
		self.assertEqual(res["status"], "Rejected")
