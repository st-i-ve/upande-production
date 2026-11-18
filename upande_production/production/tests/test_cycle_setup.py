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


class TestCycleSetupOtherCrops(IntegrationTestCase):
	"""A crop without avocado's stage anchor: seasons of fruits and vegetables with no stage rows."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make("Farm", farm_name="CSO Farm", company=cls.company, abbreviation="CSO",
			farm_type=[{"farm_type": "Has Blocks"}])
		cls.crop = _make("Production Crop", crop_name="CSO Crop", crop_key="cso-crop", unit_label="Block", yield_uom="Kg")
		cls.item = _make("Item", item_code="CSO Tomato", item_name="CSO Tomato", item_group="All Item Groups",
			stock_uom="Kg", is_stock_item=1).name
		cls.op = _make("Field Operation", crop=cls.crop.name, operation_name="CSO Weeding", category="Other",
			work_uom="Kg", default_rate=10).name
		cls.protocol = _make("Production Protocol", protocol_name="CSO Proto", crop=cls.crop.name, version_status="Active",
			key_activities=[{"operation": cls.op, "week": w, "planned_qty": 1} for w in (1, 5, 6)]).name
		cls.staged = _make("Production Variety", variety_name="CSO Staged", crop=cls.crop.name, item=cls.item,
			stage_anchor="Planting", harvest_pattern="Interval", harvest_interval_weeks=2, lifespan_years=1,
			plants_per_ha=100, days_to_first_harvest=60,
			stages=_stages(("Vegetative", 0, 40, 0), ("Fruiting", 40, 20, 0), ("Picking", 60, 60, 1))).name

	def _unit(self, area=2):
		return _make("Production Unit", unit_name=f"CSO B{frappe.generate_hash(length=6)}", unit_type="Orchard Block",
			crop=self.crop.name, farm=self.farm.name, company=self.company, area_ha=area, plant_count=0)

	def _plan_tasks(self, cycle, day):
		from frappe.utils import getdate

		from upande_production.production.logic import plans

		y, w = getdate(day).isocalendar()[:2]
		plan = plans.get_or_create_plan(self.crop.name, self.farm.name, y, w)
		plans.generate_week_detail(plan.name)
		plan.reload()
		return [t for t in plan.tasks if t.cycle == cycle]

	def test_existing_without_stages_starts_at_the_real_date(self):
		u = self._unit()
		started = add_days(today(), -30)
		r = cycle_setup.create_cycle({"unit": u.name, "item": self.item, "existing": 1, "planting_date": started,
			"protocol": self.protocol, "last_harvest_date": add_days(today(), -5), "last_season_yield_kg": 900})
		c = frappe.get_doc("Production Crop Cycle", r["name"])
		self.assertEqual(getdate(c.start_date), getdate(started))
		self.assertEqual(getdate(c.schedule_from), getdate(today()))
		self.assertEqual(c.status, "Active")
		self.assertEqual(c.item, self.item)
		self.assertTrue(c.existing_cycle)
		self.assertEqual(len(c.stage_actuals), 0)

	def test_existing_needs_a_start_date_and_variety_or_item(self):
		u = self._unit()
		with self.assertRaises(frappe.ValidationError):
			cycle_setup.create_cycle({"unit": u.name, "item": self.item, "existing": 1})
		with self.assertRaises(frappe.ValidationError):
			cycle_setup.create_cycle({"unit": u.name, "existing": 1, "planting_date": add_days(today(), -3)})

	def test_already_harvesting_flag_and_harvest_stage(self):
		u = self._unit()
		c = frappe.get_doc("Production Crop Cycle", cycle_setup.create_cycle({"unit": u.name, "item": self.item,
			"existing": 1, "planting_date": add_days(today(), -50), "already_harvesting": 1})["name"])
		self.assertEqual(c.status, "Harvesting")
		c2 = frappe.get_doc("Production Crop Cycle", cycle_setup.create_cycle({"unit": u.name, "variety": self.staged,
			"existing": 1, "planting_date": add_days(today(), -70), "current_stage": "Picking"})["name"])
		self.assertEqual(c2.status, "Harvesting")
		self.assertEqual(c2.current_stage, "Picking")

	def test_existing_with_optional_stage_left_blank(self):
		u = self._unit()
		c = frappe.get_doc("Production Crop Cycle", cycle_setup.create_cycle({"unit": u.name, "variety": self.staged,
			"existing": 1, "planting_date": add_days(today(), -10)})["name"])
		self.assertEqual(getdate(c.start_date), getdate(add_days(today(), -10)))
		self.assertEqual(c.status, "Active")

	def test_nothing_before_today_is_planned(self):
		u = self._unit()
		started = add_days(today(), -30)  # key weeks 1 and 5 fell 30 and 2 days ago, week 6 falls in 5 days
		name = cycle_setup.create_cycle({"unit": u.name, "item": self.item, "existing": 1, "planting_date": started,
			"protocol": self.protocol})["name"]
		self.assertEqual(self._plan_tasks(name, started), [])
		self.assertEqual(self._plan_tasks(name, add_days(today(), -2)), [])
		ahead = self._plan_tasks(name, add_days(today(), 5))
		self.assertEqual([getdate(t.due_date) for t in ahead], [getdate(add_days(today(), 5))])

	def test_import_for_another_crop(self):
		u = self._unit(area=3)
		self.assertNotIn("trees", cycle_setup.template_columns(self.crop.name))
		self.assertIn("item", cycle_setup.template_columns(self.crop.name))
		text = ("block,variety,item,protocol,planting_date,area_ha,current_stage,already_harvesting,last_harvest_date\n"
			f"{u.name},,{self.item},CSO Proto,{add_days(today(), -20)},2,,,\n"
			f"{u.name},CSO Staged,,,{add_days(today(), -70)},2,Picking,,\n"
			f"{u.name},,{self.item},,{add_days(today(), -9)},1,,yes,\n"
			f"{u.name},,,,{add_days(today(), -9)},1,,,\n"
			f"{u.name},,{self.item},,{add_days(today(), 9)},1,,,\n"
			f"{u.name},CSO Staged,,,{add_days(today(), -9)},1,Nowhere,,\n"
			f"{u.name},,{self.item},No Such,{add_days(today(), -9)},1,,,\n")
		rows = cycle_setup.check_rows(self.crop.name, cycle_setup.parse_file("a.csv", base64.b64encode(text.encode()).decode()))
		self.assertEqual([bool(r["errors"]) for r in rows], [False, False, False, True, True, True, True])
		self.assertTrue(rows[1]["warnings"])  # 2 + 2 ha on a 3 ha block
		res = cycle_setup.import_rows(self.crop.name, [r["raw"] for r in rows])
		self.assertEqual([r["ok"] for r in res], [True, True, True, False, False, False, False])
		made = frappe.get_all("Production Crop Cycle", filters={"unit": u.name}, fields=["status", "protocol", "schedule_from"],
			order_by="creation asc")
		self.assertEqual([m.status for m in made], ["Active", "Harvesting", "Harvesting"])
		self.assertEqual(made[0].protocol, self.protocol)
		self.assertTrue(all(getdate(m.schedule_from) == getdate(today()) for m in made))

	def test_update_cycle_rules(self):
		u, u2 = self._unit(), self._unit()
		name = cycle_setup.create_cycle({"unit": u.name, "item": self.item, "existing": 1, "planting_date": add_days(today(), -30),
			"protocol": self.protocol})["name"]
		frappe.db.set_value("Production Crop Cycle", name, "schedule_from", add_days(today(), -30))
		with self.assertRaises(frappe.ValidationError):
			cycle_setup.update_cycle(name, {"status": "Done"})
		with self.assertRaises(frappe.ValidationError):
			cycle_setup.update_cycle(name, {"expected_harvest_start": add_days(today(), 20), "expected_harvest_end": add_days(today(), 10)})
		with self.assertRaises(frappe.ValidationError):
			cycle_setup.update_cycle(name, {"planting_date": add_days(today(), 3)})
		# a note and an area do not re-plan
		r = cycle_setup.update_cycle(name, {"notes": "Moved from the old system", "area_ha": 1})
		self.assertEqual(r["notes"], [])
		self.assertEqual(getdate(frappe.db.get_value("Production Crop Cycle", name, "schedule_from")), getdate(add_days(today(), -30)))
		# a new start date on a running cycle re-plans from today
		r = cycle_setup.update_cycle(name, {"start_date": add_days(today(), -20)})
		self.assertEqual(len(r["notes"]), 1)
		c = frappe.get_doc("Production Crop Cycle", name)
		self.assertEqual((getdate(c.start_date), getdate(c.schedule_from), c.notes, c.area_ha),
			(getdate(add_days(today(), -20)), getdate(today()), "Moved from the old system", 1))
		# the block moves only while there are no tasks
		cycle_setup.update_cycle(name, {"unit": u2.name})
		self.assertEqual(frappe.db.get_value("Production Crop Cycle", name, "unit"), u2.name)
		from upande_production.production.logic import plans

		y, w = getdate(add_days(today(), 5)).isocalendar()[:2]
		plan = plans.get_or_create_plan(self.crop.name, self.farm.name, y, w)
		plans.generate_week_detail(plan.name)
		plan.reload()
		self.assertTrue([t for t in plan.tasks if t.cycle == name])
		with self.assertRaises(frappe.ValidationError):
			cycle_setup.update_cycle(name, {"unit": u.name})
		# the planned tasks stay when the protocol is changed; closing is allowed
		cycle_setup.update_cycle(name, {"status": "Closed"})
		plan.reload()
		self.assertTrue([t for t in plan.tasks if t.cycle == name])
		self.assertEqual(frappe.db.get_value("Production Crop Cycle", name, "status"), "Closed")

	def test_update_cycle_refuses_a_retired_block_and_warns_over_capacity(self):
		u = self._unit(area=2)
		a = cycle_setup.create_cycle({"unit": u.name, "item": self.item, "existing": 1, "planting_date": add_days(today(), -3), "area_ha": 2})["name"]
		b = cycle_setup.create_cycle({"unit": u.name, "item": self.item, "existing": 1, "planting_date": add_days(today(), -3), "area_ha": 1})["name"]
		r = cycle_setup.update_cycle(b, {"area_ha": 2})
		self.assertEqual(len(r["warnings"]), 1)
		retired = self._unit()
		frappe.db.set_value("Production Unit", retired.name, "status", "Retired")
		with self.assertRaises(frappe.ValidationError):
			cycle_setup.update_cycle(a, {"unit": retired.name})
