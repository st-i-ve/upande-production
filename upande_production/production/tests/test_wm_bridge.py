"""Production driving Work Management (Labour mode Automatic with WM installed).

The whole chain runs through WM's own screen actions: plan save raises the planner, WM approves it, a tick-off
puts the crew on an assignment and writes the actuals, WM's approval chain confirms (or returns) them and the
result comes back onto Casual Labour Work, and so does a paid run.

WM commits in places (adding crew), and a planner raised for a refused tick-off is committed on purpose, so the
fixtures are committed and removed in tearDownClass. The payment step needs HR payroll (salary structure, slip)
to happen for real; here a run is built the way WM's send leaves it and marked paid with WM's own stamping
helpers (what its Salary Slip handler calls), then synced back.
"""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, today

from upande_production.api import approvals as approvals_api
from upande_production.api import labourpay
from upande_production.production.logic import approvals, wm_bridge, work
from upande_production.production.logic.weeks import iso_of, iso_week_bounds
from upande_production.production.tests.labour_mode import current_labour_mode, restore_labour_mode, set_labour_mode

WM = "work_management" in frappe.get_installed_apps()
REASON = "test: no scanner on this farm"
APPROVE = {"Pending Farm Manager": "act_fm_approve", "Pending HR Head": "act_hr_approve", "Pending GM": "act_gm_approve"}


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc


def _drop(doctype, names):
	for n in names:
		if not frappe.db.exists(doctype, n):
			continue
		if frappe.db.get_value(doctype, n, "docstatus") == 1:
			frappe.db.set_value(doctype, n, "docstatus", 2, update_modified=False)
		frappe.delete_doc(doctype, n, force=True, ignore_permissions=True)


class TestWMBridge(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not WM:
			raise __import__("unittest").SkipTest("Work Management is not installed")
		frappe.set_user("Administrator")
		cls.addClassCleanup(restore_labour_mode, current_labour_mode())
		set_labour_mode("Automatic")
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		abbr = frappe.db.get_value("Company", cls.company, "abbr")
		for dt, name, extra in (("UOM", "Kg", {"uom_name": "Kg"}), ("Farm Type", "Has Blocks", {"name": "Has Blocks"}),
				("Employment Type", "Task Worker", {"employee_type_name": "Task Worker"})):
			if not frappe.db.exists(dt, name):
				_make(dt, **extra)
		tag = cls.tag = frappe.generate_hash(length=4).upper()
		cls.farm = _make("Farm", farm_name=f"WMB Farm {tag}", company=cls.company, abbreviation=f"W{tag}",
			farm_type=[{"farm_type": "Has Blocks"}])
		cls.project = _make("Project", project_name=f"WMB Project {tag}", company=cls.company)
		cls.wm_farm_row = _make("WM Farm", parent="Work Management Settings", parenttype="Work Management Settings",
			parentfield="farms", farm=cls.farm.name, project=cls.project.name, idx=999)
		frappe.clear_document_cache("Work Management Settings", "Work Management Settings")
		cls.wh = _make("Warehouse", warehouse_name=f"WMB Block {tag}", company=cls.company, custom_farm=cls.farm.name)
		cls.crop = _make("Production Section", crop_name=f"WMB Crop {tag}", crop_key=f"wmb-{tag.lower()}",
			unit_label="Block", yield_uom="Kg")
		cls.op = _make("Field Operation", crop=cls.crop.name, operation_name=f"WMB Weeding {tag}", category="Other",
			work_uom="Kg", default_rate=40, daily_target=10)
		cls.unit = _make("Production Unit", unit_name=f"WMB-{tag}", crop=cls.crop.name, farm=cls.farm.name,
			unit_type="Orchard Block", company=cls.company, warehouse=cls.wh.name)
		cls.wh2 = _make("Warehouse", warehouse_name=f"WMB Block2 {tag}", company=cls.company, custom_farm=cls.farm.name)
		cls.unit2 = _make("Production Unit", unit_name=f"WMB2-{tag}", crop=cls.crop.name, farm=cls.farm.name,
			unit_type="Orchard Block", company=cls.company, warehouse=cls.wh2.name)
		cls.bare_unit = _make("Production Unit", unit_name=f"WMB-NOWH-{tag}", crop=cls.crop.name, farm=cls.farm.name,
			unit_type="Orchard Block", company=cls.company)
		cls.emps = [_make("Employee", first_name=f"WMB{tag}{i}", gender="Male", date_of_birth="1990-01-01",
			date_of_joining="2020-01-01", company=cls.company, employment_type="Task Worker",
			custom_farm=cls.farm.name) for i in range(3)]
		# the activity, and the approved budget WM's planner draws on
		cls.task = wm_bridge.task_for(cls.op.name, cls.farm.name)
		cls.week = iso_of(today())
		start, end = iso_week_bounds(*cls.week)
		cls.mp = _make("Work Management Master Plan", farm=cls.farm.name, period_from=add_days(start, -7),
			period_to=add_days(end, 7), company=cls.company,
			activities=[{"task": cls.task, "work_qty": 1000, "rate": 40, "cost": 100000, "consultant_state": "OK"}])
		frappe.db.set_value("Work Management Master Plan", cls.mp.name, "workflow_state", "Approved")
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		emps = [e.name for e in cls.emps]
		plans = frappe.get_all("Production Work Plan", filters={"crop": cls.crop.name}, pluck="name")
		work_rows = frappe.get_all("Casual Labour Work", filters={"employee": ("in", emps)}, pluck="name")
		planners = frappe.get_all(wm_bridge.PLANNER, filters={"farm": cls.farm.name}, pluck="name")
		assigners = frappe.get_all(wm_bridge.ASSIGNER, filters={"planner_request": ("in", planners or [""])}, pluck="name")
		actuals = frappe.get_all(wm_bridge.ACTUALS, filters={"assignment": ("in", assigners or [""])}, pluck="name")
		payments = frappe.get_all(wm_bridge.PAYMENT, filters={"farm": cls.farm.name}, pluck="name")
		_drop("Casual Labour Work", work_rows)
		_drop("Production Work Plan", plans)
		for dt, names in ((wm_bridge.PAYMENT, payments), (wm_bridge.ACTUALS, actuals), (wm_bridge.ASSIGNER, assigners),
				(wm_bridge.PLANNER, planners), ("Work Management Master Plan", [cls.mp.name])):
			_drop(dt, names)
		_drop("Task", frappe.get_all("Task", filters={"project": cls.project.name}, pluck="name"))
		frappe.db.delete("WM Farm", {"name": cls.wm_farm_row.name})
		frappe.clear_document_cache("Work Management Settings", "Work Management Settings")
		for doc in (cls.unit, cls.unit2, cls.bare_unit, cls.op, cls.crop, *cls.emps, cls.wh, cls.wh2, cls.project, cls.farm):
			frappe.delete_doc(doc.doctype, doc.name, force=True, ignore_permissions=True)
		# the cost centres production made for the units and the crop
		for cc in frappe.get_all("Cost Center", filters={"cost_center_name": ("like", f"%{cls.tag}%")},
				pluck="name", order_by="lft desc"):
			frappe.delete_doc("Cost Center", cc, force=True, ignore_permissions=True)
		frappe.db.commit()
		super().tearDownClass()

	# -- helpers --------------------------------------------------------------------------------------------

	def _plan(self, qty, unit=None, week=None):
		year, wk = week or self.week
		plan = frappe.get_doc({"doctype": "Production Work Plan", "crop": self.crop.name, "farm": self.farm.name,
			"plan_year": year, "plan_week": wk, "tasks": [{"unit": (unit or self.unit).name,
				"operation": self.op.name, "planned_qty": qty, "uom": "Kg", "rate": 40, "due_date": today(),
				"status": "Open"}]})
		plan.insert()
		frappe.db.commit()
		return plan

	def _drop_plan(self, plan):
		rows = frappe.get_all("Casual Labour Work", filters={"plan": plan.name}, pluck="name")
		_drop("Casual Labour Work", rows)
		frappe.delete_doc("Production Work Plan", plan.name, force=True)

	def _approve_planner(self, name):
		out = wm_bridge.call("planner", "approve", name=name)
		self.assertFalse(out.get("error"), out)

	def _approve_actuals(self, name):
		for _i in range(4):
			state = frappe.db.get_value(wm_bridge.ACTUALS, name, "workflow_state")
			if state not in APPROVE:
				break
			out = wm_bridge.call("actuals", APPROVE[state], name=name, quality_score="1")
			self.assertFalse(out.get("error"), out)
		return frappe.db.get_value(wm_bridge.ACTUALS, name, "workflow_state")

	def _entries(self, n=2, qty=8):
		return [{"employee": e.name, "qty": qty} for e in self.emps[:n]]

	# -- the chain ------------------------------------------------------------------------------------------

	def test_plan_raises_planner_and_tick_off_runs_the_chain(self):
		plan = self._plan(16)
		row = plan.tasks[0]
		row.reload()
		self.assertTrue(row.wm_planner, row.rule_notes)
		p = frappe.get_doc(wm_bridge.PLANNER, row.wm_planner)
		start, end = iso_week_bounds(*self.week)
		self.assertEqual((p.farm, p.block_section, p.task, p.quantity), (self.farm.name, self.wh.name, self.task, 16))
		self.assertEqual((getdate(p.from_date), getdate(p.to_date)), (start, end))
		self.assertEqual((p.uom, p.daily_target, p.rate), ("Kg", 10, 40))
		self.assertEqual(p.master_plan, self.mp.name)
		self.assertEqual(p.workflow_state, "Pending Approval")
		self.assertEqual(p.people_per_day, 2)  # 16 at 10 a day, on its due day

		# a quantity change while WM still holds a request edits the same planner
		plan.reload()
		plan.tasks[0].planned_qty = 16.0
		plan.save()
		self.assertEqual(frappe.db.count(wm_bridge.PLANNER, {"farm": self.farm.name, "task": self.task,
			"from_date": start}), 1)

		# tick-off before WM approves the planner: refused, nothing recorded
		with self.assertRaisesRegex(wm_bridge.WMError, "Waiting for Work Management approval of planner"):
			work.record_task_work(plan.name, row.name, "In Progress", self._entries(), override_reason=REASON)
		self.assertFalse(frappe.db.exists("Casual Labour Work", {"plan": plan.name}))

		self._approve_planner(row.wm_planner)
		res = work.record_task_work(plan.name, row.name, "Done", self._entries(), override_reason=REASON)
		frappe.db.commit()
		self.assertEqual(len(res["work"]), 2)
		self.assertTrue(res["wm"]["actuals"])
		actuals = res["wm"]["actuals"]
		row = frappe.get_doc("Work Plan Task", row.name)
		self.assertTrue(row.wm_assigner)
		asg = frappe.get_doc(wm_bridge.ASSIGNER, row.wm_assigner)
		self.assertEqual(asg.planner_request, row.wm_planner)
		self.assertEqual({r.employee for r in asg.employees}, {e.name for e in self.emps[:2]})
		ac = frappe.get_doc(wm_bridge.ACTUALS, actuals)
		self.assertEqual(ac.assignment, asg.name)
		self.assertEqual(sorted((r.employee, str(r.work_date), r.actual_quantity) for r in ac.employees),
			sorted((e.name, str(getdate(today())), 8) for e in self.emps[:2]))
		self.assertEqual({r.amount for r in ac.employees}, {320})  # WM's own arithmetic: 8 x 40, task workers
		self.assertEqual(ac.workflow_state, "Pending Farm Manager")  # Done submits it into WM's chain
		for n in res["work"]:
			self.assertEqual(frappe.db.get_value("Casual Labour Work", n, ["wm_actuals", "docstatus", "approval_status"]),
				(actuals, 0, "Pending"))

		# production's own approval is not where this work is decided
		r = approvals_api.approve(res["work"])
		self.assertIn("Work Management", r["error"])
		r = approvals_api.send_back(res["work"], "nope")
		self.assertIn("Work Management", r["error"])

		# WM returns it -> Sent Back in production
		out = wm_bridge.call("actuals", "act_reject", name=actuals)
		self.assertFalse(out.get("error"), out)
		wm_bridge.reconcile([actuals])
		for n in res["work"]:
			status, note = frappe.db.get_value("Casual Labour Work", n, ["approval_status", "review_note"])
			self.assertEqual(status, "Sent Back")
			self.assertIn(actuals, note)

		# fixed and resubmitted in production -> back onto the same WM actuals and into its chain
		approvals.resubmit(res["work"], override_reason=REASON)
		self.assertEqual(frappe.db.get_value(wm_bridge.ACTUALS, actuals, "workflow_state"), "Pending Farm Manager")

		# WM's final approval -> the work is approved (submitted) in production
		self.assertEqual(self._approve_actuals(actuals), "CONFIRMED")
		wm_bridge.reconcile()
		for n in res["work"]:
			d = frappe.get_doc("Casual Labour Work", n)
			self.assertEqual((d.docstatus, d.approval_status), (1, "Approved"))
			self.assertEqual(d.pay_value, 320)
			self.assertEqual(d.paid, "Unpaid")
		self.assertEqual(frappe.db.get_value("Work Plan Task", row.name, "done_qty"), 16)

		# paid in WM -> paid in production
		pay = self._paid_run(actuals, res["work"])
		for n in res["work"]:
			self.assertEqual(frappe.db.get_value("Casual Labour Work", n, ["paid", "payroll_reference"]),
				("Paid", pay))
			self.assertTrue(frappe.db.get_value("Casual Labour Work", n, "paid_on"))

		# payroll withdraws the slip -> back to unpaid
		from work_management.api.payment import _revert_payment_to_unpaid

		_revert_payment_to_unpaid(pay)
		wm_bridge.defer(payments=[pay])  # what on_salary_slip queues for the slip's runs
		wm_bridge.flush()
		for n in res["work"]:
			self.assertEqual(frappe.db.get_value("Casual Labour Work", n, "paid"), "Unpaid")
		frappe.db.commit()

	def _paid_run(self, actuals, names):
		"""A run as WM's send leaves it (payment_ref on its rows), then paid the way on_salary_slip_submit pays."""
		from work_management.api.payment import _stamp_actuals_paid_for_payment

		rows = frappe.get_all("Work Actuals Employee", filters={"parent": actuals}, fields=["name", "employee", "amount"])
		pay = frappe.get_doc({"doctype": wm_bridge.PAYMENT, "run_title": "WMB test", "farm": self.farm.name,
			"company": self.company, "payroll_date": today(), "period_from": today(), "period_to": today(),
			"workflow_state": "Unpaid", "amount": sum(r.amount for r in rows),
			"lines": [{"actuals": actuals, "employee": r.employee, "amount": r.amount} for r in rows]})
		pay.flags.ignore_permissions = True
		pay.insert()
		for r in rows:
			frappe.db.set_value("Work Actuals Employee", r.name, "payment_ref", pay.name, update_modified=False)
		frappe.db.set_value(wm_bridge.PAYMENT, pay.name, {"workflow_state": "Paid", "accounts_approval_date": today()},
			update_modified=False)
		_stamp_actuals_paid_for_payment(pay.name)
		# the document event fires on the run, and the sync waits for the commit
		wm_bridge.on_wm_payment(pay)
		self.assertIn(wm_bridge.flush, frappe.db.before_commit._functions)
		frappe.db.commit()
		return pay.name

	def test_unplanned_work_raises_a_planner_and_waits(self):
		plan_rows_before = frappe.db.count(wm_bridge.PLANNER, {"farm": self.farm.name})
		e = [{"employee": self.emps[2].name, "qty": 5}]
		with self.assertRaisesRegex(wm_bridge.WMError, "waiting for approval"):
			work.record_unplanned_work(self.unit2.name, self.op.name, e, today(), override_reason=REASON)
		self.assertEqual(frappe.db.count(wm_bridge.PLANNER, {"farm": self.farm.name}), plan_rows_before + 1)
		self.assertFalse(frappe.db.exists("Casual Labour Work", {"employee": self.emps[2].name, "unplanned": 1}))

	def test_unit_without_warehouse_is_noted_not_failed(self):
		plan = self._plan(10, unit=self.bare_unit, week=iso_of(add_days(today(), 7)))
		try:
			row = frappe.get_doc("Work Plan Task", plan.tasks[0].name)
			self.assertFalse(row.wm_planner)
			self.assertIn("has no warehouse", row.rule_notes)
			with self.assertRaisesRegex(wm_bridge.WMError, "has no warehouse"):
				work.record_task_work(plan.name, row.name, "In Progress", self._entries(1), override_reason=REASON)
		finally:
			self._drop_plan(plan)
			frappe.db.commit()

	def test_builtin_pay_runs_refused(self):
		for fn, args in ((labourpay.new_pay_run, {}), (labourpay.approve_pay_run, {"name": "x"}),
				(labourpay.mark_pay_run_paid, {"name": "x"}), (labourpay.refresh_pay_run, {"name": "x"})):
			out = fn(**args)
			self.assertIn("Work Management", out.get("error") or "", fn.__name__)

	def test_status(self):
		st = labourpay.wm_bridge_status()
		self.assertTrue(st["wm_active"])
		self.assertIn({"farm": self.farm.name, "project": self.project.name}, st["farms_mapped"])
		self.assertIn(self.bare_unit.name, [u["unit"] for u in st["units_without_warehouse"]])
		self.assertNotIn(self.op.name, [o.name for o in st["operations_without_task"]])

	def test_request_watch_queues_a_sync(self):
		from types import SimpleNamespace

		frappe.flags.wm_bridge_queue = None
		saved_req, saved_form = getattr(frappe.local, "request", None), frappe.local.form_dict
		try:
			frappe.local.request = SimpleNamespace(method="POST", path="/api/method/wm_actuals")
			frappe.local.form_dict = frappe._dict(action="act_gm_approve", name="WMAC-X")
			wm_bridge.watch_request()
			self.assertTrue(frappe.flags.wm_bridge_queue["all"])
			self.assertIn("WMAC-X", frappe.flags.wm_bridge_queue["names"])
			frappe.flags.wm_bridge_queue = None
			frappe.local.form_dict = frappe._dict(action="act_pending")
			wm_bridge.watch_request()
			self.assertFalse(frappe.flags.wm_bridge_queue)
		finally:
			frappe.local.request, frappe.local.form_dict = saved_req, saved_form
			frappe.flags.wm_bridge_queue = None


class TestWMBridgeHarmless(IntegrationTestCase):
	def test_built_in_mode_leaves_wm_alone(self):
		prev = current_labour_mode()
		set_labour_mode("Built-in only")
		try:
			self.assertFalse(wm_bridge.active())
			doc = frappe._dict(flags=frappe._dict(), tasks=[], get_doc_before_save=lambda: None)
			wm_bridge.on_plan_update(doc)  # no-op, no WM call
		finally:
			set_labour_mode(prev)

	def test_hooks_need_no_wm_import(self):
		import ast
		import inspect

		tree = ast.parse(inspect.getsource(wm_bridge))
		top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
		self.assertFalse([n for n in top if "work_management" in ast.dump(n)])
		hooks = frappe.get_hooks("doc_events")
		for dt in ("Work Management Actuals", "Work Management Payment"):
			self.assertIn(dt, hooks)
