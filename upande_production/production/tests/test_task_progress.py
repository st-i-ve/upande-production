import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import today

from upande_production.api import production as desk
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from frappe.utils import add_days

from upande_production.production.logic import approvals, progress, cycle_setup, plans, settings, task_approval, work
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


class TestTaskProgress(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		use_builtin_labour(cls)
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make("Farm", farm_name="TPL Farm", company=cls.company, abbreviation="TPL",
			farm_type=[{"farm_type": "Has Blocks"}])
		cls.crop = _make("Production Crop", crop_name="TPL Crop", crop_key="tpl-crop", unit_label="Block", yield_uom="Kg", uses_crop_cycles=1)
		cls.op = _make("Field Operation", crop=cls.crop.name, operation_name="TPL Weeding",
			category="Other", work_uom="Kg", default_rate=40)
		cls.item = _make("Item", item_code="TPL Tomato", item_name="TPL Tomato", item_group="All Item Groups",
			stock_uom="Kg", is_stock_item=1).name
		cls.protocol = _make("Production Protocol", protocol_name="TPL Proto", crop=cls.crop.name,
			version_status="Active", key_activities=[{"operation": cls.op.name, "week": w, "planned_qty": 1} for w in (1, 2, 3)]).name
		cls.u1 = _make("Production Unit", unit_name="TPL B1", crop=cls.crop.name, farm=cls.farm.name,
			unit_type="Orchard Block", company=cls.company, area_ha=1, plant_count=0)
		cls.u2 = _make("Production Unit", unit_name="TPL B2", crop=cls.crop.name, farm=cls.farm.name,
			unit_type="Orchard Block", company=cls.company, area_ha=1, plant_count=0)
		cls.mgr = _user("tpl.mgr@x.test", "Production Manager")
		cls.sup = _user("tpl.sup@x.test", "Production Supervisor")
		cls.asst = _user("tpl.asst@x.test", settings.ASSISTANT_ROLE)
		cls.emp = _make("Employee", first_name="TPLEmp", gender="Male", date_of_birth="1990-01-01",
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
		frappe.db.delete("Task Progress Log", {"crop": cls.crop.name})
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
		frappe.db.delete("Task Progress Log", {"crop": self.crop.name})
		frappe.db.delete("File", {"file_name": ("like", "tpl-%")})
		frappe.clear_cache(user=self.asst)  # a test may have dropped the role in an uncommitted change
		for p in frappe.get_all("Production Work Plan", filters={"crop": self.crop.name}, pluck="name"):
			frappe.delete_doc("Production Work Plan", p, force=True)
		for c in frappe.get_all("Production Crop Cycle", filters={"unit": self.u1.name}, pluck="name"):
			frappe.delete_doc("Production Crop Cycle", c, force=True)
		frappe.db.commit()

	MSG = "Your progress for today has been logged. Wait for tomorrow to make another log."

	def add_task(self, user="Administrator", step=False):
		set_step(step)
		frappe.set_user(user)
		res = desk.save_plan_tasks(self.crop.name, self.farm.name, self.year, self.week,
			[{"unit": self.u1.name, "operation": self.op.name, "planned_qty": 5, "due_date": self.start}])
		self.assertNotIn("error", res)
		frappe.set_user("Administrator")
		frappe.db.commit()
		task = frappe.get_all("Work Plan Task", filters={"parent": res["name"]}, pluck="name")[0]
		return res["name"], task

	def crew(self, plan, task, day=None, status="In Progress"):
		res = desk.record_task_work(plan, task, status, [{"employee": self.emp, "qty": 1}], work_date=day)
		frappe.db.commit()  # the desk request commits on success; a later refusal rolls back only its own work
		return res

	# -- same-day rule -------------------------------------------------------------

	def test_same_day_second_crew_save_refused(self):
		plan, task = self.add_task()
		self.assertNotIn("error", self.crew(plan, task))
		res = self.crew(plan, task)
		self.assertEqual(res.get("error"), self.MSG)
		self.assertEqual(len(frappe.get_all("Casual Labour Work", filters={"plan_task": task, "docstatus": ("<", 2)})), 1)

	def test_next_day_allowed(self):
		plan, task = self.add_task()
		self.assertNotIn("error", self.crew(plan, task, day=add_days(today(), -1)))
		self.assertNotIn("error", self.crew(plan, task, day=today()))
		self.assertEqual(len(frappe.get_all("Casual Labour Work", filters={"plan_task": task, "docstatus": ("<", 2)})), 2)

	def test_status_only_same_day_allowed(self):
		plan, task = self.add_task()
		self.assertNotIn("error", self.crew(plan, task))
		res = desk.record_task_work(plan, task, "In Progress", [], note="still going")
		self.assertNotIn("error", res)

	# -- progress logs -------------------------------------------------------------

	def test_log_progress_notes_only(self):
		plan, task = self.add_task()
		log = progress.log_progress(plan, task, notes="  Weeded the north rows  ")
		self.assertEqual(log["notes"], "Weeded the north rows")
		self.assertEqual((log["plan"], log["task"], log["unit"], log["operation"], log["crop"]),
			(plan, task, self.u1.name, self.op.name, self.crop.name))
		self.assertEqual(str(log["log_date"]), today())
		self.assertEqual(log["logged_by"], "Administrator")
		self.assertEqual(log["attachments"], [])
		self.assertIsNone(log["uom"])
		self.assertEqual(progress.log_progress(plan, task, qty=1.5)["uom"], "Kg")
		# any number of logs a day
		progress.log_progress(plan, task, qty=2)
		self.assertEqual(len(progress.list_progress(plan, task)), 3)

	def test_log_progress_requires_something(self):
		plan, task = self.add_task()
		for kw in ({}, {"notes": "  "}, {"files": []}):
			with self.assertRaises(frappe.ValidationError):
				progress.log_progress(plan, task, **kw)
		with self.assertRaises(frappe.ValidationError):
			progress.log_progress(plan, task, qty=-1)
		with self.assertRaises(frappe.ValidationError):
			progress.log_progress(plan, task, notes="x", log_date=add_days(today(), 1))
		self.assertEqual(progress.list_progress(plan, task), [])

	def test_log_progress_no_labour_rows(self):
		plan, task = self.add_task()
		before = frappe.db.get_value("Work Plan Task", task, ["done_qty", "pending_qty"])
		progress.log_progress(plan, task, qty=3, notes="done a lot")
		self.assertEqual(frappe.db.get_value("Work Plan Task", task, ["done_qty", "pending_qty"]), before)
		self.assertEqual(frappe.db.count("Casual Labour Work", {"plan_task": task}), 0)

	def test_supervisor_can_log_and_read(self):
		plan, task = self.add_task()
		frappe.set_user(self.sup)
		res = desk.log_task_progress(plan, task, notes="from the field")
		self.assertNotIn("error", res)
		self.assertEqual(res["logged_by"], self.sup)
		self.assertEqual(len(desk.list_task_progress(plan, task)), 1)

	def test_log_on_awaiting_refused_for_supervisor(self):
		plan, task = self.add_task(self.asst, step=True)
		frappe.set_user(self.sup)
		res = desk.log_task_progress(plan, task, notes="sneaky")
		self.assertIn("error", res)
		self.assertIn("waiting for a manager's approval", res["error"])
		self.assertIn("error", desk.list_task_progress(plan, task))
		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.count("Task Progress Log", {"task": task}), 0)
		# logging is refused for everyone while it awaits (like recording work); managers and assistants can read
		for u in (self.asst, self.mgr):
			frappe.set_user(u)
			self.assertIn("error", desk.log_task_progress(plan, task, notes="ok"), u)
			self.assertEqual(desk.list_task_progress(plan, task), [], u)

	def test_files_attached_to_log(self):
		plan, task = self.add_task()
		f = frappe.get_doc({"doctype": "File", "file_name": "tpl-proof.txt", "content": b"hello", "is_private": 1}).insert()
		g = frappe.get_doc({"doctype": "File", "file_name": "tpl-proof.png", "content": b"\x89PNG", "is_private": 1}).insert()
		log = progress.log_progress(plan, task, files=[f.file_url, g.file_url])
		self.assertEqual([a["file_url"] for a in log["attachments"]], [f.file_url, g.file_url])
		self.assertEqual([a["is_image"] for a in log["attachments"]], [0, 1])
		self.assertEqual(log["attachments"][0]["file_name"], "tpl-proof.txt")
		for doc in (f, g):
			doc.reload()
			self.assertEqual((doc.attached_to_doctype, doc.attached_to_name), ("Task Progress Log", log["name"]))
			self.assertEqual(doc.is_private, 1)
		with self.assertRaises(frappe.ValidationError):
			progress.log_progress(plan, task, files=["/private/files/does-not-exist.txt"])

	def test_supervisor_files(self):
		plan, task = self.add_task()
		frappe.set_user(self.sup)
		f = frappe.get_doc({"doctype": "File", "file_name": "tpl-sup.txt", "content": b"hi", "is_private": 1}).insert()
		res = desk.log_task_progress(plan, task, files=[f.file_url])
		self.assertNotIn("error", res)
		self.assertEqual(len(res["attachments"]), 1)

	def test_list_newest_first(self):
		plan, task = self.add_task()
		a = progress.log_progress(plan, task, notes="old", log_date=add_days(today(), -2))
		b = progress.log_progress(plan, task, notes="today first")
		c = progress.log_progress(plan, task, notes="today second")
		frappe.db.set_value("Task Progress Log", b["name"], "logged_at", frappe.utils.add_to_date(None, minutes=-5))
		self.assertEqual([x["notes"] for x in progress.list_progress(plan, task)], ["today second", "today first", "old"])
		self.assertEqual(progress.latest_by_task(plan), {task: frappe.utils.getdate(today())})

	def test_get_plan_last_progress_on(self):
		plan, task = self.add_task()
		rows = desk.get_plan(self.crop.name, self.farm.name, self.year, self.week)["tasks"]
		self.assertIsNone(rows[0]["last_progress_on"])
		progress.log_progress(plan, task, notes="a", log_date=add_days(today(), -1))
		rows = desk.get_plan(self.crop.name, self.farm.name, self.year, self.week)["tasks"]
		self.assertEqual(str(rows[0]["last_progress_on"]), add_days(today(), -1))

	def _phone(self, fn, payload, user="Administrator"):
		frappe.set_user(user)
		frappe.response.pop("data", None)
		try:
			with patch.object(frappe.local, "request", SimpleNamespace(get_json=lambda: payload), create=True):
				fn()
		finally:
			frappe.set_user("Administrator")
		return frappe.response["data"]

	def test_phone_endpoints_roundtrip(self):
		from upande_production.mobile import progress as mp
		from upande_production.mobile import api as mobile
		plan, task = self.add_task()
		frappe.set_user(self.sup)
		f = frappe.get_doc({"doctype": "File", "file_name": "tpl-ph.txt", "content": b"x", "is_private": 1}).insert()
		frappe.set_user("Administrator")
		res = self._phone(mp.productionLogProgress, {"plan": plan, "task": task, "notes": "phone note", "qty": 2,
			"files": [f.file_url]}, self.sup)
		self.assertEqual(res["status"], "success", res)
		self.assertEqual(res["log"]["notes"], "phone note")
		self.assertEqual(len(res["log"]["attachments"]), 1)
		res = self._phone(mp.productionListProgress, {"plan": plan, "task": task}, self.sup)
		self.assertEqual(res["status"], "success")
		self.assertEqual([l["notes"] for l in res["logs"]], ["phone note"])
		# empty log and missing fields refused
		res = self._phone(mp.productionLogProgress, {"plan": plan, "task": task}, self.sup)
		self.assertIn("error", res)
		res = self._phone(mp.productionLogProgress, {"plan": plan}, self.sup)
		self.assertIn("error", res)
		# viewer cannot log
		viewer = _user("tpl.view@x.test", "Production Viewer")
		res = self._phone(mp.productionLogProgress, {"plan": plan, "task": task, "notes": "n"}, viewer)
		self.assertIn("error", res)
		# the phone task lists carry last_progress_on
		frappe.set_user("Administrator")
		pl = self._phone(mobile.productionGetPlanDetail, {"crop": self.crop.name, "farm": self.farm.name, "year": self.year, "week": self.week})
		self.assertEqual(pl["blocks"][0]["tasks"][0]["last_progress_on"], frappe.utils.getdate(today()))
		wk = self._phone(mobile.productionGetWeekPlan, {"crop": self.crop.name, "farm": self.farm.name, "year": self.year, "week": self.week})
		self.assertEqual(wk["tasks"][0]["last_progress_on"], frappe.utils.getdate(today()))
		frappe.delete_doc("User", viewer, force=True)
