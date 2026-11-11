from unittest import mock

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, flt, today

from upande_production.api import silage as api
from upande_production.production.logic import harvest as H
from upande_production.production.logic import silage as S
from upande_production.production.setup.silage_fields import ensure_silage_fields


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


class TestSilage(IntegrationTestCase):
	"""Silage cycle: inputs from stock, machine diesel, labour -> pit receipt at cost per kg. Rolls back."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		ensure_silage_fields()
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		for uom in ("Kg", "Nos"):
			if not frappe.db.exists("UOM", uom):
				_make("UOM", uom_name=uom)
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		if not frappe.db.exists("Item Group", "All Item Groups"):
			_make("Item Group", item_group_name="All Item Groups", is_group=1)
		cls.farm = _make("Farm", farm_name="SL Farm", company=cls.company, abbreviation="SLF",
			farm_type=[{"farm_type": "Has Blocks"}])
		cls.crop = _make("Production Crop", crop_name="SL Maize", crop_key="sl-maize", unit_label="Field",
			yield_uom="Kg", enabled=1, uses_crop_cycles=1, grown_for_silage=1)
		cls.unit = _make("Production Unit", unit_name="SL Field 1", crop=cls.crop.name, farm=cls.farm.name,
			unit_type="Other", company=cls.company)
		cls.store = H.new_warehouse("SL Input Store", cls.company, farm=cls.farm.name)
		cls.pit = H.new_warehouse("SL Pit 1", cls.company, farm=cls.farm.name)
		cls.seed = _make("Item", item_code="SL Seed", item_name="SL Seed", item_group="All Item Groups",
			stock_uom="Kg", is_stock_item=1, valuation_rate=50)
		cls.silage_item = _make("Item", item_code="SL Maize Silage", item_name="SL Maize Silage",
			item_group="All Item Groups", stock_uom="Kg", is_stock_item=1)
		receipt = frappe.get_doc({"doctype": "Stock Entry", "stock_entry_type": "Material Receipt",
			"purpose": "Material Receipt", "company": cls.company, "to_warehouse": cls.store,
			"items": [{"item_code": cls.seed.name, "qty": 500, "t_warehouse": cls.store, "basic_rate": 50}]})
		receipt.insert()
		receipt.submit()
		frappe.db.set_single_value("Production Settings", {"silage_input_warehouse": cls.store,
			"silage_pit_warehouse": cls.pit, "silage_labour_day_rate": 400})

	def setUp(self):
		# `run` rolls back on a refusal; keep the rest of the test's uncommitted rows (rolled back at class end).
		p = mock.patch.object(frappe.db, "rollback")
		p.start()
		self.addCleanup(p.stop)

	def new_cycle(self, **kw):
		return _make("Silage Cycle", crop="Maize", production_unit=self.unit.name, start_date=add_days(today(), -30),
			silage_item=self.silage_item.name, **kw)

	def test_defaults_from_field_and_settings(self):
		c = self.new_cycle()
		self.assertEqual(c.production_crop, self.crop.name)
		self.assertEqual(c.company, self.company)
		self.assertEqual(c.pit_warehouse, self.pit)
		self.assertEqual(c.status, "Planned")
		self.assertTrue(c.title.startswith("Maize silage - SL Field 1"))

	def test_activity_labour_uses_settings_day_rate(self):
		c = self.new_cycle(activities=[
			{"date": add_days(today(), -20), "activity": "Planting", "workers": 6},
			{"date": add_days(today(), -10), "activity": "Weeding", "workers": 2, "day_rate": 350},
			{"date": add_days(today(), -5), "activity": "Other", "labour_cost": 1200},
		])
		self.assertEqual([r.labour_cost for r in c.activities], [2400, 700, 1200])
		self.assertEqual(c.activities[0].day_rate, 400)
		self.assertEqual(c.labour_cost, 4300)
		self.assertEqual(c.total_cost, 4300)

	def test_activity_before_start_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self.new_cycle(activities=[{"date": add_days(today(), -60), "activity": "Land prep", "workers": 1}])

	def test_inputs_issue_and_close_receives_silage_at_cost_per_kg(self):
		c = self.new_cycle(activities=[{"date": add_days(today(), -20), "activity": "Planting", "workers": 5}])
		se = S.issue_inputs(c.name, [{"item_code": self.seed.name, "qty": 40}])
		self.assertEqual((se.docstatus, se.purpose, se.production_silage_cycle), (1, "Material Issue", c.name))
		rows = S.input_rows(c.name)
		self.assertEqual(len(rows), 1)
		self.assertAlmostEqual(flt(rows[0].amount), 2000)  # 40 kg at 50, from the stock ledger
		c.reload()
		c.save()
		self.assertEqual((c.inputs_cost, c.labour_cost, c.total_cost), (2000, 2000, 4000))

		res = api.close_silage_cycle(name=c.name, ensiled_kg=1000)
		self.assertNotIn("error", res)
		c.reload()
		self.assertEqual((c.docstatus, c.status), (1, "Closed"))
		self.assertAlmostEqual(flt(c.cost_per_kg), 4.0)
		receipt = frappe.get_doc("Stock Entry", c.receipt_stock_entry)
		self.assertEqual((receipt.docstatus, receipt.purpose, receipt.production_silage_cycle), (1, "Material Receipt", c.name))
		self.assertEqual((receipt.items[0].item_code, receipt.items[0].qty, receipt.items[0].t_warehouse),
			(self.silage_item.name, 1000, self.pit))
		self.assertAlmostEqual(flt(receipt.items[0].basic_rate), 4.0)
		self.assertAlmostEqual(flt(frappe.db.get_value("Bin", {"item_code": self.silage_item.name, "warehouse": self.pit},
			"valuation_rate")), 4.0)

		# a closed cycle takes no more inputs, and its cost stays frozen
		with self.assertRaises(frappe.ValidationError):
			S.issue_inputs(c.name, [{"item_code": self.seed.name, "qty": 1}])
		summary = S.cycle_summary(c)
		self.assertEqual(summary["cost"]["total"], 4000)
		stock = {(r["item_code"], r["warehouse"]): r for r in S.pit_stock()}
		self.assertEqual(stock[(self.silage_item.name, self.pit)]["qty"], 1000)

		# cancelling the cycle cancels the receipt
		c.cancel()
		self.assertEqual(frappe.db.get_value("Stock Entry", receipt.name, "docstatus"), 2)
		self.assertEqual(frappe.db.get_value("Silage Cycle", c.name, "status"), "Cancelled")

	def test_close_needs_ensiled_kg(self):
		c = self.new_cycle()
		res = api.close_silage_cycle(name=c.name, ensiled_kg=0)
		self.assertIn("error", res)
		self.assertEqual(frappe.db.get_value("Silage Cycle", c.name, "docstatus"), 0)

	def test_tagged_receipt_is_refused(self):
		c = self.new_cycle()
		se = frappe.get_doc({"doctype": "Stock Entry", "stock_entry_type": "Material Receipt", "purpose": "Material Receipt",
			"company": self.company, "to_warehouse": self.store, "production_silage_cycle": c.name,
			"items": [{"item_code": self.seed.name, "qty": 1, "t_warehouse": self.store, "basic_rate": 50}]})
		se.insert()
		with self.assertRaises(frappe.ValidationError):
			se.submit()

	def test_casual_labour_on_the_field_counts(self):
		c = self.new_cycle()
		name = frappe.generate_hash(length=10)
		frappe.db.sql("""insert into `tabCasual Labour Work` (name, docstatus, unit, work_date, pay_value, creation, modified)
			values (%s, 1, %s, %s, 900, now(), now())""", (name, self.unit.name, add_days(today(), -3)))
		# The tests share one field; left behind, this pay lands in every later cycle's total.
		self.addCleanup(frappe.db.delete, "Casual Labour Work", {"name": name})
		c.reload()
		c.save()
		self.assertEqual(c.casual_labour_cost, 900)
		c.include_casual_labour = 0
		c.save()
		self.assertEqual(c.casual_labour_cost, 0)

	def test_allocation_diesel_counts_when_present(self):
		if not S.has_allocations():
			self.skipTest("Production Asset Allocation is not installed on this site")
		c = self.new_cycle()
		for docstatus, cost in ((1, 3320), (0, 999)):  # a draft (open) allocation does not count
			frappe.db.sql("""insert into `tabProduction Asset Allocation` (name, docstatus, reference_doctype, reference_name,
				diesel_cost, diesel_litres, duration_hours, creation, modified) values (%s, %s, 'Silage Cycle', %s, %s, 20, 4, now(), now())""",
				(frappe.generate_hash(length=10), docstatus, c.name, cost))
		c.save()
		self.assertEqual((c.diesel_cost, c.diesel_litres, c.machine_hours), (3320, 20, 4))
		self.assertIn("error", api.close_silage_cycle(name=c.name, ensiled_kg=100))  # the open allocation blocks closing

	def test_api_shapes(self):
		c = self.new_cycle(activities=[{"date": add_days(today(), -20), "activity": "Planting", "workers": 1}])
		res = api.silage_cycles()
		self.assertTrue(res["ok"])
		mine = [r for r in res["cycles"] if r["name"] == c.name][0]
		self.assertEqual(mine["cost"]["labour"], 400)
		self.assertIsNone(mine["cost_per_kg"])  # nothing ensiled yet
		self.assertEqual([k["kind"] for k in mine["by_kind"]], ["inputs", "diesel", "labour", "casual_labour"])
		self.assertIn("error", api.silage_cycles(status="Nope"))
		summary = api.silage_cost_summary(from_date=add_days(today(), -7), to_date=today())
		self.assertTrue(summary["ok"])
		self.assertIn(c.name, [r["name"] for r in summary["cycles"]])
		self.assertIn("cost_per_kg", summary["totals"])
		before = api.silage_cost_summary(from_date=add_days(today(), -400), to_date=add_days(today(), -60))
		self.assertNotIn(c.name, [r["name"] for r in before["cycles"]])
		page = api.silage_page()
		self.assertTrue(page["ok"])
		self.assertIn(self.crop.name, page["options"]["production_crops"])
		self.assertEqual(page["options"]["pit_warehouse"], self.pit)
