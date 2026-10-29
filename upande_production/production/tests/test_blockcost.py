import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import today

from upande_production.api import blockcost as api
from upande_production.production.logic import blockcost as B
from upande_production.production.logic.harvest import new_warehouse


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


class TestBlockCost(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		cls.abbr = frappe.db.get_value("Company", cls.company, "abbr")
		for uom in ("Kg", "Litre"):
			if not frappe.db.exists("UOM", uom):
				_make("UOM", uom_name=uom)
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		if not frappe.db.exists("Item Group", "All Item Groups"):
			_make("Item Group", item_group_name="All Item Groups", is_group=1)
		cls.farm = _make("Farm", farm_name="BC Farm", company=cls.company, abbreviation="BCF",
			farm_type=[{"farm_type": "Has Blocks"}])
		cls.crop = _make("Production Crop", crop_name="BC Crop", crop_key="bc-crop", unit_label="Block", yield_uom="Kg")
		cls.fert = _make("Item", item_code="BC Fertiliser", item_name="BC Fertiliser", item_group="All Item Groups",
			stock_uom="Kg", is_stock_item=1)
		cls.expense = frappe.get_all("Account", filters={"company": cls.company, "root_type": "Expense", "is_group": 0},
			pluck="name", limit=1)[0]
		cls.wh = [cls._wh(n) for n in ("BC Store", "BC Other Store")]
		cls.n = 0

	@classmethod
	def _wh(cls, name):
		return new_warehouse(name, cls.company, farm=cls.farm.name)

	def _unit(self, name, **kw):
		return _make("Production Unit", unit_name=name, crop=self.crop.name, farm=self.farm.name,
			unit_type="Orchard Block", company=self.company, area_ha=kw.pop("area_ha", 2), **kw)

	def _issue(self, unit, qty, amount, entry_type="Material Issue", d=None, receipt=False):
		type(self).n += 1
		name = f"BC-SE-{self.n:04d}"
		cc = frappe.db.get_value("Production Unit", unit, "cost_center")
		frappe.get_doc({"doctype": "Stock Entry", "name": name, "stock_entry_type": entry_type,
			"purpose": {"Material Transfer": "Material Transfer", "Chemical Mixing": "Repack"}.get(entry_type, "Material Issue"),
			"company": self.company,
			"docstatus": 1, "posting_date": d or today()}).db_insert()
		frappe.get_doc({"doctype": "Stock Entry Detail", "name": f"{name}-1", "parent": name, "parenttype": "Stock Entry",
			"parentfield": "items", "item_code": self.fert.name, "qty": qty, "transfer_qty": qty, "stock_uom": "Kg", "uom": "Kg",
			"amount": amount, "cost_center": cc, "s_warehouse": None if receipt else self.wh[0],
			"t_warehouse": self.wh[0] if receipt else None}).db_insert()
		return name

	def _gl(self, unit, amount, voucher_type="Journal Entry", voucher_no="BC-JV-1", d=None):
		cc = frappe.db.get_value("Production Unit", unit, "cost_center")
		frappe.get_doc({"doctype": "GL Entry", "posting_date": d or today(), "account": self.expense, "cost_center": cc,
			"debit": amount, "debit_in_account_currency": amount, "company": self.company,
			"voucher_type": voucher_type, "voucher_no": voucher_no, "is_cancelled": 0,
			"fiscal_year": frappe.db.get_value("Fiscal Year", {}, "name")}).db_insert()

	def test_links_flags_name_mismatch(self):
		cc_name = f"BC Match - {self.abbr}"
		u1 = self._unit("BC Match")
		u1.db_set("warehouse", self.wh[0])  # a warehouse named differently from the cost centre
		u2 = self._unit("BC Missing")
		u3 = self._unit("BC Fine")
		frappe.db.set_value("Production Unit", u3.name, "warehouse", u3.cost_center)
		rows = {r["unit"]: r for r in B.links(self.crop.name)}
		self.assertEqual(rows[u3.name]["ok"], True)
		self.assertEqual(rows[u3.name]["problems"], [])
		self.assertFalse(rows[u1.name]["ok"])
		self.assertEqual(rows[u1.name]["cost_center"], cc_name)
		self.assertIn("differ", rows[u1.name]["problems"][0])
		self.assertEqual(rows[u2.name]["problems"], ["No warehouse"])
		res = frappe.call("upande_production.api.production.block_links", crop=self.crop.name)
		self.assertTrue({u1.name, u2.name, u3.name} <= {r["unit"] for r in res["rows"]})

	def test_erp_budget_sums_cost_center(self):
		u = self._unit("BC Budget")
		other = self._unit("BC Budget Other")
		fy = frappe.db.get_value("Fiscal Year", {"year_start_date": ("<=", today()), "year_end_date": (">=", today())}, "name")
		if not fy:
			self.skipTest("no current fiscal year")
		accounts = frappe.get_all("Account", filters={"company": self.company, "root_type": "Expense", "is_group": 0},
			pluck="name", limit=2)
		for acc, amount, cc in ((accounts[0], 1000, u), (accounts[-1], 500, u), (accounts[0], 70, other)):
			b = frappe.get_doc({"doctype": "Budget", "budget_against": "Cost Center", "company": self.company,
				"cost_center": cc.cost_center, "account": acc, "budget_amount": amount, "from_fiscal_year": fy,
				"to_fiscal_year": fy, "applicable_on_booking_actual_expenses": 1})
			b.insert()
			b.submit()
		if accounts[0] == accounts[-1]:  # one account only: the second budget was a duplicate-free no-op
			self.skipTest("needs two expense accounts")
		self.assertEqual(B.erp_budget(u.cost_center), 1500)
		self.assertEqual(B.erp_budget(u.cost_center, fy), 1500)
		self.assertEqual(B.erp_budget(other.cost_center), 70)
		self.assertEqual(B.erp_budget(None), 0)
		from upande_production.production.logic import establishment
		by_unit = {r["unit"]: r for r in establishment.list_costs(self.crop.name)["by_unit"]}
		self.assertEqual(by_unit[u.name]["erp_budget"], 1500)
		self.assertEqual(B.erp_budget("No such cc"), 0)

	def test_breakdown_inputs_from_issues(self):
		u = self._unit("BC Inputs", area_ha=4)
		self._issue(u.name, 100, 5000)
		self._issue(u.name, 60, 3000)
		self._issue(u.name, 10, 999, entry_type="Material Transfer")  # not an issue: not counted
		self._issue(u.name, 30, 888, entry_type="Chemical Mixing")    # repack consumption: counted at the mix only
		self._gl(u.name, 250)                                         # other expense, a journal
		self._gl(u.name, 8000, "Stock Entry", "BC-SE-0001")           # stock posting of the issue: not "other"
		res = B.breakdown(u.name, None, None, True)
		self.assertEqual(res["unit"], u.name)
		self.assertEqual(res["area_ha"], 4)
		row = res["inputs"][0]
		self.assertEqual((row["item_code"], row["qty"], row["uom"], row["amount"], row["per_ha"]),
			(self.fert.name, 160, "Kg", 8000, 40))
		self.assertEqual(row["item_group"], "All Item Groups")
		self.assertEqual(res["other"], [{"account": self.expense, "amount": 250}])
		self.assertEqual(res["totals"]["inputs"], 8000)
		self.assertEqual(res["totals"]["other"], 250)
		self.assertEqual(res["totals"]["total"], 8250)
		self.assertEqual(res["totals"]["per_ha"], 2062.5)
		self.assertEqual(set(res["budget"]), {"erp_budget", "actual_this_fy"})

	def test_breakdown_labour_and_pay_hidden(self):
		u = self._unit("BC Labour")
		emp = _make("Employee", first_name="BCWorker", gender="Male", date_of_birth="1990-01-01",
			date_of_joining="2020-01-01", company=self.company)
		op = _make("Production Operation", crop=self.crop.name, operation_name="BC Weeding", category="Other", work_uom="Kg")
		frappe.get_doc({"doctype": "Value Adder Work", "name": "BC-VAW-1", "work_date": today(), "employee": emp.name,
			"unit": u.name, "operation": op.name, "qty": 3, "uom": "Kg", "pay_value": 300, "docstatus": 1}).db_insert()
		res = B.breakdown(u.name, None, None, True)
		self.assertEqual(res["labour"], [{"operation": op.name, "operation_name": "BC Weeding",
			"qty_by_uom": [{"uom": "Kg", "qty": 3}], "workers": 1, "pay": 300}])
		self.assertEqual(res["totals"]["labour"], 300)
		hidden = B.breakdown(u.name, None, None, False)
		self.assertIsNone(hidden["labour"][0]["pay"])
		self.assertEqual((hidden["totals"]["labour"], hidden["totals"]["total"], hidden["totals"]["per_ha"]), (None, None, None))

	def test_breakdown_excludes_harvesting_entries(self):
		u = self._unit("BC Harvest")
		self._issue(u.name, 20, 400)
		self._issue(u.name, 500, 9000, entry_type="Harvesting")
		self._issue(u.name, 500, 9000, entry_type="Harvesting", receipt=True)
		res = B.breakdown(u.name, None, None, True)
		self.assertEqual([r["amount"] for r in res["inputs"]], [400])

	def test_breakdown_period_and_api(self):
		u = self._unit("BC Period")
		self._issue(u.name, 5, 50, d="2025-01-10")
		self._issue(u.name, 7, 70, d="2025-03-10")
		res = frappe.call("upande_production.api.blockcost.block_breakdown", unit=u.name,
			from_date="2025-03-01", to_date="2025-03-31")
		self.assertEqual([r["amount"] for r in res["inputs"]], [70])
		with self.assertRaises(frappe.ValidationError):
			B.breakdown("Nope", None, None, True)

	def test_blockcosts_table_ignores_harvesting_receipt(self):
		from upande_production.production.logic import analytics

		u = self._unit("BC Table")
		issue = self._issue(u.name, 20, 400)
		self._gl(u.name, 400, "Stock Entry", issue)
		self._gl(u.name, 250)
		harvest = self._issue(u.name, 500, 9000, entry_type="Harvesting", receipt=True)
		self._gl(u.name, -9000, "Stock Entry", harvest)  # the receipt credits the expense account
		row = next(r for r in analytics.block_costs(self.crop.name, None, None, True)["rows"] if r["unit"] == u.name)
		res = B.breakdown(u.name, None, None, True)
		self.assertEqual(row["inputs"], res["totals"]["inputs"] + res["totals"]["other"])
		self.assertEqual(row["inputs"], 650)

	def test_scope_dedupes_cost_centres(self):
		g = self._unit("BC Group", is_group=1)
		a = self._unit("BC Shared A", parent_production_unit=g.name)
		b = self._unit("BC Shared B", parent_production_unit=g.name)
		frappe.db.set_value("Production Unit", b.name, "cost_center", a.cost_center)
		_units, ccs, _area = B._scope(g.name)
		self.assertEqual(len(ccs), len(set(ccs)))

	def test_actual_this_fy_includes_labour_and_setup_both_sides(self):
		from upande_production.production.logic import establishment

		fy = B.fiscal_year_range()
		if not fy:
			self.skipTest("no current fiscal year")
		u = self._unit("BC Actual")
		self._gl(u.name, 100)
		self._gl(u.name, 7000, d=fy[1].replace(year=fy[1].year - 1))  # last year: out
		emp = _make("Employee", first_name="BCActual", gender="Male", date_of_birth="1990-01-01",
			date_of_joining="2020-01-01", company=self.company)
		op = _make("Production Operation", crop=self.crop.name, operation_name="BC Actual Op", category="Other", work_uom="Kg")
		frappe.get_doc({"doctype": "Value Adder Work", "name": "BC-VAW-ACT", "work_date": today(), "employee": emp.name,
			"unit": u.name, "operation": op.name, "qty": 1, "uom": "Kg", "pay_value": 300, "docstatus": 1}).db_insert()
		frappe.get_doc({"doctype": "Budget", "budget_against": "Cost Center", "company": self.company,
			"cost_center": u.cost_center, "account": self.expense, "budget_amount": 5000, "from_fiscal_year": fy[0],
			"to_fiscal_year": fy[0], "applicable_on_booking_actual_expenses": 1}).insert().submit()
		self.assertEqual(B.actual_this_fy([u.name], [u.cost_center]), 400)
		self.assertEqual(B.breakdown(u.name, None, None, True)["budget"]["actual_this_fy"], 400)
		row = {r["unit"]: r for r in establishment.list_costs(self.crop.name)["by_unit"]}[u.name]
		self.assertEqual((row["erp_budget"], row["actual_this_fy"]), (5000, 400))
		hidden = {r["unit"]: r for r in establishment.list_costs(self.crop.name, None, False)["by_unit"]}[u.name]
		self.assertIsNone(hidden["actual_this_fy"])
