import frappe
from frappe.tests import IntegrationTestCase

from upande_production.patches import rename_production_crop_to_section as patch


class TestRenameProductionCropToSection(IntegrationTestCase):
	"""The doctype is Production Section; the patch is a no-op once it ran and fixes names stored as values."""

	def test_doctype_is_renamed_and_links_follow(self):
		self.assertFalse(frappe.db.exists("DocType", "Production Crop"))
		self.assertEqual(frappe.db.get_value("DocType", "Production Section", "module"), "Production")
		self.assertEqual(frappe.get_meta("Production Unit").get_field("crop").options, "Production Section")

	def test_execute_is_idempotent(self):
		before = frappe.db.count("Production Section")
		patch.execute()
		patch.execute()
		self.assertEqual(frappe.db.count("Production Section"), before)
		self.assertFalse(frappe.db.exists("DocType", "Production Crop"))

	def test_stored_doctype_names_are_fixed(self):
		c = frappe.get_doc({"doctype": "Comment", "comment_type": "Comment", "reference_doctype": "Production Section",
			"reference_name": "Phases", "content": "t"}).insert(ignore_permissions=True)
		frappe.db.set_value("Comment", c.name, "reference_doctype", patch.OLD)
		patch.fix_stored_names()
		self.assertEqual(frappe.db.get_value("Comment", c.name, "reference_doctype"), patch.NEW)

	def test_copy_rows_skips_a_missing_old_table(self):
		self.assertEqual(patch.copy_rows(), 0)
