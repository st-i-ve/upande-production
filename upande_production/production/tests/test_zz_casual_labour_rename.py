import frappe
from frappe.tests import IntegrationTestCase

from upande_production.patches import rename_value_adder_to_casual_labour as patch


# Named test_zz_ so it runs last: the patch commits, which must not persist earlier tests' data.
class TestCasualLabourRename(IntegrationTestCase):
	def test_patch_renames_old_doctype_keeping_rows(self):
		if frappe.conf.developer_mode:
			# in developer mode rename_doc moves the doctype's source folder on disk
			self.skipTest("rename_doc moves the doctype folder in developer mode")
		self.assertTrue(frappe.db.exists("DocType", "Casual Labour Work"))
		before = frappe.db.count("Casual Labour Work")
		# put the site back in its pre-patch state, then run the patch
		frappe.rename_doc("DocType", "Casual Labour Work", "Value Adder Work", force=True, show_alert=False)
		self.assertFalse(frappe.db.exists("DocType", "Casual Labour Work"))
		patch.execute()
		frappe.clear_cache()
		self.assertTrue(frappe.db.exists("DocType", "Casual Labour Work"))
		self.assertFalse(frappe.db.exists("DocType", "Value Adder Work"))
		self.assertEqual(frappe.db.count("Casual Labour Work"), before)

	def test_patch_is_idempotent(self):
		patch.execute()
		self.assertTrue(frappe.db.exists("DocType", "Casual Labour Work"))

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
