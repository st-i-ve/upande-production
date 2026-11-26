import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from upande_production.api import cycle_setup as api
from upande_production.production.logic import clear_block as cb, cycle_requests as cr, cycle_setup, plans, settings
from upande_production.production.logic.weeks import iso_of

CYCLE = "Production Crop Cycle"
CCR = "Production Cycle Change Request"
TASK = "Work Plan Task"


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


def _user(email, *roles):
	if not frappe.db.exists("User", email):
		_make("User", email=email, first_name=email.split("@")[0], send_welcome_email=0, roles=[{"role": r} for r in roles])
	return email


class TestClearBlock(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make("Farm", farm_name="CLB Farm", company=cls.company, abbreviation="CLB",
			farm_type=[{"farm_type": "Has Blocks"}])
		cls.crop = _make("Production Crop", crop_name="CLB Crop", crop_key="clb-crop", unit_label="Block", yield_uom="Kg", uses_crop_cycles=1)
		cls.op = _make("Field Operation", crop=cls.crop.name, operation_name="CLB Weeding", category="Other", work_uom="Kg", default_rate=40)
		cls.item = _make("Item", item_code="CLB Tomato", item_name="CLB Tomato", item_group="All Item Groups",
			stock_uom="Kg", is_stock_item=1).name
		cls.mgr = _user("clb.mgr@x.test", "Production Manager")
		cls.sup = _user("clb.sup@x.test", "Production Supervisor")
		cls.asst = _user("clb.asst@x.test", settings.ASSISTANT_ROLE)
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		cls._wipe()
		for dt, name in (("Field Operation", cls.op.name), ("Item", cls.item), ("Production Crop", cls.crop.name), ("Farm", cls.farm.name)):
			frappe.delete_doc(dt, name, force=True)
		for u in (cls.mgr, cls.sup, cls.asst):
			frappe.delete_doc("User", u, force=True)
		frappe.db.commit()
		super().tearDownClass()

	@classmethod
	def _wipe(cls):
		units = frappe.get_all("Production Unit", filters={"crop": cls.crop.name}, pluck="name")
		cycles = frappe.get_all(CYCLE, filters={"unit": ("in", units or [""])}, pluck="name")
		frappe.db.delete(CCR, {"cycle": ("in", cycles or [""])})
		frappe.db.delete(TASK, {"unit": ("in", units or [""])})
		for p in frappe.get_all("Production Work Plan", filters={"crop": cls.crop.name}, pluck="name"):
			frappe.delete_doc("Production Work Plan", p, force=True)
		for c in cycles:
			frappe.db.set_value(CYCLE, c, {"proposed_next_cycle": None, "previous_cycle": None}, update_modified=False)
		for c in cycles:
			frappe.delete_doc(CYCLE, c, force=True)
		for u in units:
			frappe.delete_doc("Production Unit", u, force=True)
		for v in frappe.get_all("Production Variety", filters={"crop": cls.crop.name}, pluck="name"):
			frappe.delete_doc("Production Variety", v, force=True)

	def setUp(self):
		frappe.set_user("Administrator")
		self.addCleanup(self._clean)
		self.unit = self._unit()
		self.start = add_days(today(), -30)
		self.cycle = self._cycle(start=self.start)
		self.plan = plans.get_or_create_plan(self.crop.name, self.farm.name, *iso_of(today())).name
		frappe.db.commit()

	def _clean(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		self._wipe()
		frappe.db.commit()

	def _unit(self):
		return _make("Production Unit", unit_name=f"CLB {frappe.generate_hash(length=6)}", crop=self.crop.name, farm=self.farm.name,
			unit_type="Orchard Block", company=self.company, area_ha=5, plant_count=0).name

	def _cycle(self, unit=None, start=None, status="Active", **kw):
		return _make(CYCLE, unit=unit or self.unit, crop=self.crop.name, item=self.item, start_date=start or self.start,
			status=status, **kw).name

	def _task(self, due, cycle=None, status="Open"):
		plan = frappe.get_doc("Production Work Plan", self.plan)
		row = plan.append("tasks", {"unit": self.unit, "cycle": cycle or self.cycle, "operation": self.op.name,
			"due_date": due, "status": status, "planned_qty": 1})
		plan.save()
		return row.name

	def val(self, name, field):
		return frappe.db.get_value(CYCLE, name, field)

	def as_user(self, user, fn, *a, **kw):
		frappe.set_user(user)
		try:
			return fn(*a, **kw)
		finally:
			frappe.set_user("Administrator")

	def clear(self, user=None, **kw):
		args = {"unit": self.unit, "on_date": today(), "reason": "Uprooted", **kw}
		return self.as_user(user or self.mgr, api.clear_block, **args)

	def test_manager_clears_running_cycle(self):
		res = self.clear(note="old trees")
		self.assertIn("cleared", res)
		self.assertEqual(self.val(self.cycle, "status"), "Closed")
		self.assertEqual(str(self.val(self.cycle, "closed_on")), today())
		self.assertEqual(self.val(self.cycle, "close_reason"), "Uprooted")
		self.assertEqual(self.val(self.cycle, "close_note"), "old trees")
		self.assertEqual(str(self.val(self.cycle, "actual_harvest_end")), today())

	def test_existing_harvest_end_kept(self):
		frappe.db.set_value(CYCLE, self.cycle, "actual_harvest_end", add_days(today(), -2))
		self.clear()
		self.assertEqual(str(self.val(self.cycle, "actual_harvest_end")), add_days(today(), -2))

	def test_no_successor_proposed(self):
		self.clear()
		self.assertFalse(self.val(self.cycle, "proposed_next_cycle"))
		self.assertEqual(frappe.db.count(CYCLE, {"unit": self.unit}), 1)

	def test_unit_fallow_and_cleared_on(self):
		self.clear(on_date=add_days(today(), -1))
		self.assertEqual(frappe.db.get_value("Production Unit", self.unit, "status"), "Fallow")
		self.assertEqual(str(frappe.db.get_value("Production Unit", self.unit, "cleared_on")), add_days(today(), -1))

	def test_planned_without_records_deleted(self):
		planned = self._cycle(start=add_days(today(), 20), status="Planned")
		res = self.clear()
		self.assertFalse(frappe.db.exists(CYCLE, planned))
		self.assertEqual(res["cleared"]["planned_deleted"], 1)

	def test_planned_with_records_closed(self):
		planned = self._cycle(start=add_days(today(), 20), status="Planned")
		self._task(add_days(today(), -40), cycle=planned, status="Done")
		res = self.clear(reason="Replanting")
		self.assertEqual(self.val(planned, "status"), "Closed")
		self.assertEqual(self.val(planned, "close_reason"), "Replanting")
		self.assertEqual(res["cleared"]["planned_closed"], 1)

	def test_open_tasks_from_date_skipped(self):
		later = self._task(add_days(today(), 3))
		same = self._task(today(), status="In Progress")
		earlier = self._task(add_days(today(), -3))
		done = self._task(add_days(today(), 5), status="Done")
		res = self.clear()
		for t in (later, same):
			self.assertEqual(frappe.db.get_value(TASK, t, "status"), "Skipped")
			self.assertIn(f"Block cleared {today()}: Uprooted", frappe.db.get_value(TASK, t, "note"))
		self.assertEqual(frappe.db.get_value(TASK, earlier, "status"), "Open")
		self.assertEqual(frappe.db.get_value(TASK, done, "status"), "Done")
		self.assertEqual(res["cleared"]["tasks_skipped"], 2)

	def test_pending_edit_request_rejected(self):
		req = self.as_user(self.sup, cr.request_edit, self.cycle, {"area_ha": 3}, "Re-measured")["request"]
		self.clear()
		r = frappe.get_doc(CCR, req)
		self.assertEqual((r.status, r.review_note), ("Rejected", "Block cleared"))

	def test_future_date_refused(self):
		res = self.clear(on_date=add_days(today(), 1))
		self.assertIn("future", res["error"].lower())
		self.assertEqual(self.val(self.cycle, "status"), "Active")

	def test_date_before_earliest_running_start_refused(self):
		res = self.clear(on_date=add_days(self.start, -1))
		self.assertIn("error", res)
		self.assertEqual(self.val(self.cycle, "status"), "Active")

	def test_other_needs_note(self):
		self.assertIn("note", self.clear(reason="Other")["error"].lower())
		self.assertNotIn("error", self.clear(reason="Other", note="Flood"))

	def test_bad_reason_refused(self):
		self.assertIn("error", self.clear(reason="Boredom"))

	def test_retired_unit_refused(self):
		frappe.db.set_value("Production Unit", self.unit, "status", "Retired")
		self.assertIn("retired", self.clear()["error"].lower())

	def test_nothing_to_clear(self):
		self.clear()
		self.assertIn("nothing to clear", self.clear()["error"].lower())

	def test_supervisor_and_assistant_make_request(self):
		res = self.clear(user=self.sup, note="x")
		self.assertTrue(res["pending"])
		self.assertEqual(self.val(self.cycle, "status"), "Active")
		r = frappe.get_doc(CCR, res["request"])
		self.assertEqual((r.action, r.status, r.requested_by), ("Clear block", "Pending", self.sup))
		self.assertEqual(frappe.parse_json(r.payload)["unit"], self.unit)
		self.assertEqual(frappe.parse_json(r.payload)["reason"], "Uprooted")

	def test_one_pending_per_block(self):
		self._cycle(start=self.start)
		self.clear(user=self.sup)
		res = self.clear(user=self.asst)
		self.assertIn("waiting for approval", res["error"])

	def test_request_validated_up_front(self):
		self.assertIn("future", self.clear(user=self.sup, on_date=add_days(today(), 2))["error"].lower())
		self.assertFalse(frappe.db.exists(CCR, {"cycle": self.cycle}))

	def test_approve_runs_clear(self):
		task = self._task(add_days(today(), 2))
		req = self.clear(user=self.sup)["request"]
		self.as_user(self.mgr, cr.approve, req)
		self.assertEqual(self.val(self.cycle, "status"), "Closed")
		self.assertEqual(frappe.db.get_value(TASK, task, "status"), "Skipped")
		self.assertEqual(frappe.db.get_value("Production Unit", self.unit, "status"), "Fallow")
		self.assertEqual(frappe.db.get_value(CCR, req, "status"), "Approved")

	def test_direct_clear_rejects_the_pending_clear_request(self):
		req = self.clear(user=self.sup)["request"]
		self.clear()  # manager clears directly; the request is rejected as part of it
		self.assertEqual(frappe.db.get_value(CCR, req, "status"), "Rejected")

	def test_preview_counts(self):
		self._cycle(start=add_days(today(), 20), status="Planned")
		kept = self._cycle(start=add_days(today(), 25), status="Planned")
		self._task(add_days(today(), -40), cycle=kept, status="Done")
		self._task(add_days(today(), 3))
		self._task(add_days(today(), -3))
		res = self.as_user(self.mgr, api.clear_block_preview, self.unit)
		self.assertEqual((res["running"], res["planned_deleted"], res["planned_closed"], res["tasks_skipped"]), (1, 1, 1, 1))
		self.assertEqual(self.val(self.cycle, "status"), "Active")  # preview writes nothing

	def test_new_cycle_on_fallow_unit_activates_it(self):
		self.clear()
		self.assertEqual(frappe.db.get_value("Production Unit", self.unit, "status"), "Fallow")
		cycle_setup.create_cycle({"unit": self.unit, "item": self.item, "existing": 1, "planting_date": today()})
		self.assertEqual(frappe.db.get_value("Production Unit", self.unit, "status"), "Active")

	def test_continuous_variety_cycle_ends(self):
		v = _make("Production Variety", variety_name="CLB Cont", crop=self.crop.name, item=self.item, is_flowering=1,
			harvest_pattern="Continuous", harvest_interval_weeks=1, harvest_window_weeks=8, flowering_pattern="Interval",
			flowering_interval_weeks=4, weeks_to_first_flowering=20, weeks_flowering_to_harvest=10,
			stages=[{"stage": n, "start_day": s, "length_days": ln, "is_harvest": h} for n, s, ln, h in
				(("Planting", 0, 140, 0), ("Flowering", 140, 70, 0), ("Harvest", 210, 60, 1))]).name
		u = self._unit()
		c = _make(CYCLE, unit=u, crop=self.crop.name, variety=v, start_date=add_days(today(), -100), status="Active").name
		cb.clear_block(u, today(), "Crop failed")
		self.assertEqual(self.val(c, "status"), "Closed")
		self.assertEqual(self.val(c, "close_reason"), "Crop failed")
		self.assertFalse(self.val(c, "proposed_next_cycle"))
		self.assertEqual(frappe.db.count(CYCLE, {"unit": u}), 1)
