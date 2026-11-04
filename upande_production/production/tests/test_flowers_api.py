import frappe
from frappe.tests import IntegrationTestCase

from upande_production.api import flowers


class TestFlowerData(IntegrationTestCase):
	"""flower_data reads greenhouse- and block-based cycles, and works with or without the custom fields."""

	def test_shape_without_data_or_custom_fields(self):
		out = flowers.flower_data("No Such Crop")
		self.assertIn(out["mode"], ("block", "greenhouse"))
		for k in ("units", "cycles", "farms", "totals"):
			self.assertIn(k, out)
		self.assertEqual(out["totals"]["cycles"], len(out["cycles"]))

	def test_unknown_fields_are_never_selected(self):
		got = flowers._fields("Item", ["name", "custom_definitely_not_a_field", "item_name"])
		self.assertEqual(got, ["name", "item_name"])
		self.assertEqual(flowers._fields("No Such DocType", ["name"]), [])

	def test_farm_and_label_helpers(self):
		self.assertEqual(flowers._farm_from_name("CC-Bondet - Block 10A1-2025W39"), "Bondet")
		self.assertEqual(flowers._label("Kariki Thika - Block 9B", "Kariki Thika"), "Block 9B")

	def test_item_names(self):
		item = frappe.db.get_value("Item", {}, ["name", "item_name"], as_dict=True)
		if item:
			self.assertEqual(flowers.item_names([item.name])[item.name], item.item_name)
		self.assertEqual(flowers.item_names([]), {})
