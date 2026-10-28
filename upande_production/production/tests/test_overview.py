import frappe
from frappe.tests import IntegrationTestCase

from frappe.utils import today

from upande_production.api import overview as api


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


class TestOverviewExtras(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make(
			"Farm", farm_name="OV Farm", company=cls.company, abbreviation="OVF",
			farm_type=[{"farm_type": "Has Blocks"}],
		)
		cls.crop = _make("Production Crop", crop_name="OV Crop", crop_key="ov-crop", unit_label="Block", yield_uom="Kg")

		cls.crop2 = _make("Production Crop", crop_name="OV Crop 2", crop_key="ov-crop2", unit_label="Block", yield_uom="Kg")

	def test_empty_crop(self):
		r = api.get_overview_extras(self.crop.name)
		self.assertEqual(len(r["trend"]), 8)
		self.assertEqual(len(r["forecast_weeks"]), 4)
		self.assertEqual(r["blocks"], [])
		self.assertEqual(r["operations"], [])
		self.assertEqual(r["upcoming"], [])
		self.assertEqual(r["pending_approvals"], 0)

	def test_block_rows_and_pay_hidden(self):
		_make(
			"Production Unit", unit_name="OV B1", crop=self.crop2.name, farm=self.farm.name,
			unit_type="Orchard Block", company=self.company, area_ha=2,
		)
		r = api.get_extras(self.crop2.name, False)
		self.assertEqual([b["unit"] for b in r["blocks"]], ["OV B1"])
		self.assertIsNone(r["trend"][-1]["labour"])
		self.assertIsNone(r["blocks"][0]["last_activity"])

	def _keyed_unit(self, uoms):
		"""A unit with one operation per UOM and one employee per entry, keyed as unplanned work (drafts)."""
		from upande_production.production.logic import work

		unit = _make(
			"Production Unit", unit_name=frappe.generate_hash(length=6), crop=self.crop.name, farm=self.farm.name,
			unit_type="Orchard Block", company=self.company, area_ha=1,
		)
		emps = [
			_make("Employee", first_name=f"OVU{i}", gender="Male", date_of_birth="1990-01-01",
				date_of_joining="2020-01-01", company=self.company)
			for i in range(3)
		]
		ops = []
		for uom in uoms:
			if not frappe.db.exists("UOM", uom):
				_make("UOM", uom_name=uom)
			ops.append(_make("Production Operation", crop=self.crop.name, operation_name=f"OV {uom} {unit.name}",
				category="Field Care", work_uom=uom, default_rate=10))
		return unit, emps, ops, work

	def test_pending_approvals_counts_submissions_not_entries(self):
		from upande_production.api.overview import get_extras

		before = get_extras(self.crop.name, False)["pending_approvals"]
		unit, emps, ops, work = self._keyed_unit(["Kg"])
		# three people on one card: one submission waiting, not three entries
		work.record_unplanned_work(unit.name, ops[0].name, [{"employee": e.name, "qty": 2.1} for e in emps], today())
		self.assertEqual(get_extras(self.crop.name, False)["pending_approvals"], before + 1)

	def test_value_adder_summary_never_adds_across_uoms(self):
		from upande_production.production.logic import analytics

		unit, emps, ops, work = self._keyed_unit(["Hectare", "Tree"])
		d = today()
		work.record_unplanned_work(unit.name, ops[0].name, [{"employee": emps[0].name, "qty": 6, "hours": 2}], d)
		work.record_unplanned_work(unit.name, ops[1].name, [{"employee": emps[0].name, "qty": 309, "hours": 3}], d)
		for n in frappe.get_all("Value Adder Work", filters={"unit": unit.name}, pluck="name"):
			frappe.get_doc("Value Adder Work", n).submit()
		res = analytics.value_adder_summary(self.crop.name, d, d, "unit", True)
		row = next(r for r in res["rows"] if r["key"] == unit.name)
		self.assertNotIn("qty", row)
		self.assertEqual(row["qty_by_uom"], [{"uom": "Tree", "qty": 309.0}, {"uom": "Hectare", "qty": 6.0}])
		self.assertEqual(row["hours"], 5.0)
		self.assertIn({"uom": "Tree", "qty": 309.0}, res["total_qty_by_uom"])
		detail = api.get_value_adder_detail_data(self.crop.name, emps[0].name, d, d, True)
		self.assertEqual(len(detail["by_day"]), 1)
		self.assertEqual({u["uom"] for u in detail["by_day"][0]["qty_by_uom"]}, {"Tree", "Hectare"})

	def test_value_adder_detail_empty(self):
		emp = _make(
			"Employee", first_name="OVEmp", gender="Male", date_of_birth="1990-01-01",
			date_of_joining="2020-01-01", company=self.company,
		)
		r = api.get_value_adder_detail_data(self.crop.name, emp.name, None, None, False)
		self.assertEqual(r["by_day"], [])
		self.assertEqual(r["recent"], [])
		self.assertEqual(r["pending_entries"], 0)

	def test_deviations_count_plan_tasks_once_not_unplanned_work(self):
		"""Approved unplanned work (one VAW row per person) is output, not a deviation: the Overview
		tile, the recent list and the deviations endpoint count the same plan-task deviations."""
		from datetime import timedelta

		from frappe.utils import getdate

		from upande_production.api import production as prod
		from upande_production.production.logic import analytics

		# a crop of its own so the shared empty-crop tests above never see this unit
		self.crop = _make("Production Crop", crop_name="OV Dev Crop", crop_key="ov-dev", unit_label="Block", yield_uom="Kg")
		unit, emps, ops, work = self._keyed_unit(["Kg"])
		t = getdate(today())
		window = (t - timedelta(days=28), t)
		before = len(analytics.deviations(self.crop.name, *window)["rows"])
		names = work.record_unplanned_work(
			unit.name, ops[0].name, [{"employee": e.name, "qty": 2.1} for e in emps], today()
		)
		names = names["work"] if isinstance(names, dict) else names
		for n in names:  # approved and submitted, so they would show up as "Unplanned" rows
			frappe.db.set_value("Value Adder Work", n, {"docstatus": 1, "approval_status": "Approved"})
		self.assertGreaterEqual(len(names), 3)

		rows = analytics.deviations(self.crop.name, *window)["rows"]
		self.assertEqual(len(rows), before)
		self.assertNotIn("Unplanned", {r["kind"] for r in rows})
		self.assertEqual(prod.deviations(self.crop.name, *window)["rows"], rows)
		self.assertEqual(analytics.overview(self.crop.name, False)["tiles"]["deviations"], len(rows))
