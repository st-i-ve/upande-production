"""The summer-flowers half of upande_summer_flowers now living in production."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt

from upande_production import hooks
from upande_production.patches import take_over_from_upande_summer_flowers as patch
from upande_production.summer_flowers import planning, protocol_math


class V:
	"""Stands in for a Crop Protocol Version: the arithmetic only reads its fields."""

	def __init__(self, **kw):
		self.__dict__.update(kw)


class TestProtocolMath(IntegrationTestCase):
	def test_bed_size_is_zero_rather_than_a_guess(self):
		self.assertEqual(protocol_math.bed_sqm(V(sqm_net_per_bed=50)), 50)
		# a minimum planting area of one square metre is a field nobody filled in, not a bed
		self.assertEqual(protocol_math.bed_sqm(V(sqm_net_per_bed=0, min_planting_area_sqm=1)), 0.0)
		self.assertEqual(protocol_math.bed_sqm(V(sqm_net_per_bed=0, min_planting_area_sqm=40)), 40)

	def test_what_grades_out_and_what_takes(self):
		self.assertAlmostEqual(protocol_math.saleable(V(cutting_reject_pct=10, reject_pct=0)), 0.9)
		self.assertAlmostEqual(protocol_math.saleable(V(cutting_reject_pct=10, reject_pct=10)), 0.81)
		self.assertEqual(protocol_math.saleable(V()), 1.0)
		self.assertEqual(protocol_math.establishment(V(field_establishment_pct=95)), 0.95)
		self.assertEqual(protocol_math.establishment(V()), 1.0)
		self.assertEqual(protocol_math.plants_to_plant(V(field_establishment_pct=50), 100), 200)

	def test_a_planting_is_sized_in_whole_beds_but_to_the_minimum_area(self):
		v = V(plants_per_sqm_net=16, min_planting_area_sqm=10, sqm_net_per_bed=50, plants_per_bed=800)
		beds, plants, area = protocol_math.size_planting(v, 1000)
		self.assertEqual(area, 70)          # 1000 plants at 16/m2 is 62.5 m2, rounded up to units of 10
		self.assertEqual(plants, 1120)
		self.assertEqual(beds, 2)           # and held in whole beds
		self.assertEqual(protocol_math.size_planting(V(), 100, min_beds=3), (3, 0, 0.0))


class TestWeekHelpers(IntegrationTestCase):
	def test_iso_weeks(self):
		import datetime

		self.assertEqual(planning.iso_year_week(datetime.date(2026, 11, 4)), (2026, 45))
		self.assertEqual(planning.iso_monday(2026, 45), datetime.date(2026, 11, 2))
		self.assertEqual(planning.add_weeks(2026, 52, 2)[0], 2027)


class TestWiring(IntegrationTestCase):
	def test_every_old_summer_flowers_path_resolves(self):
		"""upande_summer_flowers.* whitelisted paths keep working: each maps to a real function."""
		missing = []
		for old, new in hooks.SUMMER_FLOWERS_OVERRIDES.items():
			self.assertTrue(old.startswith("upande_summer_flowers."))
			try:
				frappe.get_attr(new)
			except Exception as e:  # noqa: BLE001
				missing.append((new, str(e)[:80]))
		self.assertEqual(missing, [])

	def test_hooks_point_at_real_code(self):
		for dt, evs in hooks.doc_events.items():
			for ev, paths in evs.items():
				for p in ([paths] if isinstance(paths, str) else paths):
					frappe.get_attr(p)
		for p in hooks.override_doctype_class.values():
			frappe.get_attr(p)
		for p in [hooks.before_migrate, *hooks.after_migrate]:
			frappe.get_attr(p)

	def test_no_summer_flowers_imports_remain(self):
		import pathlib

		root = pathlib.Path(frappe.get_app_path("upande_production"))
		hits = [str(f) for f in list((root / "summer_flowers").rglob("*.py")) + list((root / "www").glob("*.py"))
			if "upande_summer_flowers" in f.read_text() and "SUMMER_FLOWERS" not in f.read_text()]
		self.assertEqual(hits, [])


class TestOwnershipPatch(IntegrationTestCase):
	def test_patch_leaves_other_modules_alone_and_is_a_noop_without_summer_flowers(self):
		before = frappe.db.sql("select name, module, custom from tabDocType where module != 'Summer Flowers' order by name")
		patch.execute()
		patch.execute()  # idempotent
		after = frappe.db.sql("select name, module, custom from tabDocType where module != 'Summer Flowers' order by name")
		self.assertEqual(before, after)

	def test_it_only_names_doctypes_this_app_ships(self):
		for name in patch.DOCTYPES:
			self.assertTrue(frappe.db.exists("DocType", name), name)
			self.assertEqual(frappe.db.get_value("DocType", name, "module"), "Crop Production")
			self.assertEqual(flt(frappe.db.get_value("DocType", name, "custom")), 0)
