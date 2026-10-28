import frappe
from frappe.tests import IntegrationTestCase

from upande_production.production.logic import cycles as cycles_logic


class TestNoCyclesForBeesAndFish(IntegrationTestCase):
	def setUp(self):
		self.crop = "Apiary Test Crop"
		if not frappe.db.exists("Production Crop", self.crop):
			frappe.get_doc({"doctype": "Production Crop", "crop_name": self.crop, "crop_key": "apiary-test",
				"unit_label": "Hive Group", "uses_crop_cycles": 0}).insert()
		self.unit = "Test Hive Group"
		if not frappe.db.exists("Production Unit", self.unit):
			frappe.get_doc({"doctype": "Production Unit", "unit_name": self.unit, "crop": self.crop,
				"unit_type": "Hive Group"}).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_flag(self):
		self.assertFalse(cycles_logic.crop_uses_cycles(self.crop))
		self.assertTrue(cycles_logic.crop_uses_cycles(None))

	def test_cycle_refused(self):
		doc = frappe.get_doc({"doctype": "Production Crop Cycle", "unit": self.unit, "cycle_type": "Hive Season",
			"item": "Honey", "start_date": frappe.utils.today(), "status": "Active"})
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_demo_bees_and_fish_have_no_cycles(self):
		for name in ("Apiary", "Aquaculture"):
			if frappe.db.exists("Production Crop", name):
				self.assertFalse(frappe.db.get_value("Production Crop", name, "uses_crop_cycles"), name)
				self.assertFalse(frappe.db.count("Production Crop Cycle", {"crop": name}), name)
