import csv
import io

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from upande_production.api import labourpay as api
from upande_production.production.logic import attendance, labour, payrun, rates, work
from upande_production.production.logic.labour import DEFAULTS


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	frappe.db.commit()  # the API envelope rolls back on an error; committed fixtures survive that (cleaned in tearDownClass)
	return doc


def _set(**kw):
	for k, v in kw.items():
		frappe.db.set_single_value("Production Settings", k, v)
	frappe.clear_document_cache("Production Settings", "Production Settings")


class TestLabourPay(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make("Farm", farm_name="LP Farm", company=cls.company, abbreviation="LPF",
			farm_type=[{"farm_type": "Has Blocks"}])
		cls.crop = _make("Production Crop", crop_name="LP Crop", crop_key="lp-crop", unit_label="Block", yield_uom="Kg")
		cls.op = _make("Field Operation", crop=cls.crop.name, operation_name="LP Weeding", category="Other",
			work_uom="Kg", default_rate=40)
		cls.op2 = _make("Field Operation", crop=cls.crop.name, operation_name="LP Pruning", category="Other",
			work_uom="Kg", default_rate=10)
		cls.units = []
		cls.unit = _make("Production Unit", unit_name=frappe.generate_hash(length=6), crop=cls.crop.name,
			farm=cls.farm.name, unit_type="Orchard Block", company=cls.company)
		cls.unit2 = _make("Production Unit", unit_name=frappe.generate_hash(length=6), crop=cls.crop.name,
			farm=cls.farm.name, unit_type="Orchard Block", company=cls.company)
		cls.units = [cls.unit, cls.unit2]
		cls.emps = [_make("Employee", first_name=f"LP{i}", gender="Male", date_of_birth="1990-01-01",
			date_of_joining="2020-01-01", company=cls.company) for i in range(3)]
		frappe.db.commit()

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for dt in ("Casual Labour Pay Run", "Casual Labour Work"):
			for n in frappe.get_all(dt, filters={"employee": ("in", [e.name for e in cls.emps])} if dt == "Casual Labour Work"
				else {"farm": cls.farm.name}, pluck="name"):
				doc = frappe.get_doc(dt, n)
				if doc.docstatus == 1:
					doc.flags.ignore_links = True
					doc.cancel()
				frappe.delete_doc(dt, n, force=True)
		for dt, f in (("Field Operation Rate", {"operation": ("in", [cls.op.name, cls.op2.name])}),
			("Casual Labour Attendance", {"employee": ("in", [e.name for e in cls.emps])})):
			for n in frappe.get_all(dt, filters=f, pluck="name"):
				frappe.delete_doc(dt, n, force=True)
		_set(**{k: v for k, v in DEFAULTS.items() if k != "daily_wage"}, daily_wage=0)
		for doc in (*cls.units, cls.op, cls.op2, cls.crop, *cls.emps, cls.farm):
			frappe.delete_doc(doc.doctype, doc.name, force=True)
		if frappe.db.exists("User", "lp_viewer@example.com"):
			frappe.delete_doc("User", "lp_viewer@example.com", force=True)
		frappe.db.commit()
		super().tearDownClass()

	def setUp(self):
		_set(**{k: v for k, v in DEFAULTS.items() if k != "daily_wage"}, daily_wage=0)
		self._clean()

	def tearDown(self):
		frappe.set_user("Administrator")

	def _clean(self):
		for n in frappe.get_all("Casual Labour Pay Run", filters={"farm": self.farm.name}, pluck="name"):
			doc = frappe.get_doc("Casual Labour Pay Run", n)
			if doc.docstatus == 1:
				doc.status = "Approved"
				doc.cancel()
			frappe.delete_doc("Casual Labour Pay Run", n, force=True)
		for n in frappe.get_all("Casual Labour Work", filters={"employee": ("in", [e.name for e in self.emps])}, pluck="name"):
			doc = frappe.get_doc("Casual Labour Work", n)
			if doc.docstatus == 1:
				frappe.db.set_value("Casual Labour Work", n, "pay_run", None)
				doc.reload()
				doc.cancel()
			frappe.delete_doc("Casual Labour Work", n, force=True)
		for dt in ("Field Operation Rate", "Casual Labour Attendance"):
			f = {"operation": ("in", [self.op.name, self.op2.name])} if dt == "Field Operation Rate" \
				else {"employee": ("in", [e.name for e in self.emps])}
			for n in frappe.get_all(dt, filters=f, pluck="name"):
				frappe.delete_doc(dt, n, force=True)

	def _work(self, emp=0, day=None, op=None, unit=None, qty=5, rate=None, **kw):
		return _make("Casual Labour Work", work_date=day or today(), employee=self.emps[emp].name,
			unit=(unit or self.unit).name, operation=(op or self.op).name, qty=qty, uom="Kg",
			**({"rate": rate} if rate is not None else {}), **kw)

	def _period(self, frm, to=None, **kw):
		return _make("Field Operation Rate", operation=self.op.name, valid_from=frm, valid_to=to, **kw)

	# -- rates ---------------------------------------------------------------

	def test_rate_precedence(self):
		d = today()
		self.assertEqual(rates.rate_on(self.op.name, d)[0], 40)
		_set(daily_wage=400)
		p = self._period(add_days(d, -10), add_days(d, -5), daily_target=8)
		self.assertEqual(rates.rate_on(self.op.name, add_days(d, -7))[0], 50)  # wage / target
		self.assertEqual(rates.rate_on(self.op.name, d)[0], 40)  # outside the period: default
		p.rate = 45
		p.save()
		rate, label = rates.rate_on(self.op.name, add_days(d, -7))
		self.assertEqual(rate, 45)  # a rate beats wage / target
		self.assertIn(p.name, label)
		_set(daily_wage=0)
		p.rate = None
		p.save()
		self.assertEqual(rates.rate_on(self.op.name, add_days(d, -7))[0], 40)  # no wage: default

	def test_rate_overlap_and_dates(self):
		d = today()
		self._period(add_days(d, -10), add_days(d, -5), rate=1)
		with self.assertRaises(frappe.ValidationError):
			self._period(add_days(d, -7), add_days(d, -3), rate=2)
		with self.assertRaises(frappe.ValidationError):
			self._period(add_days(d, -20), add_days(d, -10), rate=2)
		with self.assertRaises(frappe.ValidationError):
			self._period(add_days(d, 3), add_days(d, 1), rate=2)
		self._period(add_days(d, -4), None, rate=3)  # open ended, right after
		with self.assertRaises(frappe.ValidationError):
			self._period(add_days(d, 5), None, rate=4)

	def test_work_takes_period_rate(self):
		d = today()
		self._period(add_days(d, -3), None, rate=55)
		w = self._work(day=add_days(d, -2))
		self.assertEqual((w.rate, w.pay_value), (55, 275))
		self.assertIn("Rate period", w.rate_source)
		old = self._work(1, day=add_days(d, -6))
		self.assertEqual((old.rate, old.rate_source), (40, "Operation default"))
		# the plan's copy of the default is not a decision; a different rate is, and stays
		self.assertEqual(self._work(2, day=add_days(d, -2), rate=40).rate, 55)
		manual = self._work(0, day=add_days(d, -1), op=self.op2, rate=99)
		self.assertEqual((manual.rate, manual.rate_source), (99, "Manual"))

	def test_rate_frozen_in_pay_run(self):
		w = self._work()
		w.submit()
		run = self._run()
		run.submit()
		self._period(add_days(today(), -3), None, rate=70)
		w.reload()
		w.validate()
		self.assertEqual(w.rate, 40)

	# -- guards --------------------------------------------------------------

	def test_duplicate_rules(self):
		self._work()
		with self.assertRaises(frappe.ValidationError):
			self._work()
		_set(duplicate_rule="Warn")
		w = self._work()
		self.assertIn("already recorded", w.rule_notes)
		_set(duplicate_rule="Off")
		self.assertFalse(self._work().rule_notes)
		# a different unit is not a duplicate
		_set(duplicate_rule="Block")
		self._work(1)
		self._work(1, unit=self.unit2)

	def test_multiple_jobs(self):
		self._work()
		_set(multiple_jobs_per_day="Allow")
		self.assertFalse(self._work(op=self.op2).rule_notes)
		_set(multiple_jobs_per_day="Warn")
		w = self._work(op=self.op2, unit=self.unit2)
		self.assertIn("another job", w.rule_notes)
		_set(multiple_jobs_per_day="Block")
		with self.assertRaises(frappe.ValidationError):
			self._work(op=self.op2, unit=self.unit2, qty=3)

	def test_dates(self):
		with self.assertRaises(frappe.ValidationError):
			self._work(day=add_days(today(), 1))
		self._work(day=add_days(today(), -400))  # 0 = no limit
		_set(max_backdate_days=7)
		with self.assertRaises(frappe.ValidationError):
			self._work(1, day=add_days(today(), -8))
		self._work(1, day=add_days(today(), -7))

	def test_attendance_required(self):
		d = today()
		_set(attendance_required=1)
		with self.assertRaises(frappe.ValidationError):
			self._work()
		attendance.mark([self.emps[0].name], d, "Absent")
		with self.assertRaises(frappe.ValidationError):
			self._work()
		attendance.mark([self.emps[0].name], d, "Half Day")
		self._work()
		self.assertEqual(attendance.day_status(self.emps[0].name, d), "Half Day")
		self.assertIsNone(attendance.day_status(self.emps[1].name, d))
		# HRMS source reads Attendance only: Production marks are ignored
		_set(attendance_source="HRMS Attendance")
		self.assertIsNone(attendance.day_status(self.emps[0].name, d))
		_set(attendance_source="Both")
		self.assertEqual(attendance.day_status(self.emps[0].name, d), "Half Day")

	def test_attendance_unique_and_bulk(self):
		d = today()
		names = attendance.mark([e.name for e in self.emps], d, "Present")
		self.assertEqual(len(names), 3)
		again = attendance.mark([self.emps[0].name], d, "Off")
		self.assertEqual(again, [names[0]])
		self.assertEqual(frappe.db.get_value("Casual Labour Attendance", names[0], "status"), "Off")
		with self.assertRaises(frappe.ValidationError):
			_make("Casual Labour Attendance", employee=self.emps[0].name, date=d)
		self.assertEqual(frappe.db.get_value("Casual Labour Attendance", names[0], "marked_by"), frappe.session.user)
		self.assertEqual(len(api.attendance_day(d)["rows"]), 3)

	def test_existing_flows_still_record(self):
		# unplanned work and a planned task's tick-off pass the guards
		names = work.record_unplanned_work(self.unit.name, self.op.name, [{"employee": self.emps[0].name, "qty": 2}], today())
		self.assertEqual(len(names), 1)

	def test_modes(self):
		self.assertFalse(labour.wm_active() and not labour.wm_installed())
		_set(labour_mode="Built-in only")
		self.assertFalse(labour.wm_active())
		self.assertEqual(api.labour_mode_status()["mode"], "Built-in only")

	# -- pay runs ------------------------------------------------------------

	def _run(self, farm=True):
		d = today()
		doc = frappe.new_doc("Casual Labour Pay Run")
		doc.update({"company": self.company, "from_date": add_days(d, -6), "to_date": d,
			"farm": self.farm.name if farm else None})
		payrun.fill(doc)
		doc.insert()
		return doc

	def test_default_period(self):
		_set(pay_period="Weekly", pay_week_starts_on="Monday")
		self.assertEqual([str(x) for x in payrun.default_period("2026-11-18")], ["2026-11-16", "2026-11-22"])
		_set(pay_week_starts_on="Saturday")
		self.assertEqual([str(x) for x in payrun.default_period("2026-11-18")], ["2026-11-14", "2026-11-20"])
		_set(pay_period="Monthly")
		self.assertEqual([str(x) for x in payrun.default_period("2026-11-18")], ["2026-11-01", "2026-11-30"])
		_set(pay_period="Fortnightly", pay_week_starts_on="Monday")
		a, b = payrun.default_period("2026-11-18")
		self.assertEqual((b - a).days, 13)

	def test_pay_run_flow(self):
		d = today()
		ws = [self._work(0, day=d), self._work(0, day=add_days(d, -1), qty=2), self._work(1, day=d, qty=1)]
		pending = self._work(2, day=d)  # still a draft: not in the run
		for w in ws:
			w.submit()
		run = self._run()
		self.assertEqual((run.total_people, run.total_amount), (2, 320))
		first = next(ln for ln in run.lines if ln.employee == self.emps[0].name)
		self.assertEqual((first.days, first.entries, first.qty, first.amount), (2, 2, 7, 280))
		self.assertEqual(run.status, "Draft")
		# another farm's filter finds nothing
		other = frappe.new_doc("Casual Labour Pay Run")
		other.update({"company": self.company, "from_date": add_days(d, -6), "to_date": d,
			"farm": _make("Farm", farm_name="LP Farm 2", company=self.company, abbreviation="LP2",
				farm_type=[{"farm_type": "Has Blocks"}]).name})
		self.assertEqual(len(payrun.fill(other).lines), 0)
		frappe.delete_doc("Farm", other.farm, force=True)

		run.submit()
		self.assertTrue(run.name.startswith("PAY-"))
		self.assertEqual(frappe.db.get_value("Casual Labour Pay Run", run.name, "status"), "Approved")
		self.assertEqual(frappe.db.get_value("Casual Labour Work", ws[0].name, "pay_run"), run.name)
		self.assertFalse(frappe.db.get_value("Casual Labour Work", pending.name, "pay_run"))
		# work in a run cannot be cancelled, and is not pulled into a second run
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc("Casual Labour Work", ws[0].name).cancel()
		self.assertEqual(len(payrun.fill(frappe.get_doc({**run.as_dict(), "name": None, "lines": []})).lines), 0)
		# csv
		rows = list(csv.reader(io.StringIO(payrun.export_csv(run.name))))
		self.assertEqual(rows[0], ["employee", "name", "days", "entries", "qty", "amount"])
		self.assertEqual(len(rows), 3)

		payrun.mark_paid(run.name, "MPESA-1", d)
		run.reload()
		self.assertEqual((run.status, run.payment_reference), ("Paid", "MPESA-1"))
		w = frappe.get_doc("Casual Labour Work", ws[0].name)
		self.assertEqual((w.paid, str(w.paid_on), w.payroll_reference), ("Paid", d, "MPESA-1"))
		with self.assertRaises(frappe.ValidationError):
			run.cancel()

	def test_cancel_releases(self):
		w = self._work()
		w.submit()
		run = self._run()
		run.submit()
		run.reload().cancel()
		self.assertEqual(frappe.db.get_value("Casual Labour Pay Run", run.name, "status"), "Cancelled")
		self.assertFalse(frappe.db.get_value("Casual Labour Work", w.name, "pay_run"))
		frappe.get_doc("Casual Labour Work", w.name).cancel()  # free again
		# an empty run cannot be approved
		with self.assertRaises(frappe.ValidationError):
			self._run().submit()

	def test_api_pay_run_and_permissions(self):
		w = self._work()
		w.submit()
		d = today()
		res = api.new_pay_run(add_days(d, -6), d, self.farm.name)
		self.assertEqual(res["total_people"], 1)
		self.assertEqual(res["lines"][0]["work"], [w.name])
		self.assertEqual(api.approve_pay_run(res["name"])["status"], "Approved")
		self.assertEqual(api.mark_pay_run_paid(res["name"], "REF")["status"], "Paid")
		self.assertIn("csv", api.pay_run_csv(res["name"]))
		frappe.db.commit()
		self.assertIn("error", api.cancel_pay_run(res["name"]))
		self.assertEqual(api.list_pay_runs()["runs"][0]["name"], res["name"])
		# settings: only labour keys, managers only
		self.assertIn("error", api.save_labour_settings({"company": "x"}))
		self.assertEqual(api.save_labour_settings({"pay_day": "Thursday"})["pay_day"], "Thursday")
		if not frappe.db.exists("User", "lp_viewer@example.com"):
			_make("User", email="lp_viewer@example.com", first_name="Viewer", send_welcome_email=0,
				roles=[{"role": "Production Viewer"}])
		frappe.set_user("lp_viewer@example.com")
		self.assertIn("error", api.list_pay_runs())
		self.assertIn("error", api.save_labour_settings({"pay_day": "Friday"}))
		self.assertIn("error", api.new_pay_run())
		self.assertNotIn("daily_wage", api.get_labour_settings())

	def test_api_rates(self):
		d = today()
		r = api.save_rate(self.op.name, add_days(d, -3), None, 60, None, "note")
		self.assertEqual(api.list_rates(self.op.name)["rates"][0]["rate"], 60)
		self.assertIn("error", api.save_rate(self.op.name, add_days(d, -1), None, 61))  # overlap
		self.assertEqual(api.delete_rate(r["name"]), {"deleted": r["name"]})
