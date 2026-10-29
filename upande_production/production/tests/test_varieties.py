import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, today

from upande_production.production.doctype.production_variety.production_variety import derive
from upande_production.production.logic import plans, protocols as P, stages
from upande_production.production.logic.weeks import iso_of


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


def _stages(*rows):
	return [{"stage": n, "start_day": s, "length_days": ln, "is_harvest": 1 if h else 0} for n, s, ln, h in rows]


class TestVarieties(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make("Farm", farm_name="TV Farm", company=cls.company, abbreviation="TVF",
			farm_type=[{"farm_type": "Has Blocks"}])
		cls.crop = _make("Production Crop", crop_name="TV Crop", crop_key="tv-crop", unit_label="Block", yield_uom="Kg")
		cls.other_crop = _make("Production Crop", crop_name="TV Other", crop_key="tv-other", unit_label="Block", yield_uom="Kg")
		cls.op = _make("Field Activity", crop=cls.crop.name, operation_name="TV Top Dress", category="Fertilising",
			work_uom="Kg", default_rate=10)
		cls.unit = _make("Production Unit", unit_name="TV Unit", unit_type="Orchard Block", crop=cls.crop.name,
			farm=cls.farm.name, company=cls.company)
		cls.items = {}
		for n in ("TV Product", "TV Product - Alpha", "TV Product - Beta"):
			cls.items[n] = _make("Item", item_code=n, item_name=n, item_group="All Item Groups", stock_uom="Kg",
				is_stock_item=1).name
		cls.alpha = _make("Production Variety", variety_name="TV Alpha", crop=cls.crop.name, product="TV Product",
			item="TV Product - Alpha", days_to_first_harvest=100, harvest_window_days=15,
			stages=_stages(("Planting", 0, 7, 0), ("Vegetative", 7, 33, 0), ("Bulking", 40, 60, 0), ("Harvest", 100, 15, 1)))
		cls.beta = _make("Production Variety", variety_name="TV Beta", crop=cls.crop.name, product="TV Product",
			item="TV Product - Beta", days_to_first_harvest=80, harvest_window_days=10,
			stages=_stages(("Planting", 0, 7, 0), ("Harvest", 80, 10, 1)))
		cls.flower = _make("Production Variety", variety_name="TV Flower", crop=cls.crop.name, item="TV Product",
			stage_anchor="Flowering", days_to_first_harvest=240, harvest_window_days=100,
			stages=_stages(("Flowering", 0, 30, 0), ("Fruit set", 30, 60, 0), ("Harvest", 90, 60, 1)))

	def _protocol(self, name, variety=None, **kw):
		return _make("Production Protocol", protocol_name=name, crop=self.crop.name, item=self.items["TV Product"],
			variety=variety, version_status="Active",
			key_activities=[{"operation": self.op.name, "week": 1, "planned_qty": 1}], **kw)

	def _cycle(self, variety=None, start=None, **kw):
		return _make("Production Crop Cycle", unit=self.unit.name, crop=self.crop.name, variety=variety,
			start_date=start or add_days(today(), -10), status="Active", **kw)

	# ---------------------------------------------------------------- stage_on

	def test_stages_for(self):
		rows = stages.stages_for("TV Alpha")
		self.assertEqual([r.stage for r in rows], ["Planting", "Vegetative", "Bulking", "Harvest"])
		self.assertEqual(rows[2]["end_day"], 100)
		self.assertEqual(stages.stages_for(None), [])

	def test_stage_on_without_actuals(self):
		c = self._cycle("TV Alpha", start="2026-01-01")
		r = stages.stage_on(c, "2026-01-01")
		self.assertEqual((r["stage"], r["day"], r["is_harvest"]), ("Planting", 0, 0))
		self.assertEqual(r["start"], getdate("2026-01-01"))
		self.assertEqual(r["end"], getdate("2026-01-08"))
		self.assertEqual(stages.stage_on(c, "2026-01-08")["stage"], "Vegetative")
		self.assertEqual(stages.stage_on(c, "2026-02-09")["stage"], "Vegetative")  # day 39
		self.assertEqual(stages.stage_on(c, "2026-02-10")["stage"], "Bulking")  # day 40
		h = stages.stage_on(c, "2026-04-11")  # day 100
		self.assertEqual((h["stage"], h["is_harvest"], h["day"]), ("Harvest", 1, 100))
		self.assertEqual(stages.stage_on(c, "2027-01-01")["stage"], "Harvest")  # past the end: last stage
		self.assertIsNone(stages.stage_on(c, "2025-12-25")["stage"])  # before the start
		self.assertIsNone(stages.stage_on(self._cycle(None), today())["stage"])

	def test_stage_on_with_actuals_shifts_later_stages(self):
		c = self._cycle("TV Alpha", start="2026-01-01")
		# Bulking really began 5 days late: it and Harvest move, earlier stages do not
		c.append("stage_actuals", {"stage": "Bulking", "actual_date": "2026-02-15"})
		c.save()
		self.assertEqual(stages.stage_on(c, "2026-02-10")["stage"], "Vegetative")
		b = stages.stage_on(c, "2026-02-15")
		self.assertEqual((b["stage"], b["start"]), ("Bulking", getdate("2026-02-15")))
		self.assertEqual(stages.stage_on(c, "2026-04-11")["stage"], "Bulking")  # Harvest now starts 2026-04-16
		self.assertEqual(stages.stage_on(c, "2026-04-16")["stage"], "Harvest")
		self.assertEqual(stages.harvest_start(c), getdate("2026-04-11"))  # the explicit expected date wins
		c.expected_harvest_start = None
		self.assertEqual(stages.harvest_start(c), getdate("2026-04-16"))  # the shifted harvest stage

	def test_first_stage_actual_reanchors(self):
		c = self._cycle("TV Flower", start="2026-06-01")
		c.append("stage_actuals", {"stage": "Flowering", "actual_date": "2026-01-01"})
		c.save()
		self.assertEqual(stages.anchor_date(c), getdate("2026-01-01"))
		self.assertEqual(stages.stage_on(c, "2026-02-15")["stage"], "Fruit set")
		self.assertEqual(stages.stage_on(c, "2026-04-01")["stage"], "Harvest")  # day 90
		self.assertEqual(stages.stage_on(c, "2026-06-01")["day"], 151)

	def test_harvest_start(self):
		c = self._cycle("TV Alpha", start="2026-01-01")
		self.assertEqual(c.expected_harvest_start, getdate("2026-04-11"))  # defaulted from the variety
		self.assertEqual(c.expected_harvest_end, getdate("2026-04-26"))
		self.assertEqual(stages.harvest_start(c), getdate("2026-04-11"))
		c.expected_harvest_start = None
		self.assertEqual(stages.harvest_start(c), getdate("2026-04-11"))  # from the harvest stage
		c.expected_harvest_start = "2026-05-01"
		self.assertEqual(stages.harvest_start(c), getdate("2026-05-01"))
		self.assertIsNone(stages.harvest_start(self._cycle(None)))

	def test_current_stage_on_save_and_refresh(self):
		c = self._cycle("TV Alpha", start=add_days(today(), -10))
		self.assertEqual(c.current_stage, "Vegetative")
		frappe.db.set_value("Production Crop Cycle", c.name, "current_stage", "Planting")
		self.assertEqual(stages.refresh_current_stage(c.name), "Vegetative")
		self.assertEqual(frappe.db.get_value("Production Crop Cycle", c.name, "current_stage"), "Vegetative")
		self.assertGreaterEqual(stages.refresh_all_open(), 1)

	def test_pond_stocking_stage(self):
		pond = _make("Production Unit", unit_name="TV Pond", unit_type="Pond", crop=self.crop.name,
			farm=self.farm.name, company=self.company)
		st = frappe._dict(doctype="Pond Stocking", stocking_date="2026-01-01", strain="TV Alpha")
		self.assertEqual(stages.stage_on(st, "2026-01-10")["stage"], "Vegetative")
		self.assertEqual(stages.variety_of(st), "TV Alpha")
		del pond

	# ---------------------------------------------------------------- cycle behaviour

	def test_item_follows_variety(self):
		c = self._cycle("TV Alpha", item=self.items["TV Product - Beta"])
		self.assertEqual(c.item, "TV Product - Alpha")

	def test_protocol_defaults_to_varietys_active(self):
		p = self._protocol("TV Proto Alpha", variety="TV Alpha")
		frappe.db.set_value("Production Variety", "TV Alpha", "default_protocol", p.name)
		self.assertEqual(self._cycle("TV Alpha").protocol, p.name)
		# a newer Active version of the family wins
		v2 = P.new_version(p.name)["name"]
		self.assertEqual(frappe.db.get_value("Production Protocol", v2, "variety"), "TV Alpha")
		P.submit_for_approval(v2)
		frappe.set_user("Administrator")
		P.approve(v2)
		self.assertEqual(self._cycle("TV Alpha").protocol, v2)

	def test_protocol_falls_back_to_product(self):
		prod = self._protocol("TV Proto Product")
		prod.db_set("item", "TV Product")
		self.assertEqual(self._cycle("TV Beta").protocol, prod.name)

	def test_protocol_of_another_variety_refused(self):
		pa = self._protocol("TV Proto A2", variety="TV Alpha")
		with self.assertRaises(frappe.ValidationError):
			self._cycle("TV Beta", protocol=pa.name)
		# a variety of another crop is refused too
		other = _make("Production Variety", variety_name="TV Elsewhere", crop=self.other_crop.name,
			item=self.items["TV Product - Beta"])
		with self.assertRaises(frappe.ValidationError):
			self._cycle(other.name)

	def test_protocol_version_keeps_variety_and_anchor(self):
		p = _make("Production Protocol", protocol_name="TV Proto Anchor", crop=self.crop.name, variety="TV Alpha",
			version_status="Active", key_activities=[{"operation": self.op.name, "week": 2}])
		v2 = frappe.get_doc("Production Protocol", P.new_version(p.name)["name"])
		self.assertEqual(v2.variety, "TV Alpha")
		self.assertEqual(v2.key_activities[0].week, 2)
		self.assertEqual(v2.item, "TV Product - Alpha")  # defaulted from the variety on the original

	# ---------------------------------------------------------------- anchored steps

	def test_step_due_date(self):
		c = self._cycle("TV Alpha", start="2026-01-01")
		self.assertEqual(stages.step_due_date(c, {"day_offset": 3}), getdate("2026-01-04"))
		self.assertEqual(stages.step_due_date(c, {"day_offset": 3, "repeat_every_days": 7}, 2), getdate("2026-01-18"))
		step = {"anchor_stage": "Vegetative", "day_offset": 10}
		self.assertEqual(stages.step_due_date(c, step), getdate("2026-01-18"))  # Vegetative starts day 7
		c.append("stage_actuals", {"stage": "Vegetative", "actual_date": "2026-01-12"})
		c.save()
		self.assertEqual(stages.step_due_date(c, step), getdate("2026-01-22"))
		# an unknown stage falls back to the cycle start
		self.assertEqual(stages.step_due_date(c, {"anchor_stage": "Nope", "day_offset": 2}), getdate("2026-01-03"))

	def test_generate_uses_key_and_cultural(self):
		p = _make("Production Protocol", protocol_name="TV Proto Gen", crop=self.crop.name, variety="TV Alpha",
			version_status="Active",
			key_activities=[{"operation": self.op.name, "week": 6, "planned_qty": 5}],
			cultural_activities=[{"operation": self.op.name, "schedule": "Interval", "interval_weeks": 1,
				"planned_qty": 2}])
		# week 6 starts on day 35, and the weekly activity falls on day 35 too: make that today
		c = self._cycle("TV Alpha", start=add_days(today(), -35), protocol=p.name)
		monday = add_days(today(), -getdate(today()).weekday())
		plan = plans.get_or_create_plan(self.crop.name, self.farm.name, *iso_of(monday))
		self.assertGreaterEqual(plans.generate_week(plan.name), 2)
		plan.reload()
		mine = [t for t in plan.tasks if t.cycle == c.name and getdate(t.due_date) == getdate(today())]
		self.assertEqual(len(mine), 2)
		refs = {t.protocol_ref for t in mine}
		self.assertTrue(any(r.endswith(":k") for r in refs))
		self.assertTrue(any(r.endswith(":5") for r in refs))

	def test_seed_sanity(self):
		if not frappe.db.exists("Production Variety", "Shangi"):
			self.skipTest("varieties not seeded on this site")
		names = frappe.get_all("Production Variety", filters={"crop": ("in", ["Avocado", "Fruits & Vegetables", "Aquaculture"])},
			pluck="name")
		self.assertGreaterEqual(len(names), 13)
		for n in names:
			v = frappe.get_doc("Production Variety", n)
			self.assertTrue(frappe.db.exists("Item", v.item), n)
			self.assertEqual(sum(1 for s in v.stages if s.is_harvest), 1, n)
			self.assertEqual(frappe.db.get_value("Production Protocol", v.default_protocol, "variety"), n)
			self.assertIsNotNone(stages.variety_protocol(n), n)
		for c in frappe.get_all("Production Crop Cycle", filters={"crop": ("in", ["Avocado", "Fruits & Vegetables"]),
				"variety": ("is", "not set")}, pluck="name"):
			self.fail(f"cycle {c} has no variety")
		for c in frappe.get_all("Production Crop Cycle", filters={"crop": ("in", ["Avocado", "Fruits & Vegetables"])},
				fields=["name", "variety", "item", "protocol", "status", "current_stage"]):
			self.assertEqual(c.item, frappe.db.get_value("Production Variety", c.variety, "item"), c.name)
			self.assertTrue(c.protocol, c.name)
			self.assertEqual(frappe.db.get_value("Production Protocol", c.protocol, "variety"), c.variety, c.name)
			if c.status != "Closed":
				self.assertTrue(c.current_stage, c.name)
		self.assertEqual(frappe.db.get_value("Production Crop Cycle", {"unit": "PH1-B1", "status": "Harvesting"}, "variety"), "Hass")
		self.assertEqual(frappe.db.get_value("Production Crop Cycle", {"unit": "PH1-B3", "status": "Harvesting"}, "variety"), "Fuerte")
		self.assertFalse(frappe.get_all("Field Activity", filters={"category": ("is", "not set")}, pluck="name"))
		self.assertFalse(frappe.get_all("Pond Stocking", filters={"strain": ("is", "not set")}, pluck="name"))

	# ---------------------------------------------------------------- desk api

	def test_save_list_variety_rules_and_actuals(self):
		from unittest import mock

		from upande_production.api import varieties as api
		patcher = mock.patch.object(frappe.db, "rollback")  # envelope errors must not wipe class fixtures
		patcher.start()
		self.addCleanup(patcher.stop)
		r = api.save_variety({"variety_name": "TV Gamma", "crop": self.crop.name, "item": "TV Product - Alpha",
			"stages": [{"stage": "Plant", "start_day": 0, "length_days": 10, "is_harvest": 0},
				{"stage": "Pick", "start_day": 10, "length_days": 5, "is_harvest": 1}]})
		self.assertEqual(r["name"], "TV Gamma")
		rows = api.list_varieties(self.crop.name)["varieties"]
		g = next(v for v in rows if v["name"] == "TV Gamma")
		self.assertEqual([s["stage"] for s in g["stages"]], ["Plant", "Pick"])
		bad = api.save_variety({"variety_name": "TV Bad", "crop": self.crop.name, "item": "TV Product - Alpha",
			"stages": [{"stage": "X", "start_day": 0, "length_days": 0}]})
		self.assertIn("error", bad)
		rule = api.save_rule({"crop": self.crop.name, "variety": "TV Gamma", "stage": "Plant",
			"operation_category": "Weeding", "rule_type": "Not in stage", "enforcement": "Warn", "enabled": 1})
		self.assertTrue(rule["name"])
		self.assertIn("error", api.save_rule({"crop": self.crop.name, "rule_type": "Not in stage", "enforcement": "Warn"}))
		api.set_rule_enabled(rule["name"], 0)
		self.assertEqual(next(x for x in api.list_rules(self.crop.name)["rules"] if x["name"] == rule["name"])["enabled"], 0)
		cy = _make("Production Crop Cycle", unit=self.unit.name, crop=self.crop.name, variety="TV Gamma",
			start_date=add_days(today(), -3), status="Active")
		out = api.set_stage_actual(cy.name, "Pick", str(add_days(today(), 2)))
		self.assertEqual(out["current_stage"], "Plant")
		self.assertTrue(next(b for b in out["stage_bands"] if b["stage"] == "Pick")["actual"])
		self.assertIn("error", api.set_stage_actual(cy.name, "Nope", str(today())))

	# ---------------------------------------------------------------- template derivation

	def test_variety_derives_weeks_and_density(self):
		d = frappe._dict(plants_per_m2=0.0156, is_flowering=1, weeks_to_first_flowering=104,
			weeks_flowering_to_harvest=36, harvest_window_weeks=12)
		derive(d)
		self.assertEqual(d.weeks_to_first_harvest, 140)
		self.assertEqual(d.days_to_first_harvest, 980)
		self.assertEqual(d.harvest_window_days, 84)
		self.assertEqual(d.plants_per_ha, 156)

	def test_variety_derives_m2_from_ha_and_typed_weeks(self):
		d = frappe._dict(plants_per_ha=20000, weeks_to_first_harvest=10)
		derive(d)
		self.assertEqual(d.plants_per_m2, 2)
		self.assertEqual(d.days_to_first_harvest, 70)

	def test_variety_clears_hidden_fields(self):
		d = frappe._dict(harvest_pattern="Once", is_flowering=1, weeks_to_first_flowering=10,
			weeks_flowering_to_harvest=5, weeks_to_reflower_after_harvest=10, harvest_interval_weeks=4)
		derive(d)
		self.assertFalse(d.weeks_to_reflower_after_harvest)
		self.assertFalse(d.harvest_interval_weeks)
		self.assertEqual(d.weeks_to_first_harvest, 15)
		n = frappe._dict(harvest_pattern="Interval", is_flowering=0, weeks_to_first_flowering=10,
			weeks_flowering_to_harvest=5, weeks_to_reflower_after_harvest=3, weeks_to_first_harvest=30)
		derive(n)
		self.assertFalse(n.weeks_to_first_flowering or n.weeks_flowering_to_harvest or n.weeks_to_reflower_after_harvest)
		self.assertEqual(n.weeks_to_first_harvest, 30)
		self.assertEqual(n.days_to_first_harvest, 210)

	def test_variety_saves_derived_values(self):
		v = _make("Production Variety", variety_name="TV Derived", crop=self.crop.name, item="TV Product - Alpha",
			plants_per_m2=0.0156, is_flowering=1, flowering_pattern="Interval", flowering_interval_weeks=52, weeks_to_first_flowering=104, weeks_flowering_to_harvest=36)
		v.reload()
		self.assertEqual(v.weeks_to_first_harvest, 140)
		self.assertEqual(v.days_to_first_harvest, 980)


class TestFloweringPatternDerive(IntegrationTestCase):
	def test_seasonal_derive_clears_interval_fields(self):
		d = frappe._dict(is_flowering=1, flowering_pattern="Seasonal", weeks_to_maturity=130,
			weeks_to_first_flowering=20, flowering_interval_weeks=4,
			flowering_seasons=[{"weeks_flowering_to_harvest": 36}])
		derive(d)
		self.assertFalse(d.weeks_to_first_flowering or d.flowering_interval_weeks)
		self.assertEqual(d.weeks_to_first_harvest, 166)

	def test_patch_sets_interval_pattern(self):
		from upande_production.patches import flowering_pattern_from_reflower

		crop = frappe.db.get_value("Production Crop", {}, "name")
		item = frappe.db.get_value("Item", {"is_stock_item": 1}, "name")
		name = "TV Patch Interval"
		if frappe.db.exists("Production Variety", name):
			frappe.delete_doc("Production Variety", name, force=1)
		old = frappe.get_doc({"doctype": "Production Variety", "name": name, "variety_name": name, "crop": crop, "item": item,
			"is_flowering": 1, "harvest_pattern": "Interval", "weeks_to_reflower_after_harvest": 6,
			"weeks_flowering_to_harvest": 30})
		old.db_insert()  # a legacy row: validation now refuses a flowering variety without a pattern
		flowering_pattern_from_reflower.execute()
		v = frappe.db.get_value("Production Variety", name, ["flowering_pattern", "flowering_interval_weeks"], as_dict=True)
		self.assertEqual((v.flowering_pattern, v.flowering_interval_weeks), ("Interval", 36))
