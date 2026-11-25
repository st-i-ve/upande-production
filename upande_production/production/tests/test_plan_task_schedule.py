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
		cls.crop = _make("Production Crop", crop_name="PTS Crop", crop_key="pts-crop", unit_label="Block", yield_uom="Kg")
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
				("Field Operation", cls.op), ("Production Crop", cls.crop), ("Farm", cls.farm)):
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
		self.assertEqual(getdate(new.due_date), getdate(d))
		self.assertNotEqual(data["task"], self.task)

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
