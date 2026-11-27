import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, now_datetime, today

from upande_production.api import labourers as lab_api
from upande_production.api import supervisors as sup_api
from upande_production.production.logic import people, plans, supervisors
from upande_production.production.logic.weeks import iso_of
from upande_production.production.tests.labour_mode import use_builtin_labour


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


def _user(email, role):
	if not frappe.db.exists("User", email):
		_make("User", email=email, first_name=email.split("@")[0], send_welcome_email=0, roles=[{"role": role}])
	return email


def _employee(first, company, **kw):
	return _make("Employee", first_name=first, gender="Male", date_of_birth="1990-01-01",
		date_of_joining="2020-01-01", company=company, **kw)


def _clw(name, emp, crop, unit, op, qty, day, status="Approved", docstatus=1, plan_task=None, created=None, checked=None):
	frappe.db.sql("""insert into `tabCasual Labour Work` (name, employee, crop, unit, operation, qty, uom, work_date, plan_task,
		docstatus, approval_status, checked_at, creation, modified, owner, modified_by)
		values (%s, %s, %s, %s, %s, %s, 'Kg', %s, %s, %s, %s, %s, %s, now(), 'Administrator', 'Administrator')""",
		(name, emp, crop, unit, op, qty, day, plan_task, docstatus, status, checked, created or now_datetime()))


def _log(name, task, day):
	frappe.db.sql("""insert into `tabTask Progress Log` (name, task, log_date, creation, modified, owner, modified_by)
		values (%s, %s, %s, now(), now(), 'Administrator', 'Administrator')""", (name, task, day))


class TestPeopleProfiles(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		use_builtin_labour(cls)
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make("Farm", farm_name="PPL Farm", company=cls.company, abbreviation="PPL",
			farm_type=[{"farm_type": "Has Blocks"}])
		cls.crop = _make("Production Crop", crop_name="PPL Crop", crop_key="ppl-crop", unit_label="Block", yield_uom="Kg")
		cls.op = _make("Field Operation", crop=cls.crop.name, operation_name="PPL Weeding", category="Other", work_uom="Kg", default_rate=40)
		cls.spray = _make("Field Operation", crop=cls.crop.name, operation_name="PPL Spray", category="Spraying", work_uom="Kg", default_rate=40)
		cls.u1 = _make("Production Unit", unit_name="PPL B1", crop=cls.crop.name, farm=cls.farm.name, unit_type="Orchard Block", company=cls.company)
		cls.u2 = _make("Production Unit", unit_name="PPL B2", crop=cls.crop.name, farm=cls.farm.name, unit_type="Orchard Block", company=cls.company)
		cls.sup_user = _user("ppl.sup@x.test", "Production Supervisor")
		cls.year, cls.week = iso_of(today())

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		frappe.db.rollback()
		super().tearDownClass()

	def setUp(self):
		frappe.db.savepoint("ppl_test")
		self.addCleanup(frappe.db.rollback, save_point="ppl_test")
		self.addCleanup(frappe.set_user, "Administrator")
		self.a = _employee("PPLA", self.company)
		self.b = _employee("PPLB", self.company)
		self.me = _employee("PPLMe", self.company, user_id=self.sup_user)
		for e in (self.a, self.b, self.me):
			_make("Production Supervisor", employee=e.name)

	def _two_weeks(self):
		old = iso_of(add_days(today(), -14))
		for y, w in ((self.year, self.week), old):
			supervisors.save_week(self.crop.name, self.farm.name, y, w, [
				{"unit": self.u1.name, "supervisor": self.a.name, "category": ""},
				{"unit": self.u2.name, "supervisor": self.a.name, "category": "Spraying"},
				{"unit": self.u2.name, "supervisor": self.b.name, "category": ""}])
		new = plans.get_or_create_plan(self.crop.name, self.farm.name, self.year, self.week)
		for unit, op, status in ((self.u1, self.op, "Done"), (self.u1, self.op, "Open")):
			new.append("tasks", {"unit": unit.name, "operation": op.name, "planned_qty": 5, "uom": "Kg", "rate": 40,
				"due_date": today(), "status": status})
		new.save()
		past = plans.get_or_create_plan(self.crop.name, self.farm.name, *old)
		for op, status, count in ((self.spray, "Open", 0), (self.op, "Done", 1)):
			past.append("tasks", {"unit": self.u2.name, "operation": op.name, "planned_qty": 5, "uom": "Kg", "rate": 40,
				"due_date": add_days(today(), -14), "status": status, "postpone_count": count})
		past.save()
		frappe.db.sql("update `tabWork Plan Task` set completed_at = %s where parent = %s and status = 'Done'",
			(now_datetime(), new.name))
		frappe.db.sql("update `tabWork Plan Task` set completed_at = %s where parent = %s and status = 'Done'",
			(add_days(today(), -14), past.name))
		return new, past

	def _row(self, emp, **kw):
		res = people.supervisor_people(self.crop.name, **kw)
		return res, next(p for p in res["people"] if p["employee"] == emp.name)

	def test_supervisor_figures(self):
		new, _past = self._two_weeks()
		done = next(t.name for t in new.tasks if t.status == "Done")
		_log("PPL-L1", done, today())
		_log("PPL-L2", done, add_days(today(), -1))
		x = _employee("PPLX", self.company)
		_make("Casual Labourer", employee=x.name, active=1, supervisor=self.a.name)
		c, u, o = self.crop.name, self.u1.name, self.op.name
		_clw("PPL-W1", x.name, c, u, o, 5, today(), "Sent Back", 0)
		_clw("PPL-W2", x.name, c, u, o, 5, add_days(today(), -1), "Checked", 0, created=add_days(now_datetime(), -3), checked=add_days(now_datetime(), -1))
		_clw("PPL-W3", x.name, c, u, o, 5, add_days(today(), -2), "Pending", 0)
		res, a = self._row(self.a)
		m = a["metrics"]
		self.assertEqual((m["assigned"], m["done"]), (3, 1))
		self.assertEqual(m["on_time_pct"], 33.3)
		self.assertEqual(m["late_pct"], 33.3)  # the overdue spray
		self.assertEqual((m["logs"], m["active_days"], m["logs_per_day"]), (2, 2, 1.0))
		self.assertEqual((m["sent_back"], m["entries"], m["sent_back_pct"]), (1, 3, 33.3))
		self.assertEqual(m["check_days"], 2.0)
		self.assertEqual({f["kind"]: f["count"] for f in a["flags"]}, {"overdue": 1, "waiting": 1, "stale": 1})
		self.assertEqual(sum(w["done"] for w in a["weekly"]), 1)
		self.assertEqual(sum(w["logs"] for w in a["weekly"]), 2)
		self.assertEqual(a["where"][0]["share"], 66.7)  # two of three tasks on B1
		self.assertTrue(a["overseer"])
		self.assertEqual((a["blocks"], a["activities"]), (2, 1))
		_res, b = self._row(self.b)
		self.assertEqual((b["metrics"]["assigned"], b["metrics"]["on_time_pct"], b["metrics"]["late_pct"]), (1, 100.0, 100.0))
		self.assertAlmostEqual(res["medians"]["on_time_pct"], 66.7, delta=0.1)
		self.assertEqual(len(res["weeks"]), len(set(res["weeks"])))

	def test_range_limits_tasks_and_crew_figures_hidden_from_others(self):
		self._two_weeks()
		_res, a = self._row(self.a, from_date=add_days(today(), -3), to_date=today())
		self.assertEqual(a["metrics"]["assigned"], 2)  # the old week's spray is outside the range
		frappe.set_user(self.sup_user)
		_res, a = self._row(self.a)
		self.assertFalse(a["full"])
		self.assertIsNone(a["metrics"]["sent_back"])
		self.assertFalse(any(f["kind"] == "waiting" for f in a["flags"]))
		self.assertEqual(a["metrics"]["assigned"], 3)

	def test_inactive_and_crop_scope(self):
		other = _make("Production Crop", crop_name="PPL Other", crop_key="ppl-other", unit_label="Block", yield_uom="Kg")
		scoped = _employee("PPLS", self.company)
		_make("Production Supervisor", employee=scoped.name, crops=[{"crop": other.name}])
		res = people.supervisor_people(self.crop.name)
		self.assertNotIn(scoped.name, [p["employee"] for p in res["people"]])
		frappe.db.set_value("Production Supervisor", self.b.name, "active", 0)
		_res, b = self._row(self.b)
		self.assertFalse(b["active"])
		self.assertEqual(b["metrics"]["assigned"], 0)

	def test_api_endpoints_return_the_payload(self):
		res = sup_api.people_supervisors(crop=self.crop.name)
		self.assertIn("people", res)
		res = lab_api.people_labourers(crop=self.crop.name)
		self.assertIn("medians", res)

	def _labourers(self):
		c, u = self.crop.name, self.u1.name
		self.x, self.y, self.z, self.w = (_employee(n, self.company) for n in ("PPLLX", "PPLLY", "PPLLZ", "PPLLW"))
		for e in (self.x, self.y, self.z, self.w):
			_make("Casual Labourer", employee=e.name, active=1, supervisor=self.a.name)
		_clw("PPL-X1", self.x.name, c, u, self.op.name, 100, add_days(today(), -1), plan_task="T1")
		_clw("PPL-X2", self.x.name, c, u, self.op.name, 100, add_days(today(), -2), plan_task="T2")
		_clw("PPL-Y1", self.y.name, c, u, self.op.name, 50, add_days(today(), -1), plan_task="T1")
		_clw("PPL-Y2", self.y.name, c, u, self.op.name, 10, add_days(today(), -3), "Sent Back", 0)
		_clw("PPL-W1", self.w.name, c, u, self.op.name, 10, add_days(today(), -40))

	def _lrow(self, emp):
		res = people.labourer_people(self.crop.name)
		return res, next(p for p in res["people"] if p["employee"] == emp.name)

	def test_labourer_figures_and_peer_output(self):
		self._labourers()
		res, x = self._lrow(self.x)
		m = x["metrics"]
		self.assertEqual((m["days_worked"], m["tasks"], m["sent_back"]), (2, 2, 0))
		self.assertEqual((m["output_per_day"], x["output_uom"]), (100.0, "Kg"))
		self.assertEqual(m["output_vs_peers"], 133.3)  # 100 a day against a peer median of 75
		self.assertEqual(x["last_worked"], str(add_days(today(), -1)))
		_res, y = self._lrow(self.y)
		self.assertEqual(y["metrics"]["output_vs_peers"], 66.7)
		self.assertEqual((y["metrics"]["sent_back"], y["metrics"]["sent_back_pct"]), (1, 50.0))
		self.assertEqual(y["scores"]["quality"], 50.0)
		self.assertEqual([f["kind"] for f in y["flags"]], ["sent_back"])
		self.assertEqual(x["where_blocks"][0]["label"], "PPL B1")
		self.assertEqual(x["where_activities"][0]["share"], 100.0)
		self.assertEqual(sum(w["days"] for w in x["weekly"]), 2)
		self.assertEqual(sum(w["output"] for w in x["weekly"]), 200.0)
		self.assertAlmostEqual(res["medians"]["days_worked"], 1.5)

	def test_absent_flag_and_no_pay_fields(self):
		self._labourers()
		_res, z = self._lrow(self.z)
		self.assertEqual(z["flags"][0]["kind"], "absent")
		self.assertEqual(z["flags"][0]["detail"], "No work recorded yet.")
		_res, w = self._lrow(self.w)
		self.assertEqual(w["flags"][0]["count"], 40)
		self.assertEqual(w["metrics"]["days_worked"], 0)
		blob = repr(people.labourer_people(self.crop.name)) + repr(people.supervisor_people(self.crop.name))
		for word in ("pay_value", "rate", "unpaid"):
			self.assertNotIn(word, blob)
