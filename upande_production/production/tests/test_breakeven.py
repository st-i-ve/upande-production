from datetime import date

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, add_months, flt, today

from upande_production.api import breakeven as api
from upande_production.production.logic import breakeven as B


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


class TestBreakEven(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make("Farm", farm_name="BE Farm", company=cls.company, abbreviation="BEF",
			farm_type=[{"farm_type": "Has Blocks"}])
		cls.crop = _make("Production Crop", crop_name="BE Crop", crop_key="be-crop", unit_label="Block", yield_uom="Kg")
		cls.op = _make("Production Operation", crop=cls.crop.name, operation_name="BE Land Prep",
			category="Other", work_uom="Kg", activity_type="Capital")
		cls.accounts = frappe.get_all("Account", filters={"company": cls.company, "root_type": "Expense", "is_group": 0},
			pluck="name", limit=2)

	def _unit(self, name, **kw):
		return _make("Production Unit", unit_name=name, crop=self.crop.name, farm=self.farm.name,
			unit_type="Orchard Block", company=self.company, area_ha=2, **kw)

	def _gl(self, unit, account, amount, posting_date, voucher_type="Journal Entry", voucher_no="BE-JV-1"):
		cc = frappe.db.get_value("Production Unit", unit, "cost_center")
		frappe.get_doc({"doctype": "GL Entry", "posting_date": posting_date, "account": account, "cost_center": cc,
			"debit": amount, "debit_in_account_currency": amount, "company": self.company,
			"voucher_type": voucher_type, "voucher_no": voucher_no, "is_cancelled": 0,
			"fiscal_year": frappe.db.get_value("Fiscal Year", {}, "name")}).db_insert()

	def _cost(self, unit, amount, d):
		doc = frappe.get_doc({"doctype": "Block Establishment Cost", "crop": self.crop.name, "farm": self.farm.name,
			"posting_date": d, "operation": self.op.name, "amount": amount, "split_method": "By area",
			"blocks": [{"unit": unit}]})
		doc.insert()
		doc.submit()

	def _harvest(self, unit, qty, d, price=0):
		frappe.get_doc({"doctype": "Production Harvest", "harvest_date": d, "unit": unit, "crop": self.crop.name,
			"qty": qty, "uom": "Kg", "price_per_uom": price}).insert()

	@staticmethod
	def _set_capital(accounts):
		settings = frappe.get_single("Production Settings")
		settings.set("capital_accounts", [{"account": a} for a in accounts])
		settings.save()

	# pure
	def test_series_break_even_date(self):
		s = B.series([(date(2026, 1, 5), 100)], [(date(2026, 2, 10), 60), (date(2026, 3, 3), 50)])
		self.assertEqual(s["break_even_date"], date(2026, 3, 31))
		self.assertEqual(s["invested"], 100)
		self.assertEqual(s["recovered"], 110)
		self.assertEqual(s["balance"], 10)
		self.assertEqual(s["pct_recovered"], 110)
		self.assertEqual(s["points"][0], {"date": date(2026, 1, 31), "cost": 100, "value": 0})

	def test_series_never_breaks_even(self):
		s = B.series([(date(2026, 1, 5), 100)], [(date(2026, 2, 10), 20)])
		self.assertIsNone(s["break_even_date"])
		self.assertEqual(s["pct_recovered"], 20)

	def test_project_months(self):
		self.assertEqual(B.project(-1000, 300, date(2026, 10, 28)), date(2027, 2, 28))
		self.assertIsNone(B.project(-1000, 0))
		self.assertIsNone(B.project(10, 5))

	# db
	def test_breakeven_opening_balance_no_double_count(self):
		u = self._unit("BE Opening")
		_make("Block Opening Balance", unit=u.name, crop=self.crop.name, as_of_date="2026-03-01",
			setup_cost=1000, running_costs_to_date=200, value_recovered_to_date=300)
		self._cost(u.name, 111, "2026-02-01")   # before the opening balance: already inside it
		self._cost(u.name, 40, "2026-04-01")
		self._harvest(u.name, 10, "2026-02-15", price=5)  # before: ignored
		self._harvest(u.name, 10, "2026-05-15", price=5)
		b = B.block(u.name, True)
		self.assertEqual(b["invested"], 1240)
		self.assertEqual(b["recovered"], 350)

	def test_harvesting_stock_entry_gl_excluded(self):
		u = self._unit("BE Harvesting")
		se = frappe.get_doc({"doctype": "Stock Entry", "name": "BE-SE-HARV", "stock_entry_type": "Harvesting",
			"company": self.company})
		se.db_insert()
		self._cost(u.name, 10, "2026-01-01")
		self._gl(u.name, self.accounts[0], 70, "2026-02-01", "Stock Entry", "BE-SE-HARV")
		self._gl(u.name, self.accounts[0], 30, "2026-02-02")
		self.assertEqual(B.block(u.name, True)["invested"], 40)

	def test_capital_account_excluded(self):
		u = self._unit("BE Capital")
		self._cost(u.name, 10, "2026-01-01")
		self._gl(u.name, self.accounts[0], 500, "2026-02-01")
		self._gl(u.name, self.accounts[1], 25, "2026-02-01")
		settings = frappe.get_single("Production Settings")
		before = [r.account for r in settings.capital_accounts]
		self.addCleanup(self._set_capital, before)
		settings.append("capital_accounts", {"account": self.accounts[0]})
		settings.save()
		self.assertEqual(B.block(u.name, True)["invested"], 35)

	def test_unvalued_harvest_uses_unit_value(self):
		u = self._unit("BE Unvalued")
		self._cost(u.name, 10, "2026-01-01")
		item = _make("Item", item_code="BE Fruit", item_name="BE Fruit", item_group="All Item Groups",
			stock_uom="Kg", is_stock_item=1, valuation_rate=4)
		frappe.get_doc({"doctype": "Production Harvest", "harvest_date": "2026-02-01", "unit": u.name,
			"crop": self.crop.name, "item": item.name, "qty": 5, "uom": "Kg"}).insert()
		self.assertEqual(B.block(u.name, True)["recovered"], 20)

	def test_crop_endpoint_shapes(self):
		u = self._unit("BE Shape")
		self._cost(u.name, 100, "2026-01-01")
		self._harvest(u.name, 10, "2026-02-01", price=5)
		out = api.crop_breakeven(self.crop.name, self.farm.name)
		row = next(b for b in out["blocks"] if b["unit"] == u.name)
		self.assertEqual((row["invested"], row["recovered"], row["balance"], row["pct_recovered"]), (100, 50, -50, 50))
		self.assertIn(out["farm"]["projection_basis"], (None, "forecast", "trailing_12m"))
		self.assertTrue(out["farm"]["points"])

	def test_breakeven_hidden_without_pay(self):
		email = "be_viewer@example.com"
		if not frappe.db.exists("User", email):
			_make("User", email=email, first_name="BEViewer", send_welcome_email=0, roles=[{"role": "Production Viewer"}])
		frappe.set_user(email)
		try:
			out = api.crop_breakeven(self.crop.name)
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(out, {"error": "Break-even includes pay; ask a manager."})

	# projection
	def test_projection_ignores_opening_lump_and_establishment(self):
		u = self._unit("BE Recent")
		_make("Block Opening Balance", unit=u.name, crop=self.crop.name, as_of_date=add_days(today(), -30),
			setup_cost=100000, running_costs_to_date=5000, value_recovered_to_date=0)
		self._cost(u.name, 20000, add_days(today(), -5))
		self._harvest(u.name, 100, add_days(today(), -10), price=1000)
		b = B.block(u.name, True)
		self.assertLess(b["balance"], 0)
		self.assertIsNotNone(b["projected_date"])

	def test_projection_window_is_exactly_12_months(self):
		since = add_months(frappe.utils.getdate(today()), -12)
		inside = [(add_days(since, 1), 1200)]
		outside = [(add_days(since, -1), 12000)]
		d, _y, basis = B._projection([], self.crop.name, [], inside, -1000)
		self.assertEqual(basis, "trailing_12m")
		self.assertEqual(d, B.project(-1000, 100))
		self.assertEqual(B._projection([], self.crop.name, [], outside, -1000), (None, None, None))

	def test_forecast_uses_one_forecast_per_unit(self):
		u = self._unit("BE Forecast")
		self._harvest(u.name, 1, add_days(today(), -100), price=10)
		week = add_days(today(), 14)
		for qty in (100, 300):
			_make("Production Forecast", unit=u.name, crop=self.crop.name, uom="Kg", source="Manual",
				weeks=[{"week_start": week, "expected_qty": qty}])
		# latest forecast (300 kg at 10) is the one that counts, not 400 kg
		self.assertEqual(B._forecast_value([u.name], self.crop.name), 3000)
