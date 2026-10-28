import frappe
from frappe.tests import IntegrationTestCase

from upande_production.api import production as api


class TestBootstrapShape(IntegrationTestCase):
	def test_crops_carry_dry_matter_settings(self):
		frappe.set_user("Administrator")
		if not frappe.db.exists("UOM", "Kg"):
			frappe.get_doc({"doctype": "UOM", "uom_name": "Kg"}).insert()
		crop = frappe.get_doc({"doctype": "Production Crop", "crop_name": "BS DM Crop", "crop_key": "bs-dm",
			"unit_label": "Block", "yield_uom": "Kg", "dry_matter_testing": 1, "dry_matter_on": "Fruit",
			"dry_matter_target_pct": 21.5}).insert()
		row = next(c for c in api.get_bootstrap()["crops"] if c["name"] == crop.name)
		self.assertEqual(row["dry_matter_testing"], 1)
		self.assertEqual(row["dry_matter_on"], "Fruit")
		self.assertEqual(row["dry_matter_target_pct"], 21.5)
