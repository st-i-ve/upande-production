import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from upande_production.api import labourers as api
from upande_production.production.logic import labourers, work


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


class TestCasualLabourers(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		for u in ("Kg", "Tree"):
			if not frappe.db.exists("UOM", u):
				_make("UOM", uom_name=u)
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make("Farm", farm_name="LB Farm", company=cls.company, abbreviation="LBF",
			farm_type=[{"farm_type": "Has Blocks"}])
		cls.crop = _make("Production Crop", crop_name="LB Crop", crop_key="lb-crop", unit_label="Block", yield_uom="Kg")
		cls.unit = _make("Production Unit", unit_name="LB B1", crop=cls.crop.name, farm=cls.farm.name,
			unit_type="Orchard Block", company=cls.company, area_ha=1)
		cls.op = _make("Field Operation", crop=cls.crop.name, operation_name="LB Prune", category="Pruning",
			work_uom="Tree", default_rate=5, daily_target=60)
		cls.emps = [_make("Employee", first_name=f"LBE{i}", gender="Male", date_of_birth="1990-01-01",
			date_of_joining="2020-01-01", company=cls.company) for i in range(2)]

	def _work(self, emp, qty, day, extra=None):
		names = work.record_unplanned_work(self.unit.name, self.op.name,
			[{"employee": emp.name, "qty": qty, **(extra or {})}], day)
		for n in names:
			frappe.get_doc("Casual Labour Work", n).submit()
		return names

	def test_hours_field_is_gone_and_old_hours_are_ignored(self):
		self.assertFalse(frappe.get_meta("Casual Labour Work").has_field("hours"))
		(n,) = self._work(self.emps[0], 10, today(), {"hours": 7})
		doc = frappe.get_doc("Casual Labour Work", n)
		self.assertEqual(doc.pay_value, 50)  # qty x rate per unit, nothing multiplied by hours
		self.assertEqual(doc.paid, "Unpaid")
		self.assertIsNone(doc.paid_on)

	def test_add_labourers_is_idempotent(self):
		r = api.add_labourers([self.emps[0].name, self.emps[1].name])
		self.assertEqual(len(r["added"]), 2)
		r = api.add_labourers([self.emps[0].name])
		self.assertEqual(r, {"added": [], "skipped": [self.emps[0].name]})
		ids = {p["name"] for p in api.candidate_employees()["people"]}
		self.assertNotIn(self.emps[0].name, ids)
		self.assertTrue(frappe.db.get_value("Casual Labourer", self.emps[0].name, "active"))

	def test_target_resolution_override_beats_default(self):
		api.add_labourers([self.emps[0].name])
		d, o = labourers.operation_defaults([self.op.name]), labourers.person_overrides([self.emps[0].name])
		self.assertEqual(labourers.resolve_target(d, o, self.emps[0].name, self.op.name)[:3], (60, "Tree", False))
		api.save_labourer(self.emps[0].name, targets=[{"operation": self.op.name, "daily_target": 40}])
		o = labourers.person_overrides([self.emps[0].name])
		self.assertEqual(labourers.resolve_target(d, o, self.emps[0].name, self.op.name)[:3], (40, "Tree", True))
		with self.assertRaises(frappe.ValidationError):
			labourers.save_labourer(self.emps[0].name, targets=[{"operation": self.op.name, "daily_target": 0}],
				fields=("targets",))
		with self.assertRaises(frappe.ValidationError):
			labourers.save_labourer(self.emps[0].name, targets=[
				{"operation": self.op.name, "daily_target": 1}, {"operation": self.op.name, "daily_target": 2}],
				fields=("targets",))

	def test_kpis_hit_rate_and_paid(self):
		e = _make("Employee", first_name="LBK", gender="Male", date_of_birth="1990-01-01",
			date_of_joining="2020-01-01", company=self.company)
		api.add_labourers([e.name])
		d0 = today()
		self._work(e, 70, add_days(d0, -2))  # met (>= 60)
		self._work(e, 30, add_days(d0, -1))  # not met
		(n3,) = self._work(e, 60, d0)  # met exactly
		frappe.db.set_value("Casual Labour Work", n3, {"paid": "Paid", "paid_on": d0, "payroll_reference": "PAY-1"})
		res = api.labourer_detail(self.crop.name, e.name, add_days(d0, -5), d0)
		k = res["kpis"]
		self.assertEqual((k["days_worked"], k["target_days"], k["met_days"]), (3, 3, 2))
		self.assertEqual(k["hit_rate"], 66.7)
		self.assertEqual(k["pay_value"], 800.0)  # 160 trees x 5: targets never change pay
		self.assertEqual((k["paid_value"], k["unpaid_value"]), (300.0, 500.0))
		op = res["by_operation"][0]
		self.assertEqual((op["qty"], op["days"], op["target"], op["avg_per_day"]), (160.0, 3, 60.0, 53.33))
		self.assertEqual(op["avg_vs_target"], 88.9)
		self.assertEqual([r["met"] for r in res["daily"]], [True, False, True])
		self.assertEqual({r["payroll_reference"] for r in res["recent"]}, {None, "PAY-1"})
		by_day = {str(r["work_date"]): r for r in res["recent"]}
		self.assertEqual((by_day[str(d0)]["target"], by_day[str(d0)]["target_met"]), (60, True))
		self.assertEqual((by_day[str(add_days(d0, -1))]["day_qty"], by_day[str(add_days(d0, -1))]["target_met"]), (30, False))
		lst = api.list_labourers(self.crop.name, add_days(d0, -5), d0)
		row = next(r for r in lst["rows"] if r["employee"] == e.name)
		self.assertEqual((row["days_worked"], row["hit_rate"], row["unpaid_value"]), (3, 66.7, 500.0))
		self.assertGreaterEqual(lst["totals"]["unpaid_value"], 500.0)

	def test_work_records_show_target_and_met(self):
		e = self.emps[1]
		names = self._work(e, 20, today()) + work.record_unplanned_work(
			self.unit.name, self.op.name, [{"employee": e.name, "qty": 45}], today())
		rows = frappe.get_all("Casual Labour Work", filters={"name": ("in", names)},
			fields=["employee", "operation", "work_date", "qty", "uom"])
		labourers.annotate_work(rows)
		self.assertTrue(all(r["target"] == 60 and r["target_met"] is False and r["day_qty"] == 65 or r["target_met"] for r in rows))

	def test_remove_with_history_deactivates(self):
		api.add_labourers([self.emps[1].name])
		self._work(self.emps[1], 5, today())
		self.assertEqual(api.remove_labourer(self.emps[1].name), {"removed": False, "deactivated": True})
		self.assertFalse(frappe.db.get_value("Casual Labourer", self.emps[1].name, "active"))
