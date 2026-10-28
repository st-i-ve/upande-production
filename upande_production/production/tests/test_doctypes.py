import frappe
from frappe.tests import IntegrationTestCase

DOCTYPES = [
	"Production Crop", "Production Unit", "Production Operation", "Production Protocol",
	"Production Protocol Step", "Production Crop Cycle", "Production Work Plan", "Production Plan Task",
	"Value Adder Work", "Production Harvest", "Yield Sample", "Production Forecast",
	"Production Forecast Week", "Buyer Commitment",
]
ROLES = ["Production Manager", "Production Supervisor", "Production Viewer"]


class TestDoctypes(IntegrationTestCase):
	def test_all_doctypes_exist(self):
		for name in DOCTYPES:
			self.assertTrue(frappe.db.table_exists(name), name)
			self.assertEqual(frappe.get_meta(name).is_submittable, 1 if name == "Value Adder Work" else 0, name)
		self.assertTrue(frappe.get_meta("Production Settings").issingle)
		self.assertTrue(frappe.get_meta("Production Unit").is_tree)
		for role in ROLES:
			self.assertTrue(frappe.db.exists("Role", role), role)
