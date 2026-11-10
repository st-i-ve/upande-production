import frappe
from frappe.tests import IntegrationTestCase

from upande_production.patches import rename_value_adder_to_casual_labour as patch


# Named test_zz_ so it runs last: the patch commits, which must not persist earlier tests' data.
class TestCasualLabourRename(IntegrationTestCase):
	# The doctype round trip (rename back, run the patch) is verified by hand on a migrated site: rename_doc
	# does DDL and moves folders in developer mode, which is not safe inside the shared test transaction.
	def test_patch_is_idempotent(self):
		before = frappe.db.count("Casual Labour Work")
		patch.execute()
		self.assertTrue(frappe.db.exists("DocType", "Casual Labour Work"))
		self.assertFalse(frappe.db.exists("DocType", "Value Adder Work"))
		self.assertEqual(frappe.db.count("Casual Labour Work"), before)

	def test_designation_renamed(self):
		if frappe.db.exists("Designation", "Casual Labourer"):
			frappe.delete_doc("Designation", "Casual Labourer", force=True)
		frappe.get_doc({"doctype": "Designation", "designation_name": "Value Adder"}).insert()
		patch.execute()
		self.assertTrue(frappe.db.exists("Designation", "Casual Labourer"))
		self.assertFalse(frappe.db.exists("Designation", "Value Adder"))

	def test_old_api_paths_still_resolve(self):
		overrides = frappe.get_hooks("override_whitelisted_methods")
		for old in (
			"upande_production.mobile.api.productionListValueAdders",
			"upande_production.api.production.list_value_adders",
			"upande_production.api.production.value_adder_summary",
			"upande_production.api.overview.value_adder_detail",
		):
			target = overrides[old][-1]
			fn = frappe.get_attr(target)
			self.assertIn(fn, frappe.whitelisted)
