import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, today

from upande_production.api import production as desk
from upande_production.production.logic import plans
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


class TestPlanTaskSchedule(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		use_builtin_labour(cls)
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make("Farm", farm_name="PTS Farm", company=cls.company, abbreviation="PTS",
			farm_type=[{"farm_type": "Has Blocks"}])
		cls.crop = _make("Production Section", crop_name="PTS Crop", crop_key="pts-crop", unit_label="Block", yield_uom="Kg")
		cls.op = _make("Field Operation", crop=cls.crop.name, operation_name="PTS Weeding",
			category="Other", work_uom="Kg", default_rate=40)
		cls.u1 = _make("Production Unit", unit_name="PTS B1", crop=cls.crop.name, farm=cls.farm.name,
			unit_type="Orchard Block", company=cls.company)
		cls.u2 = _make("Production Unit", unit_name="PTS B2", crop=cls.crop.name, farm=cls.farm.name,
			unit_type="Orchard Block", company=cls.company)
		cls.mgr = _user("pts.mgr@x.test", "Production Manager")
		cls.sup = _user("pts.sup@x.test", "Production Supervisor")
		cls.editor = _user("pts.editor@x.test", "Production Supervisor", "Production Plan Editor")
		cls.avo = _user("pts.avo@x.test", "Avocado Production Manager", "Production Plan Editor")
		cls.employee = _make("Employee", first_name="PTSEmp", gender="Male", date_of_birth="1990-01-01",
			date_of_joining="2020-01-01", company=cls.company)
		cls.year, cls.week = iso_of(today())
		cls.start, cls.end = iso_week_bounds(cls.year, cls.week)
		frappe.db.commit()  # the API envelope rolls back on an error; committed fixtures survive that

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		for p in frappe.get_all("Production Work Plan", filters={"crop": cls.crop.name}, pluck="name"):
			frappe.delete_doc("Production Work Plan", p, force=True)
		for dt, doc in (("Employee", cls.employee), ("Production Unit", cls.u2), ("Production Unit", cls.u1),
				("Field Operation", cls.op), ("Production Section", cls.crop), ("Farm", cls.farm)):
			frappe.delete_doc(dt, doc.name, force=True)
		for u in (cls.mgr, cls.sup, cls.editor, cls.avo):
			frappe.delete_doc("User", u, force=True)
		frappe.db.commit()
		super().tearDownClass()

	def setUp(self):
		frappe.set_user("Administrator")
		plan = plans.get_or_create_plan(self.crop.name, self.farm.name, self.year, self.week)
		plan.append("tasks", {"unit": self.u1.name, "operation": self.op.name, "planned_qty": 5, "uom": "Kg",
			"rate": 40, "due_date": self.start, "status": "Open"})
		plan.save()
		frappe.db.commit()
		self.plan = plan.name
		self.task = plan.tasks[0].name
		self.addCleanup(self._clean)

	def _clean(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		for n in frappe.get_all("Casual Labour Work", filters={"plan": self.plan}, pluck="name"):
			frappe.delete_doc("Casual Labour Work", n, force=True)
		frappe.delete_doc("Production Work Plan", self.plan, force=True)
		frappe.db.commit()

	def save(self, tasks, user):
		frappe.set_user(user)
		return desk.save_plan_tasks(self.crop.name, self.farm.name, self.year, self.week, tasks)

	def row(self):
		return frappe.db.get_value("Work Plan Task", self.task, ["due_date", "original_due_date"], as_dict=True)

	def test_bootstrap_flag(self):
		for user, expected in ((self.mgr, True), (self.sup, False), (self.editor, True)):
			frappe.set_user(user)
			self.assertEqual(desk.get_bootstrap()["can_reschedule"], expected, user)

	def test_supervisor_cannot_delete_via_save(self):
		res = self.save([{"name": self.task, "_delete": 1}], self.sup)
		self.assertIn("not permitted", res["error"])
		self.assertTrue(frappe.db.exists("Work Plan Task", self.task))

	def test_supervisor_cannot_redate_via_save(self):
		res = self.save([{"name": self.task, "due_date": add_days(self.start, 1)}], self.sup)
		self.assertIn("not permitted", res["error"])
		self.assertEqual(getdate(self.row().due_date), getdate(self.start))

	def test_editor_can_redate_via_save(self):
		res = self.save([{"name": self.task, "due_date": add_days(self.start, 1)}], self.editor)
		self.assertNotIn("error", res)
		row = self.row()
		self.assertEqual(getdate(row.due_date), getdate(add_days(self.start, 1)))
		self.assertEqual(getdate(row.original_due_date), getdate(self.start))

	def test_save_refuses_delete_with_work(self):
		_make("Casual Labour Work", work_date=today(), employee=self.employee.name, unit=self.u1.name,
			operation=self.op.name, qty=5, uom="Kg", plan=self.plan, plan_task=self.task)
		frappe.db.commit()
		res = self.save([{"name": self.task, "_delete": 1}], self.mgr)
		self.assertIn("error", res)
		self.assertIn("Skip", res["error"])
		self.assertTrue(frappe.db.exists("Work Plan Task", self.task))

	def test_adding_tasks_unchanged(self):
		res = self.save([{"unit": self.u2.name, "operation": self.op.name, "planned_qty": 3,
			"due_date": add_days(self.start, 2)}], self.sup)
		self.assertNotIn("error", res)
		self.assertEqual(frappe.db.count("Work Plan Task", {"parent": self.plan}), 2)

	# ---- move / postpone / delete endpoints ----

	def call(self, fn, user, **kw):
		frappe.set_user(user)
		return getattr(desk, fn)(plan=self.plan, task=self.task, **kw)

	def full(self):
		return frappe.db.get_value("Work Plan Task", self.task,
			["due_date", "original_due_date", "postpone_count", "status", "deviation", "postpone_reason",
			"postponed_by", "parent"], as_dict=True)

	def add_work(self, qty=4):
		w = _make("Casual Labour Work", work_date=today(), employee=self.employee.name, unit=self.u1.name,
			operation=self.op.name, qty=qty, uom="Kg", plan=self.plan, plan_task=self.task)
		frappe.db.set_value("Work Plan Task", self.task, "done_qty", qty)
		frappe.db.commit()
		return w

	def test_move_same_week(self):
		d = add_days(self.start, 2)
		res = self.call("move_plan_task", self.mgr, new_date=d)
		self.assertNotIn("error", res)
		r = self.full()
		self.assertEqual(getdate(r.due_date), getdate(d))
		self.assertEqual(getdate(r.original_due_date), getdate(self.start))
		self.assertEqual(r.postpone_count or 0, 0)

	def test_move_other_week_refused(self):
		res = self.call("move_plan_task", self.mgr, new_date=add_days(self.start, 8))
		self.assertIn("same week", res["error"])
		self.assertEqual(getdate(self.full().due_date), getdate(self.start))

	def test_postpone_same_week_stamps(self):
		d = add_days(self.start, 3)
		res = self.call("postpone_plan_task", self.mgr, new_date=d, reason="Rain")
		self.assertNotIn("error", res)
		r = self.full()
		self.assertEqual(getdate(r.due_date), getdate(d))
		self.assertEqual(getdate(r.original_due_date), getdate(self.start))
		self.assertEqual((r.postpone_count, r.deviation, r.postpone_reason, r.postponed_by),
			(1, "Late", "Rain", self.mgr))
		self.assertFalse(res["split"])

	def test_postpone_next_week_moves_row(self):
		d = add_days(self.start, 8)
		res = self.call("postpone_plan_task", self.mgr, new_date=d, reason="Rain")
		self.assertNotIn("error", res)
		self.assertFalse(frappe.db.exists("Work Plan Task", self.task))
		y, w = iso_of(d)
		new_plan = frappe.db.get_value("Production Work Plan",
			{"crop": self.crop.name, "farm": self.farm.name, "plan_year": y, "plan_week": w})
		self.assertTrue(new_plan)
		self.addCleanup(lambda: (frappe.set_user("Administrator"),
			frappe.delete_doc("Production Work Plan", new_plan, force=True), frappe.db.commit()))
		rows = frappe.get_all("Work Plan Task", filters={"parent": new_plan},
			fields=["due_date", "deviation", "postpone_count", "original_due_date"])
		self.assertEqual(len(rows), 1)
		self.assertEqual((rows[0].deviation, rows[0].postpone_count), ("Late", 1))
		self.assertEqual(getdate(rows[0].original_due_date), getdate(self.start))

	def test_postpone_twice_counts_2_keeps_first_date(self):
		self.call("postpone_plan_task", self.mgr, new_date=add_days(self.start, 2), reason="Rain")
		res = self.call("postpone_plan_task", self.mgr, new_date=add_days(self.start, 4), reason="Rain again")
		self.assertNotIn("error", res)
		r = self.full()
		self.assertEqual(r.postpone_count, 2)
		self.assertEqual(getdate(r.original_due_date), getdate(self.start))

	def test_postpone_with_work_splits(self):
		frappe.db.set_value("Work Plan Task", self.task, "planned_qty", 10)
		self.add_work(4)
		d = add_days(self.start, 3)
		res = self.call("postpone_plan_task", self.mgr, new_date=d, reason="Short of labour")
		self.assertNotIn("error", res)
		data = res
		self.assertTrue(data["split"])
		self.assertEqual(self.full().status, "Partly Done")
		self.assertEqual(frappe.db.count("Casual Labour Work", {"plan_task": self.task}), 1)
		new = frappe.db.get_value("Work Plan Task", data["task"],
			["planned_qty", "status", "due_date", "postpone_count", "deviation"], as_dict=True)
		self.assertEqual((new.planned_qty, new.status, new.postpone_count, new.deviation), (6, "Open", 1, "Late"))
		self.assertEqual(frappe.db.get_value("Work Plan Task", self.task, "planned_qty"), 4)  # done + pending stay
		self.assertEqual(getdate(new.due_date), getdate(d))
		self.assertNotEqual(data["task"], self.task)

	def _log(self, notes="did some"):
		from upande_production.production.logic import progress
		frappe.set_user("Administrator")
		log = progress.log_progress(self.plan, self.task, notes=notes)
		frappe.db.commit()
		self.addCleanup(lambda: (frappe.db.delete("Task Progress Log", {"name": log["name"]}), frappe.db.commit()))
		return log["name"]

	def test_postpone_next_week_moves_progress_logs(self):
		log = self._log()
		d = add_days(self.start, 8)
		res = self.call("postpone_plan_task", self.mgr, new_date=d, reason="Rain")
		self.assertNotIn("error", res)
		self.addCleanup(lambda: (frappe.set_user("Administrator"),
			frappe.delete_doc("Production Work Plan", res["plan"], force=True), frappe.db.commit()))
		self.assertEqual(frappe.db.get_value("Task Progress Log", log, ["plan", "task"], as_dict=True),
			{"plan": res["plan"], "task": res["task"]})

	def test_postpone_split_keeps_progress_logs_on_original(self):
		frappe.db.set_value("Work Plan Task", self.task, "planned_qty", 10)
		self.add_work(4)
		log = self._log()
		res = self.call("postpone_plan_task", self.mgr, new_date=add_days(self.start, 3), reason="x")
		self.assertTrue(res["split"])
		self.assertEqual(frappe.db.get_value("Task Progress Log", log, ["plan", "task"], as_dict=True),
			{"plan": self.plan, "task": self.task})

	def test_delete_refused_with_progress_logs(self):
		self._log()
		msg = "Progress is logged on this task; mark it Skipped instead."
		res = self.call("delete_plan_task", self.mgr, reason="x")
		self.assertIn(msg, res["error"])
		res = self.save([{"name": self.task, "_delete": 1}], self.mgr)
		self.assertIn(msg, res["error"])
		self.assertTrue(frappe.db.exists("Work Plan Task", self.task))

	def _assigned(self):
		frappe.db.set_value("Work Plan Task", self.task, {"assigned_by": self.sup, "awaiting_approval": 1,
			"forwarded_by": self.mgr, "forwarded_on": "2026-01-01 10:00:00"})
		frappe.db.commit()

	def _approval_of(self, task):
		return frappe.db.get_value("Work Plan Task", task,
			["assigned_by", "awaiting_approval", "forwarded_by", "forwarded_on"], as_dict=True)

	def test_postpone_split_keeps_approval_fields(self):
		frappe.db.set_value("Work Plan Task", self.task, "planned_qty", 10)
		self._assigned()
		self.add_work(4)
		res = self.call("postpone_plan_task", self.editor, new_date=add_days(self.start, 3), reason="Rain")
		self.assertNotIn("error", res)
		a = self._approval_of(res["task"])
		self.assertEqual((a.assigned_by, a.awaiting_approval, a.forwarded_by), (self.sup, 1, self.mgr))
		self.assertTrue(a.forwarded_on)

	def test_postpone_to_next_week_keeps_approval_fields(self):
		self._assigned()
		res = self.call("postpone_plan_task", self.editor, new_date=add_days(self.start, 8), reason="Rain")
		self.assertNotIn("error", res)
		new_plan = frappe.db.get_value("Work Plan Task", res["task"], "parent")
		self.addCleanup(lambda: (frappe.set_user("Administrator"),
			frappe.delete_doc("Production Work Plan", new_plan, force=True), frappe.db.commit()))
		a = self._approval_of(res["task"])
		self.assertEqual((a.assigned_by, a.awaiting_approval, a.forwarded_by), (self.sup, 1, self.mgr))

	def test_postpone_nothing_left_refused(self):
		self.add_work(5)
		res = self.call("postpone_plan_task", self.mgr, new_date=add_days(self.start, 3), reason="Rain")
		self.assertIn("Nothing is left", res["error"])

	def test_postpone_done_refused(self):
		frappe.db.set_value("Work Plan Task", self.task, "status", "Done")
		frappe.db.commit()
		res = self.call("postpone_plan_task", self.mgr, new_date=add_days(self.start, 3), reason="Rain")
		self.assertIn("Done task cannot be postponed", res["error"])
		self.assertEqual(getdate(self.full().due_date), getdate(self.start))

	def test_postpone_requires_reason(self):
		res = self.call("postpone_plan_task", self.mgr, new_date=add_days(self.start, 3), reason="  ")
		self.assertIn("reason", res["error"])
		self.assertEqual(getdate(self.full().due_date), getdate(self.start))

	def test_delete_logs_comment(self):
		res = self.call("delete_plan_task", self.mgr, reason="Not needed")
		self.assertNotIn("error", res)
		self.assertFalse(frappe.db.exists("Work Plan Task", self.task))
		text = f"Deleted task PTS Weeding on {self.u1.name}, due {getdate(self.start)}: Not needed"
		self.assertTrue(frappe.db.exists("Comment", {"reference_doctype": "Production Work Plan",
			"reference_name": self.plan, "comment_type": "Comment", "content": ("like", f"%{text}%")}))

	def test_delete_with_work_refused(self):
		self.add_work(2)
		res = self.call("delete_plan_task", self.mgr, reason="Oops")
		self.assertIn("Skip", res["error"])
		self.assertTrue(frappe.db.exists("Work Plan Task", self.task))

	def test_plain_supervisor_refused_on_all_three(self):
		d = add_days(self.start, 2)
		for fn, kw in (("move_plan_task", {"new_date": d}),
				("postpone_plan_task", {"new_date": d, "reason": "x"}), ("delete_plan_task", {"reason": "x"})):
			res = self.call(fn, self.sup, **kw)
			self.assertIn("not permitted", res["error"], fn)
		self.assertTrue(frappe.db.exists("Work Plan Task", self.task))

	def test_crop_restricted_user_refused(self):
		d = add_days(self.start, 2)
		for fn, kw in (("move_plan_task", {"new_date": d}),
				("postpone_plan_task", {"new_date": d, "reason": "x"}), ("delete_plan_task", {"reason": "x"})):
			res = self.call(fn, self.avo, **kw)
			self.assertIn("not permitted to see this crop", res["error"], fn)
		self.assertEqual(getdate(self.full().due_date), getdate(self.start))

	# ---- final review fixes ----

	def _direct(self, user, mutate):
		frappe.set_user(user)
		doc = frappe.get_doc("Production Work Plan", self.plan)
		mutate(doc)
		doc.save()

	def test_direct_save_remove_row_refused_for_supervisor(self):
		with self.assertRaises(frappe.PermissionError):
			self._direct(self.sup, lambda d: d.set("tasks", []))
		frappe.set_user("Administrator")
		self.assertTrue(frappe.db.exists("Work Plan Task", self.task))

	def test_direct_save_redate_refused_for_supervisor(self):
		def redate(d):
			d.tasks[0].due_date = add_days(self.start, 2)
		with self.assertRaises(frappe.PermissionError):
			self._direct(self.sup, redate)
		self.assertEqual(getdate(self.row().due_date), getdate(self.start))

	def test_direct_save_remove_row_with_work_refused_even_for_manager(self):
		self.add_work(2)
		with self.assertRaises(frappe.ValidationError):
			self._direct(self.mgr, lambda d: d.set("tasks", []))
		frappe.set_user("Administrator")
		self.assertTrue(frappe.db.exists("Work Plan Task", self.task))

	def test_supervisor_can_still_edit_other_fields_directly(self):
		def edit(d):
			d.tasks[0].note = "hello"
		self._direct(self.sup, edit)

	def _protocol_task(self, ref):
		frappe.db.set_value("Work Plan Task", self.task, "protocol_ref", ref)
		frappe.db.commit()

	def test_delete_records_dropped_ref(self):
		self._protocol_task("PROTO-1#1")
		self.call("delete_plan_task", self.mgr, reason="No")
		refs = frappe.db.get_value("Production Work Plan", self.plan, "dropped_protocol_refs")
		self.assertIn("PROTO-1#1", refs.splitlines())

	def test_postpone_next_week_records_dropped_ref(self):
		self._protocol_task("PROTO-2#1")
		d = add_days(self.start, 8)
		self.call("postpone_plan_task", self.mgr, new_date=d, reason="Rain")
		y, w = iso_of(d)
		new_plan = frappe.db.get_value("Production Work Plan",
			{"crop": self.crop.name, "farm": self.farm.name, "plan_year": y, "plan_week": w})
		self.addCleanup(lambda: (frappe.set_user("Administrator"),
			frappe.delete_doc("Production Work Plan", new_plan, force=True), frappe.db.commit()))
		refs = frappe.db.get_value("Production Work Plan", self.plan, "dropped_protocol_refs")
		self.assertIn("PROTO-2#1", refs.splitlines())

	def test_cross_week_copy_drops_wm_and_progress(self):
		frappe.db.set_value("Work Plan Task", self.task, {"wm_planner": "WMP-1", "wm_assigner": "WMA-1",
			"done_qty": 0, "pending_qty": 0, "status": "Pending"})
		frappe.db.commit()
		d = add_days(self.start, 8)
		res = self.call("postpone_plan_task", self.mgr, new_date=d, reason="Rain")
		new_plan = res["plan"]
		self.addCleanup(lambda: (frappe.set_user("Administrator"),
			frappe.delete_doc("Production Work Plan", new_plan, force=True), frappe.db.commit()))
		n = frappe.db.get_value("Work Plan Task", res["task"], ["wm_planner", "wm_assigner", "status"], as_dict=True)
		self.assertEqual((n.wm_planner, n.wm_assigner, n.status), (None, None, "Open"))

	def test_move_finished_task_refused(self):
		for st in ("Done", "Skipped"):
			frappe.db.set_value("Work Plan Task", self.task, "status", st)
			frappe.db.commit()
			res = self.call("move_plan_task", self.mgr, new_date=add_days(self.start, 2))
			self.assertIn("finished task", res["error"])
		self.assertEqual(getdate(self.full().due_date), getdate(self.start))
