import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from upande_production.api import field_crops as fc_api
from upande_production.patches import add_field_crops
from upande_production.production.logic import analytics, cycle_setup, field_crops


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


CAB, POT = "Cabbage", "Potato"  # crops are matched by name across sections; the real site already has both


class TestFieldCrops(IntegrationTestCase):
	"""Field Crops inside a mixed section; nothing here commits, so the class rolls back."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		for uom in ("Kg", "Pieces"):
			if not frappe.db.exists("UOM", uom):
				_make("UOM", uom_name=uom)
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		if not frappe.db.exists("Item Group", "All Item Groups"):
			_make("Item Group", item_group_name="All Item Groups", is_group=1)
		cls.farm = _make("Farm", farm_name="FCX Farm", company=cls.company, abbreviation="FCX", farm_type=[{"farm_type": "Has Blocks"}])
		cls.section = _make("Production Crop", crop_name="FCX Mixed", crop_key="fcx-mixed", unit_label="Block", yield_uom="Kg",
			enabled=1, uses_crop_cycles=1)
		cls.single = _make("Production Crop", crop_name="FCX Single", crop_key="fcx-single", unit_label="Block", yield_uom="Kg",
			enabled=1, uses_crop_cycles=1)
		for code, name in (("FCX Cabbage", "Cabbage"), ("FCX Potatoes", "Potatoes"), ("FCX Cabbage - Gloria", "Cabbage - Gloria"),
				("FCX Potatoes - Shangi", "Potatoes - Shangi"), ("FCX Lone", "Lone")):
			_make("Item", item_code=code, item_name=name, item_group="All Item Groups", stock_uom="Kg", is_stock_item=1)
		cls.gloria = _make("Production Variety", variety_name="FCX Gloria", crop=cls.section.name, product="FCX Cabbage",
			item="FCX Cabbage - Gloria").name
		cls.shangi = _make("Production Variety", variety_name="FCX Shangi", crop=cls.section.name, product="FCX Potatoes",
			item="FCX Potatoes - Shangi").name
		cls.lone = _make("Production Variety", variety_name="FCX Lone", crop=cls.single.name, product="FCX Lone", item="FCX Lone").name
		cls.unit = _make("Production Unit", unit_name="FCX Block 1", crop=cls.section.name, farm=cls.farm.name,
			unit_type="Orchard Block", company=cls.company, area_ha=4).name
		cls.unit2 = _make("Production Unit", unit_name="FCX Block 2", crop=cls.section.name, farm=cls.farm.name,
			unit_type="Orchard Block", company=cls.company, area_ha=4).name
		cls.single_unit = _make("Production Unit", unit_name="FCX Block S", crop=cls.single.name, farm=cls.farm.name,
			unit_type="Orchard Block", company=cls.company, area_ha=4).name

	def setUp(self):
		frappe.db.savepoint("fcx_test")

	def tearDown(self):
		frappe.db.rollback(save_point="fcx_test")

	def _cycle(self, unit, variety, **kw):
		return _make("Production Crop Cycle", unit=unit, crop=self.section.name, variety=variety, cycle_type="Season",
			start_date=today(), status="Active", **kw)

	def _legacy_state(self):
		"""The state of a site before the patch: no Field Crops, nothing linked."""
		for dt in ("Production Variety", "Production Crop Cycle"):
			frappe.db.set_value(dt, {"crop": ("in", [self.section.name, self.single.name]), "field_crop": ("is", "set")}, "field_crop", None)
		frappe.db.delete("Production Field Crop", {"name": ("in", [CAB, POT])})  # rolled back with the test
		frappe.db.set_value("Production Variety", self.gloria, "product", "FCX Cabbage")
		frappe.db.set_value("Production Variety", self.shangi, "product", "FCX Potatoes")

	# -- doctype ---------------------------------------------------------------------------

	def test_field_crop_doctype(self):
		fc = _make("Production Field Crop", crop_name="FCX Beans", crop_group="Vegetable Crops", harvest_uom="Kg")
		self.assertEqual(fc.name, "FCX Beans")
		self.assertEqual(fc.enabled, 1)
		with self.assertRaises(frappe.DuplicateEntryError):
			_make("Production Field Crop", crop_name="FCX Beans", crop_group="Vegetable Crops", harvest_uom="Kg")
		with self.assertRaises(frappe.MandatoryError):
			_make("Production Field Crop", crop_name="FCX NoUnit", crop_group="Vegetable Crops")
		with self.assertRaises(frappe.MandatoryError):
			_make("Production Field Crop", crop_name="FCX NoGroup", harvest_uom="Kg")
		# a section has crops through its varieties
		self.assertFalse(field_crops.has_field_crops(self.section.name))
		frappe.db.set_value("Production Variety", self.gloria, "field_crop", "FCX Beans")
		self.assertFalse(field_crops.has_field_crops(self.section.name))  # one crop is not "a section with crops"
		self.assertEqual(field_crops.only_crop(self.section.name), "FCX Beans")
		_make("Production Field Crop", crop_name="FCX Peas2", crop_group="Vegetable Crops", harvest_uom="Kg")
		frappe.db.set_value("Production Variety", self.shangi, "field_crop", "FCX Peas2")
		self.assertTrue(field_crops.has_field_crops(self.section.name))
		self.assertFalse(field_crops.has_field_crops(self.single.name))

	def test_singular(self):
		self.assertEqual(field_crops.singular("Potatoes"), "Potato")
		self.assertEqual(field_crops.singular("Passion Fruit"), "Passion Fruit")
		self.assertEqual(field_crops.singular("Cabbage"), "Cabbage")
		self.assertEqual(field_crops.singular("Maize"), "Maize")
		self.assertEqual(field_crops.singular("Onion"), "Onion")

	def test_api_list_and_save(self):
		r = fc_api.save_field_crop({"crop_name": "FCX Peas", "crop_group": "Vegetable Crops", "harvest_uom": "Kg"})
		self.assertEqual(r["message"]["name"] if "message" in r else r["name"], "FCX Peas")
		fc_api.save_field_crop({"name": "FCX Peas", "harvest_uom": "Pieces", "crop_name": "renamed"})
		frappe.db.set_value("Production Variety", self.gloria, "field_crop", "FCX Peas")
		row = next(x for x in fc_api.list_field_crops(self.section.name)["field_crops"] if x["name"] == "FCX Peas")
		self.assertEqual((row["harvest_uom"], row["crop_group"]), ("Pieces", "Vegetable Crops"))

	# -- patch -----------------------------------------------------------------------------

	def test_patch_creates_links_and_is_idempotent(self):
		self._legacy_state()
		cyc = self._cycle(self.unit, self.gloria)
		harvest = _make("Production Harvest", unit=self.unit, crop=self.section.name, cycle=cyc.name, item="FCX Cabbage - Gloria",
			qty=10, uom="Kg", harvest_date=today())
		self.assertFalse(frappe.db.get_value("Production Crop Cycle", cyc.name, "field_crop"))
		add_field_crops.execute()
		cabbage = frappe.db.get_value("Production Field Crop", {"product": "FCX Cabbage"}, ["name", "harvest_uom"], as_dict=True)
		potato = frappe.db.get_value("Production Field Crop", {"product": "FCX Potatoes"}, ["name", "harvest_uom"], as_dict=True)
		self.assertEqual((cabbage.name, cabbage.harvest_uom), (CAB, "Pieces"))
		self.assertEqual((potato.name, potato.harvest_uom), (POT, "Kg"))
		self.assertEqual(frappe.db.get_value("Production Variety", self.gloria, "field_crop"), CAB)
		self.assertEqual(frappe.db.get_value("Production Variety", self.shangi, "field_crop"), POT)
		self.assertEqual(frappe.db.get_value("Production Crop Cycle", cyc.name, "field_crop"), CAB)
		self.assertEqual(frappe.db.get_value("Production Harvest", harvest.name, "field_crop"), CAB)
		# the past harvest keeps the unit it was recorded in
		self.assertEqual(frappe.db.get_value("Production Harvest", harvest.name, "uom"), "Kg")
		# a single-product section gets no crop from this patch (crop_hierarchy handles Avocado)
		self.assertFalse(frappe.db.get_value("Production Variety", self.lone, "field_crop"))
		before = frappe.db.count("Production Field Crop")
		add_field_crops.execute()
		self.assertEqual(frappe.db.count("Production Field Crop"), before)
		self.assertEqual(field_crops.link_records().get("Production Crop Cycle", 0), 0)

	def test_patch_on_a_site_without_a_mixed_section(self):
		self._legacy_state()
		frappe.db.set_value("Production Variety", self.shangi, "product", "FCX Cabbage")
		field_crops.create_from_varieties()
		self.assertFalse(field_crops.crops_of(self.section.name))  # one product only: no crop for this section
		self.assertNotIn("FCX Cabbage", frappe.get_all("Production Field Crop", pluck="product"))
		add_field_crops.execute()  # must not raise (crops are global now, so a same-named crop elsewhere may be linked)

	# -- cycles ----------------------------------------------------------------------------

	def test_cycle_takes_the_crop_of_its_variety(self):
		add_field_crops.execute()
		cyc = self._cycle(self.unit, self.shangi)
		self.assertEqual(cyc.field_crop, POT)
		self.assertEqual(frappe.db.get_value("Production Crop Cycle", cyc.name, "field_crop"), POT)

	def test_cycle_needs_a_crop_when_the_section_has_crops(self):
		add_field_crops.execute()  # the section now has crops through its varieties
		_make("Production Field Crop", crop_name="FCX Third", crop_group="Vegetable Crops", harvest_uom="Kg")
		_make("Production Variety", variety_name="FCX Third V", crop=self.section.name, field_crop="FCX Third", item="FCX Lone")  # a third crop: still several
		frappe.db.set_value("Production Variety", self.gloria, "field_crop", None)
		with self.assertRaises(frappe.ValidationError):
			self._cycle(self.unit, self.gloria)
		# a section without Field Crops is unaffected
		_make("Production Crop Cycle", unit=self.single_unit, crop=self.single.name, variety=self.lone, cycle_type="Season",
			start_date=today(), status="Active")

	def test_cycle_by_item_gets_its_crop(self):
		add_field_crops.execute()
		cyc = cycle_setup.create_cycle({"unit": self.unit2, "item": "FCX Potatoes - Shangi", "existing": 1, "planting_date": add_days(today(), -30)})
		self.assertEqual(frappe.db.get_value("Production Crop Cycle", cyc["name"], "field_crop"), POT)

	def test_create_cycle_checks_variety_against_the_chosen_crop(self):
		add_field_crops.execute()
		with self.assertRaises(frappe.ValidationError):
			cycle_setup.create_cycle({"unit": self.unit, "variety": self.gloria, "field_crop": POT, "start_date": today()})
		r = cycle_setup.create_cycle({"unit": self.unit, "variety": self.gloria, "field_crop": CAB, "start_date": today()})
		self.assertEqual(frappe.db.get_value("Production Crop Cycle", r["name"], "field_crop"), CAB)

	def test_import_template_and_rows_have_a_crop_column(self):
		add_field_crops.execute()
		self.assertIn("crop", cycle_setup.template_columns(self.section.name))
		self.assertNotIn("crop", cycle_setup.template_columns(self.single.name))
		rows = [
			{"block": self.unit, "crop": CAB, "variety": "FCX Gloria", "planting_date": str(add_days(today(), -20))},
			{"block": self.unit, "crop": POT, "variety": "FCX Gloria", "planting_date": str(add_days(today(), -20))},
			{"block": self.unit, "crop": "Turnip", "variety": "FCX Gloria", "planting_date": str(add_days(today(), -20))},
			{"block": self.unit, "variety": "FCX Shangi", "planting_date": str(add_days(today(), -20))},
		]
		out = cycle_setup.check_rows(self.section.name, rows)
		self.assertEqual((out[0]["errors"], out[0]["values"]["field_crop"]), ([], CAB))
		self.assertTrue(out[1]["errors"])
		self.assertTrue(out[2]["errors"])
		self.assertEqual((out[3]["errors"], out[3]["values"]["field_crop"]), ([], POT))

	# -- harvests and reports --------------------------------------------------------------

	def test_harvest_follows_the_crop_and_its_unit(self):
		add_field_crops.execute()
		cyc = self._cycle(self.unit, self.gloria)
		h = _make("Production Harvest", unit=self.unit, cycle=cyc.name, item="FCX Cabbage - Gloria", qty=1200, uom="Kg",
			harvest_date=today())
		self.assertEqual((h.field_crop, h.uom), (CAB, "Pieces"))
		cyc2 = self._cycle(self.unit2, self.shangi)
		h2 = _make("Production Harvest", unit=self.unit2, cycle=cyc2.name, qty=3400, harvest_date=today(), uom="Kg")
		self.assertEqual((h2.field_crop, h2.uom), (POT, "Kg"))
		# with no cycle given, the block's current crop is used
		h3 = _make("Production Harvest", unit=self.unit2, qty=5, uom="Kg", harvest_date=today())
		self.assertEqual(h3.field_crop, POT)

	def test_reports_split_by_crop_and_unit(self):
		add_field_crops.execute()
		c1, c2 = self._cycle(self.unit, self.gloria), self._cycle(self.unit2, self.shangi)
		_make("Production Harvest", unit=self.unit, cycle=c1.name, qty=1200, uom="Pieces", harvest_date=today())
		_make("Production Harvest", unit=self.unit2, cycle=c2.name, qty=3400, uom="Kg", harvest_date=today())
		_make("Buyer Commitment", crop=self.section.name, item="FCX Potatoes", committed_qty=900, uom="Kg", week_start=today(),
			customer=frappe.db.get_value("Customer", {}, "name"), status="Open") if frappe.db.exists("Customer", {}) else None
		lines = {(r["field_crop"], r["uom"]): r["qty"] for r in analytics.harvest_by_field_crop(self.section.name, add_days(today(), -1), today())}
		self.assertEqual(lines[(CAB, "Pieces")], 1200)
		self.assertEqual(lines[(POT, "Kg")], 3400)
		fb = {(r["field_crop"], r["uom"]): r for r in analytics.forecast_by_crop(self.section.name, add_days(today(), -7), today())}
		self.assertEqual(fb[(CAB, "Pieces")]["actual"], 1200)
		self.assertEqual(fb[(POT, "Kg")]["actual"], 3400)
		self.assertEqual(analytics.forecast_by_crop(self.single.name, add_days(today(), -7), today()), [])
		ov = analytics.overview(self.section.name, True)
		self.assertEqual({(r["field_crop"], r["uom"]) for r in ov["harvest_by_crop"]}, {(CAB, "Pieces"), (POT, "Kg")})

	def test_plan_tasks_carry_the_crop_label(self):
		add_field_crops.execute()
		cyc = self._cycle(self.unit, self.gloria)
		rows = [frappe._dict(cycle=cyc.name), frappe._dict(cycle=None)]
		field_crops.annotate_cycles(rows)
		self.assertEqual(rows[0].crop_label, f"{CAB} (FCX Gloria)")
		self.assertIsNone(rows[1].crop_label)

	# -- crop logic: sections, sub-crops, groups -------------------------------------------

	def _two_crops(self):
		_make("Production Field Crop", crop_name="FCX Alpha", crop_group="Vegetable Crops", harvest_uom="Kg")
		_make("Production Field Crop", crop_name="FCX Beta", crop_group="Vegetable Crops", harvest_uom="Kg")
		frappe.db.set_value("Production Variety", self.gloria, "field_crop", "FCX Alpha")
		frappe.db.set_value("Production Variety", self.shangi, "field_crop", "FCX Beta")

	def test_single_crop_section_fills_silently(self):
		_make("Production Field Crop", crop_name="FCX Solo", crop_group="Fruit Crops", harvest_uom="Kg")
		frappe.db.set_value("Production Variety", self.lone, "field_crop", "FCX Solo")
		cyc = _make("Production Crop Cycle", unit=self.single_unit, crop=self.single.name, variety=self.lone, cycle_type="Season",
			start_date=today(), status="Active")
		self.assertEqual(cyc.field_crop, "FCX Solo")
		self.assertFalse(field_crops.has_field_crops(self.single.name))
		self.assertEqual(field_crops.only_crop(self.single.name), "FCX Solo")

	def test_fv_section_requires_crop(self):
		self._two_crops()
		frappe.db.set_value("Production Variety", self.gloria, "field_crop", None)
		frappe.db.set_value("Production Variety", self.lone, "crop", self.section.name)  # a third variety, third crop
		_make("Production Field Crop", crop_name="FCX Third", crop_group="Vegetable Crops", harvest_uom="Kg")
		frappe.db.set_value("Production Variety", self.lone, "field_crop", "FCX Third")
		self.assertTrue(field_crops.has_field_crops(self.section.name))
		with self.assertRaises(frappe.ValidationError):
			self._cycle(self.unit, self.gloria)

	def test_variety_needs_sub_crop_when_crop_has_them(self):
		_make("Production Field Crop", crop_name="FCX Gamma", crop_group="Fruit Crops", harvest_uom="Kg")
		_make("Production Sub Crop", sub_crop_name="FCX Gamma Sub", field_crop="FCX Gamma")
		v = frappe.get_doc({"doctype": "Production Variety", "variety_name": "FCX Gamma V", "crop": self.single.name, "item": "FCX Lone",
			"field_crop": "FCX Gamma"})
		with self.assertRaises(frappe.ValidationError):
			v.insert()
		v.sub_crop = "FCX Gamma Sub"
		v.insert()
		self.assertEqual(field_crops.list_for(self.single.name)[0]["sub_crops"][0]["name"], "FCX Gamma Sub")

	def test_sub_crop_of_other_crop_refused(self):
		_make("Production Field Crop", crop_name="FCX Gamma", crop_group="Fruit Crops", harvest_uom="Kg")
		_make("Production Field Crop", crop_name="FCX Delta", crop_group="Fruit Crops", harvest_uom="Kg")
		_make("Production Sub Crop", sub_crop_name="FCX Delta Sub", field_crop="FCX Delta")
		v = frappe.get_doc({"doctype": "Production Variety", "variety_name": "FCX Gamma V2", "crop": self.single.name, "item": "FCX Lone",
			"field_crop": "FCX Gamma", "sub_crop": "FCX Delta Sub"})
		with self.assertRaises(frappe.ValidationError):
			v.insert()

	def test_record_disagreeing_with_variety_refused(self):
		self._two_crops()
		with self.assertRaises(frappe.ValidationError):
			self._cycle(self.unit, self.gloria, field_crop="FCX Beta")
		cyc = self._cycle(self.unit, self.gloria)
		self.assertEqual(cyc.field_crop, "FCX Alpha")

	def test_group_totals_per_unit(self):
		rows = [{"field_crop": "Onion", "uom": "Kg", "qty": 10}, {"field_crop": "Potato", "uom": "Kg", "qty": 5},
			{"field_crop": "Cabbage", "uom": "Pieces", "qty": 3}]
		out = field_crops.group_totals(rows)
		self.assertEqual(sorted((r["crop_group"], r["uom"], r["qty"]) for r in out),
			[("Vegetable Crops", "Kg", 15), ("Vegetable Crops", "Pieces", 3)])

	def test_harvest_uom_prefers_sub_crop(self):
		_make("Production Field Crop", crop_name="FCX Eps", crop_group="Fruit Crops", harvest_uom="Kg")
		_make("Production Sub Crop", sub_crop_name="FCX Eps Sub", field_crop="FCX Eps", harvest_uom="Pieces")
		self.assertEqual(field_crops.harvest_uom("FCX Eps", sub_crop="FCX Eps Sub"), "Pieces")
		self.assertEqual(field_crops.harvest_uom("FCX Eps"), "Kg")
		self.assertEqual(field_crops.harvest_uom(None, default="Box"), "Box")
