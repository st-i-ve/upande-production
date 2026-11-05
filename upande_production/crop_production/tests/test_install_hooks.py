"""before_install adopts doctypes another app owned, so the JSON sync does not collide with them."""

from unittest import mock

import frappe
from frappe.tests import IntegrationTestCase

from upande_production import hooks, install


class TestInstallHooks(IntegrationTestCase):
	def setUp(self):
		patcher = mock.patch.object(frappe.db, "commit")
		patcher.start()
		self.addCleanup(patcher.stop)

	def test_hooks_are_registered(self):
		self.assertEqual(hooks.before_install, "upande_production.install.before_install")
		self.assertEqual(hooks.after_install, "upande_production.install.after_install")

	def test_every_listed_patch_is_in_patches_txt_pre_model_sync(self):
		import os
		path = os.path.join(os.path.dirname(install.__file__), "patches.txt")
		pre = open(path).read().split("[post_model_sync]")[0]
		for dotted in install.PRE_MODEL_SYNC_PATCHES:
			self.assertIn(dotted, pre)

	def test_noop_when_nothing_was_owned_elsewhere(self):
		before = frappe.db.sql("select name, module, custom from tabDocType order by name")
		self.assertIsNone(install.before_install())  # False would abort the install
		self.assertEqual(before, frappe.db.sql("select name, module, custom from tabDocType order by name"))

	def test_adopts_custom_doctypes_from_the_old_apps(self):
		agri = "Greenhouse"
		sf = "Planting Calendar"
		for dt in (agri, sf):
			if not frappe.db.exists("DocType", dt):
				self.skipTest(f"{dt} missing")
		frappe.db.set_value("DocType", agri, "module", "Upande Agriculture", update_modified=False)
		frappe.db.set_value("DocType", sf, {"module": "Summer Flowers", "custom": 1}, update_modified=False)
		self.assertIsNone(install.before_install())
		self.assertEqual(frappe.db.get_value("DocType", agri, "module"), "Crop Production")
		self.assertEqual(frappe.db.get_value("DocType", sf, ["module", "custom"]), ("Crop Production", 0))
		self.assertIsNone(install.before_install())  # idempotent

	def test_renames_production_owned_field_activity(self):
		if frappe.db.exists("DocType", "Field Activity"):
			self.skipTest("a Field Activity exists on this site")
		with mock.patch("frappe.rename_doc") as rename, \
				mock.patch.object(frappe.db, "exists", side_effect=lambda dt, n=None: (dt, n) == ("DocType", "Field Activity")), \
				mock.patch.object(frappe.db, "get_value", return_value="Production"):
			from upande_production.patches import rename_field_activity_to_field_operation as p
			p.execute()
		rename.assert_called_once()

	def test_after_install_setup_is_idempotent(self):
		self.assertIsNone(install.after_install())
		self.assertIsNone(install.after_install())
