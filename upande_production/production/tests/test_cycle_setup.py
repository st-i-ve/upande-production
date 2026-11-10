import base64

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, today

from upande_production.production.logic import cycle_setup, schedule, stages


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


def _stages(*rows):
	return [{"stage": n, "start_day": s, "length_days": ln, "is_harvest": 1 if h else 0} for n, s, ln, h in rows]


class TestCycleSetup(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make("Farm", farm_name="CS Farm", company=cls.company, abbreviation="CSF",
			farm_type=[{"farm_type": "Has Blocks"}])
		cls.crop = _make("Production Crop", crop_name="CS Crop", crop_key="cs-crop", unit_label="Block", yield_uom="Kg")
		cls.item = _make("Item", item_code="CS Hass", item_name="CS Hass", item_group="All Item Groups",
			stock_uom="Kg", is_stock_item=1).name
		cls.hass = _make("Production Variety", variety_name="CS Hass", crop=cls.crop.name, item=cls.item,
			is_flowering=1, stage_anchor="Flowering", harvest_pattern="Interval", harvest_interval_weeks=52,
			lifespan_years=25, flowering_pattern="Interval", flowering_interval_weeks=52, weeks_flowering_to_harvest=36,
			weeks_to_reflower_after_harvest=12, harvest_window_weeks=8, plants_per_ha=156, days_to_first_harvest=250,
			stages=_stages(("Flowering", 0, 30, 0), ("Fruit set", 30, 30, 0), ("Fruit development", 60, 150, 0),
				("Maturity", 210, 30, 0), ("Harvest", 240, 120, 1))).name
		cls.protocol = _make("Production Protocol", protocol_name="CS Proto", crop=cls.crop.name, variety=cls.hass,
			item=cls.item, version_status="Active",
			key_activities=[], cultural_activities=[]).name

	def _unit(self, area=10, trees=1500):
		return _make("Production Unit", unit_name=f"CS B{frappe.generate_hash(length=6)}", unit_type="Orchard Block",
			crop=self.crop.name, farm=self.farm.name, company=self.company, area_ha=area, plant_count=trees)

	def test_new_cycle_defaults_to_block(self):
		u = self._unit()
		r = cycle_setup.create_cycle({"unit": u.name, "variety": self.hass, "start_date": add_days(today(), 10)})
		c = frappe.get_doc("Production Crop Cycle", r["name"])
		self.assertEqual((c.area_ha, c.plant_count, c.status), (10, 1500, "Planned"))
		self.assertFalse(c.existing_cycle)

	def test_trees_default_from_variety_density(self):
		u = self._unit(trees=0)
		c = frappe.get_doc("Production Crop Cycle", cycle_setup.create_cycle(
			{"unit": u.name, "variety": self.hass, "start_date": today()})["name"])
		self.assertEqual(c.plant_count, 1560)

	def test_two_cycles_over_capacity_warn_not_throw(self):
		u = self._unit(area=10, trees=1000)
		cycle_setup.create_cycle({"unit": u.name, "variety": self.hass, "start_date": today(), "area_ha": 6, "plant_count": 600})
		r = cycle_setup.create_cycle({"unit": u.name, "variety": self.hass, "start_date": today(), "area_ha": 6, "plant_count": 600})
		self.assertEqual(len(r["warnings"]), 2)
		self.assertEqual(frappe.db.count("Production Crop Cycle", {"unit": u.name}), 2)

	def test_existing_cycle_stage_and_no_backlog(self):
		u = self._unit()
		planted = add_days(today(), -365 * 6)
		r = cycle_setup.create_cycle({"unit": u.name, "variety": self.hass, "existing": 1, "planting_date": planted,
			"current_stage": "Fruit development", "last_season_yield_kg": 40000, "protocol": self.protocol})
		c = frappe.get_doc("Production Crop Cycle", r["name"])
		self.assertEqual(c.current_stage, "Fruit development")
		self.assertEqual(c.status, "Active")
		self.assertTrue(c.existing_cycle)
		self.assertEqual(getdate(c.schedule_from), getdate(today()))
		self.assertEqual(cycle_setup.tree_age_years(c.planting_date), 6.0)
		self.assertFalse(c.juvenile)
		self.assertEqual(stages.stage_on(c)["stage"], "Fruit development")

	def test_existing_cycle_harvest_stage_is_harvesting(self):
		u = self._unit()
		c = frappe.get_doc("Production Crop Cycle", cycle_setup.create_cycle({"unit": u.name, "variety": self.hass,
			"existing": 1, "planting_date": add_days(today(), -2000), "current_stage": "Harvest",
			"last_flowering_date": add_days(today(), -260)})["name"])
		self.assertEqual(c.status, "Harvesting")
		self.assertEqual(c.current_stage, "Harvest")
		self.assertEqual(getdate(c.actual_flowering_date), getdate(add_days(today(), -260)))

	def test_existing_cycle_stage_off_the_flowering_date_gets_an_actual(self):
		u = self._unit()
		c = frappe.get_doc("Production Crop Cycle", cycle_setup.create_cycle({"unit": u.name, "variety": self.hass,
			"existing": 1, "planting_date": add_days(today(), -2000), "current_stage": "Fruit set",
			"last_flowering_date": add_days(today(), -200)})["name"])
		self.assertEqual(c.current_stage, "Fruit set")

	def test_schedule_from_drops_the_past(self):
		start = add_days(today(), -30)
		proto = frappe._dict(key_activities=[frappe._dict(name="k1", operation="Op", week=1, repeats="Every cycle", planned_qty=None, description=None),
			frappe._dict(name="k2", operation="Op", week=3, repeats="Every cycle", planned_qty=None, description=None),
			frappe._dict(name="k9", operation="Op", week=9, repeats="Every cycle", planned_qty=None, description=None)], cultural_activities=[])
		cyc = frappe._dict(name="X", start_date=start, cycle_no=1)
		everything = schedule.due_items(cyc, proto, add_days(start, -7), add_days(start, 90))
		self.assertEqual(len(everything), 3)
		cyc.schedule_from = today()
		after = schedule.due_items(cyc, proto, add_days(start, -7), add_days(start, 90))
		self.assertEqual([i["row"] for i in after], ["k9"])

	def test_import_preview_and_create(self):
		u = self._unit(area=20, trees=3000)
		text = ("block,variety,planting_date,trees,area_ha,current_stage,last_season_kg\n"
			f"{u.name},CS Hass,15/03/2019,1500,10,Fruit set,30000\n"
			f"{u.name},CS Hass,2019-03-15,1600,11,Fruit set,\n"
			"NOPE,CS Hass,2019-03-15,1,1,Fruit set,\n"
			f"{u.name},CS Hass,2019-03-15,10,1,Nothing,\n")
		rows = cycle_setup.check_rows(self.crop.name, cycle_setup.parse_file("a.csv", base64.b64encode(text.encode()).decode()))
		self.assertEqual([bool(r["errors"]) for r in rows], [False, False, True, True])
		self.assertEqual(rows[0]["values"]["planting_date"], "2019-03-15")
		self.assertTrue(rows[1]["warnings"])  # 10 + 11 ha on a 20 ha block, 3100 trees on 3000
		res = cycle_setup.import_rows(self.crop.name, [r["raw"] for r in rows])
		self.assertEqual([r["ok"] for r in res], [True, True, False, False])
		self.assertEqual(frappe.db.count("Production Crop Cycle", {"unit": u.name}), 2)

	def test_template_is_parsable(self):
		rows = cycle_setup.parse_file("t.csv", base64.b64encode(cycle_setup.template_csv().encode()).decode())
		self.assertEqual(len(rows), 1)
		self.assertIn("planting_date", rows[0])
