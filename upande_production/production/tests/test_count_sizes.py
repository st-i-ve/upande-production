"""Count size bands: gaps and overlaps are warned about, never blocked, and a weight in a gap names its neighbours."""

import unittest
from unittest import mock

import frappe
from frappe.tests import IntegrationTestCase

from upande_production.production.logic import count_sizes as cs


def rows(*t):
	return [{"count": c, "min_g": lo, "max_g": hi} for c, lo, hi in t]


GOOD = rows((14, 275, 317), (16, 242, 275), (18, 216, 242), (20, 196, 216))


class TestBandIssues(unittest.TestCase):
	def test_contiguous_bands_are_clean_whatever_the_row_order(self):
		self.assertEqual(cs.band_issues(GOOD), [])
		self.assertEqual(cs.band_issues(list(reversed(GOOD))), [])

	def test_gap(self):
		(i,) = cs.band_issues(rows((16, 242, 275), (18, 216, 240)))
		self.assertEqual((i["kind"], i["lo"], i["hi"]), ("gap", 240, 242))
		self.assertEqual(i["message"], "Fruit between 240 g and 242 g has no count size")

	def test_overlap(self):
		(i,) = cs.band_issues(rows((16, 242, 275), (18, 216, 244)))
		self.assertEqual(i["kind"], "overlap")
		self.assertEqual(i["message"], "Counts 16 and 18 both cover 242–244 g")

	def test_min_not_below_max_duplicate_and_order(self):
		self.assertEqual([i["kind"] for i in cs.band_issues(rows((16, 275, 242)))], ["invalid"])
		self.assertIn("duplicate", [i["kind"] for i in cs.band_issues(rows((16, 242, 275), (16, 216, 242)))])
		self.assertEqual([i["kind"] for i in cs.band_issues(rows((16, 216, 242), (18, 242, 275)))], ["order"])

	def test_close_gaps_snaps_max_to_the_bigger_fruit_min(self):
		fixed = cs.close_gaps(rows((16, 242, 275), (18, 216, 240), (20, 196, 220)))
		self.assertEqual(fixed, [(16, 242, 275), (18, 216, 242), (20, 196, 216)])
		self.assertEqual(cs.band_issues(rows(*fixed)), [])


class TestCountForWeight(unittest.TestCase):
	def test_weight_picks_its_band_and_none_in_a_gap(self):
		crop = {"count_sizes": rows((16, 242, 275), (18, 216, 240))}
		self.assertEqual(cs.count_for_weight(crop, 250), 16)
		self.assertEqual(cs.count_for_weight(crop, 242), 16)
		self.assertEqual(cs.count_for_weight(crop, 230), 18)
		self.assertIsNone(cs.count_for_weight(crop, 241))
		self.assertIsNone(cs.count_for_weight(crop, 400))

	def test_warning_names_the_nearest_counts(self):
		crop = {"count_sizes": rows((16, 242, 275), (18, 216, 240))}
		self.assertIsNone(cs.weight_warning(crop, 250))
		w = cs.weight_warning(crop, 241)
		self.assertIn("241 g", w)
		self.assertIn("count 16 and count 18", w)


class TestProductionCropValidate(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint("count_size_validate")
		self.addCleanup(frappe.db.rollback, save_point="count_size_validate")

	def crop(self, bands):
		doc = frappe.get_doc({"doctype": "Production Crop", "crop_name": "Zz Band Test", "crop_key": "zzband", "unit_label": "Block"})
		for c, lo, hi in bands:
			doc.append("count_sizes", {"count": c, "min_g": lo, "max_g": hi})
		return doc

	def test_a_gap_is_a_warning_not_an_error(self):
		doc = self.crop([(16, 242, 275), (18, 216, 240)])
		with mock.patch.object(frappe, "msgprint") as m:
			doc.insert()
		self.assertTrue(frappe.db.exists("Production Crop", doc.name))
		self.assertIn("has no count size", m.call_args.args[0])
		self.assertEqual(m.call_args.kwargs["indicator"], "orange")

	def test_clean_bands_say_nothing(self):
		with mock.patch.object(frappe, "msgprint") as m:
			self.crop([(16, 242, 275), (18, 216, 242)]).insert()
		m.assert_not_called()


class TestMaturityWeight(IntegrationTestCase):
	def test_weight_in_a_gap_returns_a_warning(self):
		from upande_production.api import avocadomaturity
		with mock.patch("upande_production.api.avocado_model.crop_name", return_value="X"), \
				mock.patch.object(cs, "_band_list", return_value=cs._clean(rows((16, 242, 275), (18, 216, 240)))):
			r = avocadomaturity.count_for_weight(241)
		self.assertIsNone(r["count"])
		self.assertIn("nearest", r["warning"])
