import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, today

from upande_production.api import production as api
from upande_production.production.logic import plans, work
from upande_production.production.logic.weeks import iso_of


def _monday(d):
	d = getdate(d)
	return add_days(d, -d.weekday())


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


class TestApi(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make(
			"Farm", farm_name="API Farm", company=cls.company, abbreviation="APF",
			farm_type=[{"farm_type": "Has Blocks"}],
		)
		cls.crop = _make("Production Crop", crop_name="API Crop", crop_key="api-crop", unit_label="Block", yield_uom="Kg")
		cls.empty_crop = _make(
			"Production Crop", crop_name="API Empty Crop", crop_key="api-empty", unit_label="Block", yield_uom="Kg"
		)
		cls.op = _make(
			"Production Operation", crop=cls.crop.name, operation_name="API Weeding",
			category="Field Care", work_uom="Kg", default_rate=40,
		)
		cls.emp = _make(
			"Employee", first_name="APIEmp", gender="Male", date_of_birth="1990-01-01",
			date_of_joining="2020-01-01", company=cls.company,
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _unit(self, name, **kw):
		return _make(
			"Production Unit", unit_name=name, crop=self.crop.name, farm=self.farm.name,
			unit_type=kw.pop("unit_type", "Orchard Block"), company=self.company, **kw,
		)

	def test_endpoints_empty_crop(self):
		c = self.empty_crop.name
		a, b = add_days(today(), -7), today()
		ov = api.get_overview(c)
		self.assertEqual(ov["blocks"], [])
		self.assertEqual(ov["tiles"]["active_cycles"], 0)
		self.assertEqual(api.list_units(c)["units"], [])
		self.assertEqual(api.list_cycles(c)["cycles"], [])
		iso_y, iso_w = iso_of(today())
		pl = api.get_plan(c, self.farm.name, iso_y, iso_w)
		self.assertIsNone(pl["plan"])
		self.assertEqual(pl["tasks"], [])
		self.assertEqual(api.block_costs(c, a, b)["rows"], [])
		self.assertEqual(api.deviations(c, a, b)["rows"], [])
		self.assertEqual(api.value_adder_summary(c, a, b, "employee")["rows"], [])
		self.assertEqual(api.forecast_summary(c, a, b)["weeks"], [])
		for fn in (api.list_samples, api.list_commitments, api.list_operations, api.list_protocols):
			self.assertEqual(fn(c)["rows"], [])
		self.assertEqual(api.list_harvests(c, a, b)["rows"], [])
		self.assertEqual(api.get_bootstrap()["can_see_pay"], True)

	def test_block_costs_rollup_and_zero(self):
		pivot = self._unit("API Pivot", unit_type="Pivot", is_group=1)
		b1 = self._unit("API B1", parent_production_unit=pivot.name, area_ha=2)
		b2 = self._unit("API B2", parent_production_unit=pivot.name, area_ha=2)
		work.record_unplanned_work(b1.name, self.op.name, [{"employee": self.emp.name, "qty": 2.5}], today())
		cc2 = frappe.db.get_value("Production Unit", b2.name, "cost_center")
		abbr = frappe.db.get_value("Company", self.company, "abbr")
		expense = frappe.db.get_value(
			"Account", {"company": self.company, "root_type": "Expense", "is_group": 0, "account_type": ("in", ["", None, "Expense Account"])}
		) or frappe.db.get_value("Account", {"company": self.company, "root_type": "Expense", "is_group": 0})
		cash = f"Cash - {abbr}"
		if not frappe.db.exists("Account", cash):
			cash = frappe.db.get_value("Account", {"company": self.company, "root_type": "Asset", "is_group": 0})
		je = frappe.get_doc({
			"doctype": "Journal Entry", "voucher_type": "Journal Entry", "company": self.company,
			"posting_date": today(),
			"accounts": [
				{"account": expense, "debit_in_account_currency": 50, "cost_center": cc2},
				{"account": cash, "credit_in_account_currency": 50},
			],
		})
		je.insert()
		je.submit()

		res = api.block_costs(self.crop.name, add_days(today(), -7), today())
		rows = {r["unit"]: r for r in res["rows"]}
		self.assertEqual(rows[pivot.name]["labour"], 100)
		self.assertEqual(rows[pivot.name]["inputs"], 50)
		self.assertEqual(rows[pivot.name]["total_cost"], 150)
		self.assertEqual(rows[b1.name]["inputs"], 0)
		self.assertEqual(rows[b1.name]["labour"], 100)
		self.assertEqual(rows[b2.name]["labour"], 0)
		self.assertEqual(rows[b2.name]["inputs"], 50)

	def test_viewer_gets_no_pay(self):
		unit = self._unit("API ViewerUnit")
		iso_y, iso_w = iso_of(today())
		plan = plans.get_or_create_plan(self.crop.name, self.farm.name, iso_y, iso_w)
		plan.append("tasks", {
			"unit": unit.name, "operation": self.op.name, "planned_qty": 10, "uom": "Kg",
			"rate": 40, "due_date": today(), "status": "Open",
		})
		plan.save()
		work.record_task_work(plan.name, plan.tasks[-1].name, "In Progress", [{"employee": self.emp.name, "qty": 4}])
		email = "api_viewer@example.com"
		if not frappe.db.exists("User", email):
			_make("User", email=email, first_name="Viewer", send_welcome_email=0, roles=[{"role": "Production Viewer"}])
		frappe.set_user(email)
		self.assertFalse(api.get_bootstrap()["can_see_pay"])
		res = api.get_plan(self.crop.name, self.farm.name, iso_y, iso_w)
		self.assertNotIn("error", res)
		task = next(t for t in res["tasks"] if t["unit"] == unit.name)
		self.assertTrue(task["work"])
		self.assertIsNone(task["rate"])
		for w in task["work"]:
			self.assertIsNone(w["pay_value"])
		summ = api.value_adder_summary(self.crop.name, add_days(today(), -1), today(), "employee")
		self.assertIsNone(summ["total_pay"])
		self.assertTrue(summ["rows"])
		self.assertIsNone(summ["rows"][0]["pay_value"])
		# writes are refused through the envelope
		self.assertIn("error", api.save_commitment({"crop": self.crop.name}))

	def test_missed_protocol_deviation(self):
		unit = self._unit("API MissedUnit")
		proto = _make(
			"Production Protocol", protocol_name="API Proto", crop=self.crop.name,
			steps=[{"operation": self.op.name, "day_offset": 0, "repeat_count": 1}],
		)
		_make(
			"Production Crop Cycle", unit=unit.name, crop=self.crop.name, start_date=add_days(today(), -3),
			protocol=proto.name, status="Active",
		)
		res = api.deviations(self.crop.name, add_days(today(), -7), today())
		missed = [r for r in res["rows"] if r["kind"] == "Missed" and r["unit"] == unit.name]
		self.assertEqual(len(missed), 1)
		self.assertEqual(str(missed[0]["due_date"]), str(add_days(today(), -3)))
		self.assertEqual(missed[0]["operation_name"], "API Weeding")

	def test_forecast_error_pct(self):
		unit = self._unit("API FcUnit")
		monday = _monday(add_days(today(), -14))
		_make(
			"Production Forecast", unit=unit.name, crop=self.crop.name, uom="Kg", source="Manual",
			weeks=[{"week_start": monday, "expected_qty": 100}],
		)
		_make("Production Harvest", harvest_date=add_days(monday, 2), unit=unit.name, crop=self.crop.name, qty=80, uom="Kg")
		res = api.forecast_summary(self.crop.name, monday, today())
		wk = next(w for w in res["weeks"] if str(w["week_start"]) == str(monday))
		self.assertEqual(wk["forecast"], 100)
		self.assertEqual(wk["actual"], 80)
		self.assertEqual(wk["error_pct"], -20.0)
		u = next(x for x in res["units"] if x["unit"] == unit.name)
		self.assertEqual(u["error_pct"], -20.0)
		self.assertEqual(u["forecast_to_date"], 100)
		self.assertEqual(res["totals"]["error_pct"], -20.0)

	def test_forecast_future_week_ignored_in_error(self):
		unit = self._unit("API FcUnit2")
		monday = _monday(add_days(today(), -14))
		future = _monday(add_days(today(), 14))
		_make(
			"Production Forecast", unit=unit.name, crop=self.crop.name, uom="Kg", source="Manual",
			weeks=[{"week_start": monday, "expected_qty": 100}, {"week_start": future, "expected_qty": 500}],
		)
		_make("Production Harvest", harvest_date=add_days(monday, 2), unit=unit.name, crop=self.crop.name, qty=80, uom="Kg")
		res = api.forecast_summary(self.crop.name, monday, add_days(today(), 21))
		u = next(x for x in res["units"] if x["unit"] == unit.name)
		self.assertEqual(u["forecast"], 100)
		self.assertEqual(u["error_pct"], -20.0)
		fw = next(w for w in res["weeks"] if str(w["week_start"]) == str(future))
		self.assertEqual(fw["forecast"], 500)
		self.assertIsNone(fw["error_pct"])
		t = res["totals"]
		self.assertEqual(t["forecast"] - t["forecast_to_date"], 500)
		self.assertEqual(t["error_pct"], -20.0)
