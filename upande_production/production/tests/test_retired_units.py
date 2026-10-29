"""A Retired unit keeps its records but never shows: pages, maps, APIs and KPIs leave it out."""

import json

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, today

from upande_production.api import breakeven, coverage, establishment, overview
from upande_production.api import production as api
from upande_production.production.logic import analytics, plans, units
from upande_production.production.logic.weeks import iso_of


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


def _monday(d):
	d = getdate(d)
	return add_days(d, -d.weekday())


class TestRetiredUnits(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make("Farm", farm_name="RT Farm", company=cls.company, abbreviation="RTF",
			farm_type=[{"farm_type": "Has Blocks"}])
		cls.crop = _make("Production Crop", crop_name="RT Crop", crop_key="rt-crop", unit_label="Block", yield_uom="Kg")
		cls.op = _make("Field Activity", crop=cls.crop.name, operation_name="RT Weeding", category="Other",
			work_uom="Kg", default_rate=5)
		cls.cap = _make("Field Activity", crop=cls.crop.name, operation_name="RT Clearing", category="Other",
			work_uom="Kg", default_rate=5, activity_type="Capital")
		cls.proto = _make("Production Protocol", protocol_name="RT Proto", version_status="Active", crop=cls.crop.name,
			key_activities=[{"operation": cls.op.name, "week": 1}])
		gj = json.dumps({"type": "Feature", "properties": {}, "geometry": {"type": "Polygon",
			"coordinates": [[[36.7, 0.0], [36.8, 0.0], [36.8, 0.1], [36.7, 0.0]]]}})
		cls.live = cls._unit("RT Live", gj)
		cls.gone = cls._unit("RT Gone", gj)
		for u in (cls.live, cls.gone):
			_make("Production Crop Cycle", unit=u, crop=cls.crop.name, start_date=add_days(today(), -3),
				protocol=cls.proto.name, status="Active")
		frappe.db.set_value("Production Unit", cls.gone, "status", "Retired")
		iso_y, iso_w = iso_of(today())
		cls.y, cls.w = iso_y, iso_w
		plan = plans.get_or_create_plan(cls.crop.name, cls.farm.name, iso_y, iso_w)
		for u in (cls.live, cls.gone):
			plan.append("tasks", {"unit": u, "operation": cls.op.name, "planned_qty": 4, "uom": "Kg", "rate": 5,
				"due_date": today(), "status": "Open"})
		plan.save()
		monday = _monday(today())
		for u in (cls.live, cls.gone):
			_make("Production Harvest", harvest_date=today(), unit=u, crop=cls.crop.name, qty=10, uom="Kg", price_per_uom=2)
			_make("Production Forecast", unit=u, crop=cls.crop.name, uom="Kg", source="Manual", season=today()[:4],
				weeks=[{"week_start": monday, "expected_qty": 50}])

	@classmethod
	def _unit(cls, name, gj):
		return _make("Production Unit", unit_name=name, crop=cls.crop.name, farm=cls.farm.name, unit_type="Orchard Block",
			company=cls.company, area_ha=2, geojson=gj).name

	def test_helpers(self):
		self.assertIn(self.gone, units.retired_units())
		self.assertNotIn(self.live, units.retired_units())
		self.assertEqual(units.not_retired([self.live, self.gone]), [self.live])
		self.assertEqual(units.unit_filter({"a": 1})["a"], 1)
		self.assertEqual(units.unit_filter()["unit"][0], "not in")

	def test_crop_units_cycles_and_overview(self):
		self.assertEqual([u.name for u in analytics.crop_units(self.crop.name)], [self.live])
		self.assertEqual(list(analytics.current_cycles(self.crop.name)), [self.live])
		ov = api.get_overview(self.crop.name)
		self.assertEqual([b["unit"] for b in ov["blocks"]], [self.live])
		self.assertEqual(ov["tiles"]["active_cycles"], 1)
		self.assertEqual(ov["tiles"]["tasks_total"], 1)
		self.assertEqual(ov["tiles"]["harvest_qty_season"], 10)
		ex = overview.get_extras(self.crop.name, True)
		self.assertEqual([b["unit"] for b in ex["blocks"]], [self.live])
		self.assertEqual({u["unit"] for u in ex["upcoming"]}, {self.live})

	def test_units_cycles_plans_samples_harvests(self):
		self.assertEqual([u["name"] for u in api.list_units(self.crop.name)["units"]], [self.live])
		self.assertEqual({c["unit"] for c in api.list_cycles(self.crop.name)["cycles"]}, {self.live})
		self.assertEqual({r["unit"] for r in api.list_harvests(self.crop.name)["rows"]}, {self.live})
		pl = api.get_plan(self.crop.name, self.farm.name, self.y, self.w)
		self.assertEqual({t["unit"] for t in pl["tasks"]}, {self.live})
		self.assertEqual({r["unit"] for r in api.cycle_flags(self.crop.name)["rows"]} - {self.live}, set())

	def test_coverage_map_has_no_retired_unit(self):
		res = coverage.coverage_map(self.crop.name, self.y, self.w)
		self.assertEqual([u["name"] for u in res["units"]], [self.live])
		self.assertEqual(res["totals"]["blocks"], 1)
		self.assertEqual(res["totals"]["planned"], {"Kg": 4.0})

	def test_block_costs_breakeven_forecast(self):
		a, b = add_days(today(), -7), today()
		self.assertEqual([r["unit"] for r in api.block_costs(self.crop.name, a, b)["rows"]], [self.live])
		self.assertEqual([r["unit"] for r in breakeven.crop_breakeven(self.crop.name)["blocks"]], [self.live])
		fc = api.forecast_summary(self.crop.name, _monday(today()), add_days(today(), 14))
		self.assertEqual({u["unit"] for u in fc["units"]}, {self.live})
		self.assertEqual(fc["totals"]["actual"], 10)
		self.assertEqual([r["unit"] for r in api.block_links(self.crop.name)["rows"]], [self.live])

	def test_plan_generation_skips_retired(self):
		plan = plans.get_or_create_plan(self.crop.name, self.farm.name, self.y, self.w)
		plans.generate_week(plan.name)
		plan.reload()
		self.assertTrue(all(t.unit == self.live for t in plan.tasks if t.protocol_ref))

	def test_setup_costs_leave_out_retired(self):
		cost = frappe.get_doc({"doctype": "Block Establishment Cost", "crop": self.crop.name, "farm": self.farm.name,
			"posting_date": today(), "operation": self.cap.name, "amount": 100, "split_method": "By area",
			"blocks": [{"unit": self.live}, {"unit": self.gone}]})
		cost.insert()
		cost.submit()
		only_gone = frappe.get_doc({"doctype": "Block Establishment Cost", "crop": self.crop.name, "farm": self.farm.name,
			"posting_date": today(), "operation": self.cap.name, "amount": 50, "split_method": "By area",
			"blocks": [{"unit": self.gone}]})
		only_gone.insert()
		only_gone.submit()
		res = establishment.list_costs(self.crop.name)
		self.assertNotIn(only_gone.name, [r["name"] for r in res["rows"]])
		mine = next(r for r in res["rows"] if r["name"] == cost.name)
		self.assertEqual([b["unit"] for b in mine["blocks"]], [self.live])
		self.assertEqual({r["unit"] for r in res["by_unit"]}, {self.live})

	def _call(self, fn, payload):
		from types import SimpleNamespace
		from unittest.mock import patch

		frappe.response.pop("data", None)
		with patch.object(frappe.local, "request", SimpleNamespace(get_json=lambda: payload), create=True):
			fn()
		return frappe.response["data"]

	def test_mobile_week_plan_and_units(self):
		from upande_production.mobile import api as mobile

		args = {"crop": self.crop.name, "farm": self.farm.name, "year": self.y, "week": self.w}
		self.assertEqual([r["name"] for r in self._call(mobile.productionListUnits, args)], [self.live])
		self.assertEqual({t["unit"] for t in self._call(mobile.productionGetWeekPlan, args)["tasks"]}, {self.live})
		self.assertEqual([b["unit"] for b in self._call(mobile.productionGetPlanDetail, args)["blocks"]], [self.live])
		counts = self._call(mobile.productionListWeekPlans, args)["plans"]
		self.assertEqual(next(p for p in counts if p["plan_week"] == self.w)["tasks_total"], 1)

	def test_avocado_blocks_of_a_retired_unit_are_hidden(self):
		from upande_production.api import avocadoapi

		code = "RTAVO1"
		frappe.db.set_value("Production Unit", self.gone, "avocado_block_code", code)
		_make("Avocado Yield Block", block_code=code, farm="RT Farm", variety="Hass", status="Active", area_ha=2,
			total_trees=100, live_trees=100, bearing_trees=100, planting_year=2018)
		self.assertIn(code, avocadoapi.retired_codes())
		rows, _src = avocadoapi._read_blocks()
		self.assertNotIn(code, {r["name"] for r in rows})
		self.assertNotIn(code, {b["name"] for b in avocadoapi.get_blocks()})
		frappe.db.set_value("Production Unit", self.gone, "status", "Active")
		rows, _src = avocadoapi._read_blocks()
		self.assertIn(code, {r["name"] for r in rows})
		frappe.db.set_value("Production Unit", self.gone, "status", "Retired")


class TestRetireClosesOpenWork(IntegrationTestCase):
	def test_retiring_closes_cycles_and_skips_tasks(self):
		frappe.set_user("Administrator")
		T = TestRetiredUnits
		T.setUpClass.__func__(T) if not hasattr(T, "live") else None
		crop, farm = T.crop, T.farm
		u = T._unit("RT Retire Me", json.dumps({"type": "Feature", "properties": {}, "geometry": {"type": "Polygon",
			"coordinates": [[[36.7, 0.0], [36.8, 0.0], [36.8, 0.1], [36.7, 0.0]]]}}))
		cyc = _make("Production Crop Cycle", unit=u, crop=crop.name, start_date=add_days(today(), -3),
			protocol=T.proto.name, status="Active")
		plan = plans.get_or_create_plan(crop.name, farm.name, T.y, T.w)
		plan.append("tasks", {"unit": u, "operation": T.op.name, "planned_qty": 4, "uom": "Kg", "rate": 5,
			"due_date": today(), "status": "Open"})
		plan.save()
		doc = frappe.get_doc("Production Unit", u)
		doc.status = "Retired"
		doc.save()
		self.assertEqual(frappe.db.get_value("Production Crop Cycle", cyc.name, "status"), "Closed")
		self.assertFalse(frappe.db.get_value("Production Crop Cycle", cyc.name, "proposed_next_cycle"))
		self.assertFalse(frappe.db.exists("Production Crop Cycle", {"previous_cycle": cyc.name}))
		t = frappe.get_all("Production Plan Task", filters={"unit": u}, fields=["status", "note"])
		self.assertEqual([x.status for x in t], ["Skipped"])
		self.assertIn("unit retired", t[0].note)
		self.assertEqual(units.close_open_work(u), {"cycles": 0, "tasks": 0})  # idempotent


class TestHarvestValue(IntegrationTestCase):
	def test_value_falls_back_to_item_buyer_then_crop_price(self):
		from upande_production.production.logic.harvest import valuation_rate

		frappe.set_user("Administrator")
		crop = _make("Production Crop", crop_name="HV Crop", crop_key="hv-crop", unit_label="Block", yield_uom="Kg")
		self.assertEqual(valuation_rate(None, crop.name), 0)
		frappe.db.set_value("Production Crop", crop.name, "price_per_kg", 7)
		self.assertEqual(valuation_rate(None, crop.name), 7)
		if not frappe.db.exists("Item Group", "All Item Groups"):
			self.skipTest("no item group")
		item = frappe.get_doc({"doctype": "Item", "item_code": "HV Honey", "item_name": "HV Honey",
			"item_group": "All Item Groups", "stock_uom": "Kg", "is_stock_item": 1, "valuation_rate": 12}).insert()
		self.assertEqual(valuation_rate(item.name, crop.name), 12)
		item.db_set("valuation_rate", 0)
		self.assertEqual(valuation_rate(item.name, crop.name), 7)  # crop price is the last fallback
