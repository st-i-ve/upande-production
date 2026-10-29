"""Dry matter per variety and stage: the variety overrides the crop, the test records the cycle's stage,
and a block is due for sampling when it is in or past the variety's sampling stage with no recent test."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from upande_production.api import drymatter, production as prod_api
from upande_production.production.logic import drymatter as dm


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


def _stages(*rows):
	return [{"stage": n, "start_day": s, "length_days": ln, "is_harvest": 1 if h else 0} for n, s, ln, h in rows]


class TestDryMatterVariety(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		# the crop default is off: each variety decides
		cls.crop = _make("Production Crop", crop_name="DMV Crop", crop_key="dmv-crop", unit_label="Block", yield_uom="Kg")
		cls.on_crop = _make("Production Crop", crop_name="DMV On", crop_key="dmv-on", unit_label="Block", yield_uom="Kg",
			dry_matter_testing=1, dry_matter_on="Fruit", dry_matter_target_pct=24)
		for n in ("DMV Onion", "DMV Passion", "DMV Plain"):
			if not frappe.db.exists("Item", n):
				_make("Item", item_code=n, item_name=n, item_group="All Item Groups", stock_uom="Kg", is_stock_item=1)
		st = _stages(("Planting", 0, 10, 0), ("Vegetative", 10, 20, 0), ("Bulb bulking", 30, 40, 0), ("Harvest", 70, 20, 1))
		cls.onion = _make("Production Variety", variety_name="DMV Red", crop=cls.crop.name, item="DMV Onion",
			days_to_first_harvest=70, harvest_window_days=20, stages=st, dry_matter_testing="Yes", dry_matter_on="Bulb",
			dry_matter_target_pct=11, dry_matter_from_stage="Bulb bulking")
		cls.passion = _make("Production Variety", variety_name="DMV Purple", crop=cls.crop.name, item="DMV Passion",
			days_to_first_harvest=70, harvest_window_days=20, stages=st, dry_matter_testing="No")
		cls.plain = _make("Production Variety", variety_name="DMV Plain", crop=cls.on_crop.name, item="DMV Plain",
			days_to_first_harvest=70, harvest_window_days=20, stages=st)
		cls.off_here = _make("Production Variety", variety_name="DMV Off", crop=cls.on_crop.name, item="DMV Plain",
			days_to_first_harvest=70, harvest_window_days=20, stages=st, dry_matter_testing="No")
		cls.units = {}
		for n in ("A", "B", "C", "D"):
			cls.units[n] = _make("Production Unit", unit_name=f"DMV {n}", crop=cls.crop.name, unit_type="Orchard Block",
				company=cls.company, area_ha=1).name

	def setUp(self):
		frappe.db.savepoint("dmv")  # every test starts from the class fixtures

	def tearDown(self):
		frappe.db.rollback(save_point="dmv")

	def _cycle(self, unit, variety, ago):
		return _make("Production Crop Cycle", unit=unit, crop=self.crop.name, variety=variety.name, status="Active",
			start_date=add_days(today(), -ago)).name

	def _test(self, unit, date=None, pcts=(11, 12), **kw):
		return {"unit": unit, "crop": self.crop.name, "test_date": date or today(),
			"samples": [{"sample_no": i + 1, "dry_matter_pct": p} for i, p in enumerate(pcts)], **kw}

	def test_rules_variety_overrides_crop(self):
		self.assertEqual(dm.rules_for("DMV Red", self.crop.name),
			{"testing": 1, "on": "Bulb", "target": 11.0, "from_stage": "Bulb bulking"})
		self.assertEqual(dm.rules_for("DMV Purple", self.crop.name)["testing"], 0)
		self.assertEqual(dm.rules_for("DMV Plain", self.on_crop.name),  # silent variety: the crop's default
			{"testing": 1, "on": "Fruit", "target": 24.0, "from_stage": None})
		self.assertEqual(dm.rules_for("DMV Off", self.on_crop.name)["testing"], 0)  # variety says No under an on crop

	def test_page_gate_follows_varieties(self):
		self.assertTrue(dm.crop_tests_dry_matter(self.crop.name))  # crop off, one variety Yes
		self.assertTrue(dm.crop_tests_dry_matter(self.on_crop.name))
		boot = {c["name"]: c for c in prod_api.get_bootstrap()["crops"]}
		self.assertEqual(boot[self.crop.name]["dry_matter_testing"], 1)

	def test_test_takes_variety_part_target_and_cycle_stage(self):
		cycle = self._cycle(self.units["A"], self.onion, 40)  # day 40: Bulb bulking
		r = drymatter.save_test(self._test(self.units["A"], pcts=(10, 13)))
		doc = frappe.get_doc("Dry Matter Test", r["name"])
		self.assertEqual((doc.cycle, doc.variety), (cycle, "DMV Red"))  # from the cycle at the test date
		self.assertEqual((doc.tested_on, doc.target_pct, doc.stage), ("Bulb", 11, "Bulb bulking"))
		self.assertTrue(r["ready"])  # 11.5 against 11
		# an earlier test date: the cycle was in an earlier stage
		old = drymatter.save_test(self._test(self.units["A"], date=add_days(today(), -35)))
		self.assertEqual(frappe.db.get_value("Dry Matter Test", old["name"], "stage"), "Planting")  # day 5
		rows = drymatter.list_tests(self.crop.name, self.units["A"])["rows"]
		self.assertEqual({r["stage"] for r in rows}, {"Bulb bulking", "Planting"})

	def test_variety_off_refuses_a_test(self):
		self._cycle(self.units["B"], self.passion, 40)
		doc = frappe.get_doc({"doctype": "Dry Matter Test", **self._test(self.units["B"])})
		with self.assertRaises(frappe.ValidationError):
			doc.insert()

	def test_sampling_stage_must_be_a_stage_of_the_variety(self):
		v = frappe.get_doc("Production Variety", "DMV Red")
		v.dry_matter_from_stage = "No such stage"
		with self.assertRaises(frappe.ValidationError):
			v.save()

	def test_due_rows_states(self):
		U = self.units
		self._cycle(U["A"], self.onion, 40)  # in Bulb bulking, never tested -> due
		self._cycle(U["B"], self.onion, 12)  # Vegetative, before the sampling stage -> not yet
		self._cycle(U["C"], self.onion, 45)  # in Bulb bulking, tested 2 days ago -> recent
		self._cycle(U["D"], self.passion, 45)  # passion is off -> not listed
		drymatter.save_test(self._test(U["C"], date=add_days(today(), -2)))
		res = drymatter.list_due(self.crop.name)
		by = {r["unit"]: r for r in res["rows"]}
		self.assertEqual(res["retest_days"], 7)
		self.assertEqual(set(by), {U["A"], U["B"], U["C"]})
		self.assertEqual((by[U["A"]]["state"], by[U["A"]]["stage"], by[U["A"]]["from_stage"]), ("due", "Bulb bulking", "Bulb bulking"))
		self.assertEqual(by[U["B"]]["state"], "not_yet")
		self.assertEqual((by[U["C"]]["state"], by[U["C"]]["days_since"], by[U["C"]]["target_pct"]), ("recent", 2, 11))
		self.assertEqual(res["rows"][0]["unit"], U["A"])  # due first
		self.assertEqual(res["counts"], {"due": 1, "recent": 1, "not_yet": 1})

	def test_due_again_after_the_retest_window_and_setting(self):
		U = self.units
		self._cycle(U["A"], self.onion, 40)
		drymatter.save_test(self._test(U["A"], date=add_days(today(), -5)))
		self.assertEqual(drymatter.list_due(self.crop.name)["rows"][0]["state"], "recent")
		frappe.db.set_single_value("Production Settings", "dry_matter_retest_days", 3)
		res = drymatter.list_due(self.crop.name)
		self.assertEqual((res["retest_days"], res["rows"][0]["state"]), (3, "due"))
		frappe.db.set_single_value("Production Settings", "dry_matter_retest_days", 7)

	def test_no_sampling_stage_means_due_from_the_start(self):
		unit = _make("Production Unit", unit_name="DMV E", crop=self.on_crop.name, unit_type="Orchard Block",
			company=self.company, area_ha=1).name
		_make("Production Crop Cycle", unit=unit, crop=self.on_crop.name, variety="DMV Plain", status="Active",
			start_date=add_days(today(), -3))
		rows = {r["unit"]: r for r in dm.due_rows(self.on_crop.name)["rows"]}
		self.assertEqual((rows[unit]["state"], rows[unit]["target_pct"], rows[unit]["on"]), ("due", 24, "Fruit"))

	def test_retired_blocks_are_not_listed(self):
		U = self.units
		self._cycle(U["A"], self.onion, 40)
		frappe.db.set_value("Production Unit", U["A"], "status", "Retired")
		self.assertEqual(drymatter.list_due(self.crop.name)["rows"], [])
		self.assertEqual(drymatter.list_tests(self.crop.name)["rows"], [])

	def test_mobile_read_endpoint_carries_the_stage(self):
		from types import SimpleNamespace
		from unittest.mock import patch

		from upande_production.mobile import api as mobile

		self._cycle(self.units["A"], self.onion, 40)
		drymatter.save_test(self._test(self.units["A"]))
		frappe.response.pop("data", None)
		with patch.object(frappe.local, "request", SimpleNamespace(get_json=lambda: {"crop": self.crop.name}), create=True):
			mobile.productionDryMatterTests()
		rows = frappe.response["data"]
		self.assertEqual(rows[0]["stage"], "Bulb bulking")

	def test_avocado_block_status(self):
		code = "DMVAVO1"
		unit = self.units["A"]
		frappe.db.set_value("Production Unit", unit, "avocado_block_code", code)
		self._cycle(unit, self.onion, 40)
		s = dm.block_status(code, "DMV Red", None)
		self.assertEqual((s["state"], s["stage"], s["from_stage"], s["testing"]), ("due", "Bulb bulking", "Bulb bulking", True))
		s = dm.block_status(code, "DMV Red", add_days(today(), -2))
		self.assertEqual((s["state"], s["days_since"]), ("recent", 2))
		self.assertEqual(dm.block_status("NOPE", "ZZZ no variety", None)["state"], None)
