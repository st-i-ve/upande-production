import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from upande_production.api import approvals as api
from upande_production.production.logic import approvals, plans, work
from upande_production.production.logic.weeks import iso_of


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


def _user(email, role):
	if not frappe.db.exists("User", email):
		_make("User", email=email, first_name=role.split()[-1], send_welcome_email=0, roles=[{"role": role}])
	return email


class TestApprovals(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make(
			"Farm", farm_name="TA Farm", company=cls.company, abbreviation="TAF",
			farm_type=[{"farm_type": "Has Blocks"}],
		)
		cls.crop = _make("Production Crop", crop_name="TA Crop", crop_key="ta-crop", unit_label="Block", yield_uom="Kg")
		cls.op = _make(
			"Production Operation", crop=cls.crop.name, operation_name="TA Weeding",
			category="Field Care", work_uom="Kg", default_rate=40,
		)
		cls.emps = [
			_make("Employee", first_name=f"TA{i}", gender="Male", date_of_birth="1990-01-01",
				date_of_joining="2020-01-01", company=cls.company)
			for i in range(2)
		]
		cls.sup = _user("ta_supervisor@example.com", "Production Supervisor")
		cls.mgr = _user("ta_manager@example.com", "Production Manager")
		cls.viewer = _user("ta_viewer@example.com", "Production Viewer")

	def tearDown(self):
		frappe.set_user("Administrator")

	def _task(self):
		unit = _make(
			"Production Unit", unit_name=frappe.generate_hash(length=6), crop=self.crop.name,
			farm=self.farm.name, unit_type="Orchard Block", company=self.company,
		)
		y, w = iso_of(today())
		plan = plans.get_or_create_plan(self.crop.name, self.farm.name, y, w)
		plan.append("tasks", {
			"unit": unit.name, "operation": self.op.name, "planned_qty": 10, "uom": "Kg", "rate": 40,
			"due_date": today(), "status": "Open",
		})
		plan.save()
		return plan, plan.tasks[-1]

	def _key(self, plan, task, qtys=(6, 4), as_user=None):
		if as_user:
			frappe.set_user(as_user)
		res = work.record_task_work(
			plan.name, task.name, "In Progress",
			[{"employee": self.emps[i].name, "qty": q} for i, q in enumerate(qtys)],
		)
		frappe.set_user("Administrator")
		return res["work"]

	def _row(self, plan):
		plan.reload()
		return plan.tasks[-1]

	def test_draft_does_not_count(self):
		plan, task = self._task()
		names = self._key(plan, task, as_user=self.sup)
		for n in names:
			d = frappe.get_doc("Value Adder Work", n)
			self.assertEqual((d.docstatus, d.approval_status, d.submitted_by), (0, "Pending", self.sup))
		row = self._row(plan)
		self.assertEqual((row.done_qty, row.pending_qty), (0, 10))

	def test_done_needs_crew(self):
		plan, task = self._task()
		with self.assertRaises(frappe.ValidationError):
			work.record_task_work(plan.name, task.name, "Done", [])
		# once somebody is recorded, closing the task later needs no new entries
		self._key(plan, task)
		res = work.record_task_work(plan.name, task.name, "Done", [])
		self.assertEqual(res["task"]["status"], "Done")
		# In Progress and Skipped never need a crew
		self.assertEqual(work.record_task_work(plan.name, task.name, "Skipped", [])["task"]["status"], "Skipped")

	def test_approve_counts(self):
		plan, task = self._task()
		names = self._key(plan, task)
		frappe.set_user(self.mgr)
		self.assertEqual(api.approve(names)["approved"], names)
		frappe.set_user("Administrator")
		row = self._row(plan)
		self.assertEqual((row.done_qty, row.pending_qty), (10, 0))
		d = frappe.get_doc("Value Adder Work", names[0])
		self.assertEqual((d.docstatus, d.approval_status, d.reviewed_by), (1, "Approved", self.mgr))
		self.assertTrue(d.reviewed_at)
		with self.assertRaises(frappe.ValidationError):  # cannot approve twice
			approvals.approve(names)

	def test_send_back_requires_note(self):
		plan, task = self._task()
		names = self._key(plan, task)
		for note in ("", "   ", None):
			with self.assertRaises(frappe.ValidationError):
				approvals.send_back(names, note)
		self.assertEqual(frappe.db.get_value("Value Adder Work", names[0], "approval_status"), "Pending")
		self.assertEqual(api.send_back(names, "Wrong block")["sent_back"], names)
		d = frappe.get_doc("Value Adder Work", names[0])
		self.assertEqual((d.docstatus, d.approval_status, d.review_note), (0, "Sent Back", "Wrong block"))
		row = self._row(plan)
		self.assertEqual((row.done_qty, row.pending_qty), (0, 0))

	def test_resubmit_goes_back_to_pending(self):
		plan, task = self._task()
		names = self._key(plan, task)
		# only Sent Back may be resubmitted
		with self.assertRaises(frappe.ValidationError):
			approvals.resubmit(names)
		api.send_back(names, "Fix qty")
		frappe.set_user(self.sup)
		res = api.resubmit(names, [{"name": names[0], "qty": 5, "hours": 3}])
		self.assertEqual(res["resubmitted"], names)
		frappe.set_user("Administrator")
		d = frappe.get_doc("Value Adder Work", names[0])
		self.assertEqual((d.approval_status, d.qty, d.hours, d.docstatus), ("Pending", 5, 3, 0))
		self.assertEqual(self._row(plan).pending_qty, 9)

	def test_permissions(self):
		plan, task = self._task()
		names = self._key(plan, task)
		frappe.set_user(self.sup)
		self.assertIn("error", api.approve(names))
		self.assertIn("error", api.send_back(names, "no"))
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc("Value Adder Work", names[0]).submit()
		frappe.set_user(self.viewer)
		self.assertIn("error", api.resubmit(names))
		self.assertIn("error", api.approve(names))
		frappe.set_user(self.mgr)
		self.assertIn("approved", api.approve(names))

	def test_cancel_still_recounts(self):
		plan, task = self._task()
		names = self._key(plan, task)
		approvals.approve(names)
		self.assertEqual(self._row(plan).done_qty, 10)
		frappe.get_doc("Value Adder Work", names[0]).cancel()
		self.assertEqual(self._row(plan).done_qty, 4)

	def test_delete_draft_refreshes_pending(self):
		plan, task = self._task()
		names = self._key(plan, task)
		frappe.delete_doc("Value Adder Work", names[0])
		self.assertEqual(self._row(plan).pending_qty, 4)

	def test_list_groups_and_counts(self):
		plan, task = self._task()
		names = self._key(plan, task, as_user=self.sup)
		res = api.list_approvals(self.crop.name, unit=task.unit)
		self.assertEqual(res["counts"]["Pending"], 1)
		g = res["groups"][0]
		self.assertEqual(g["plan_task"], task.name)
		self.assertEqual(sorted(g["names"]), sorted(names))
		self.assertEqual((g["task_planned_qty"], g["task_pending_qty"], g["task_done_qty"]), (10, 10, 0))
		self.assertEqual(g["submitted_by"], self.sup)
		self.assertEqual(len(g["entries"]), 2)
		self.assertEqual(g["total_pay"], 400)
		self.assertFalse(g["stale"])
		self.assertEqual(api.list_approvals(self.crop.name, "Approved", unit=task.unit)["groups"], [])
		# stale once old enough
		frappe.db.sql("update `tabValue Adder Work` set creation = %s where name in %s",
			(add_days(today(), -4), names))
		res = api.list_approvals(self.crop.name, unit=task.unit)
		self.assertTrue(res["groups"][0]["stale"])
		self.assertEqual(res["counts"]["stale"], 1)
		counts = api.approval_counts()
		row = next(c for c in counts["crops"] if c["crop"] == self.crop.name)
		self.assertEqual(row["crop_key"], "ta-crop")
		self.assertGreaterEqual(row["pending"], 1)
		self.assertGreaterEqual(row["stale"], 1)

	def test_viewer_sees_no_pay_and_unplanned_group(self):
		unit = _make(
			"Production Unit", unit_name="TA Un", crop=self.crop.name, farm=self.farm.name,
			unit_type="Orchard Block", company=self.company,
		)
		work.record_unplanned_work(unit.name, self.op.name, [{"employee": e.name, "qty": 2} for e in self.emps], today())
		frappe.set_user(self.viewer)
		res = api.list_approvals(self.crop.name, unit=unit.name)
		self.assertEqual(len(res["groups"]), 1)
		g = res["groups"][0]
		self.assertEqual(g["unplanned"], 1)
		self.assertIsNone(g["total_pay"])
		self.assertTrue(all(e["pay_value"] is None and e["rate"] is None for e in g["entries"]))
