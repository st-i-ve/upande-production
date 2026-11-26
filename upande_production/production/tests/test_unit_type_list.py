import frappe
from frappe.tests import IntegrationTestCase

from upande_production.patches import unit_type_list
from upande_production.production.doctype.production_crop.production_crop import slugify


class TestUnitTypeList(IntegrationTestCase):
	"""Crop labels and a block's type are a pick-list; crop key and icon are filled safely. Rolls back."""

	def test_slug(self):
		self.assertEqual(slugify("Passion Fruit"), "passion-fruit")
		for k in ("avocado", "fruits-vegetables", "apiary", "aquaculture"):
			self.assertEqual(slugify(k), k)
		self.assertEqual(slugify("  Hello__World! "), "hello-world")
		self.assertEqual(slugify(None), "")

	def test_crop_key_filled_and_normalised(self):
		doc = frappe.get_doc({"doctype": "Production Crop", "crop_name": "Zz Dragon Fruit", "unit_label": "Block"}).insert()
		self.assertEqual(doc.crop_key, "zz-dragon-fruit")
		doc.crop_key = "Zz Other Key"
		doc.save()
		self.assertEqual(doc.crop_key, "zz-other-key")

	def test_label_must_be_in_list(self):
		doc = frappe.get_doc({"doctype": "Production Crop", "crop_name": "Zz Bad Label", "crop_key": "zz-bad", "unit_label": "Block 1"})
		self.assertRaises(frappe.LinkValidationError, doc.insert)

	def test_patch_maps_labels(self):
		name = frappe.generate_hash(length=6)
		frappe.db.sql("insert into `tabProduction Crop` (name, crop_name, crop_key, unit_label, parent_unit_label, sub_unit_label, icon_key, creation, modified, owner, modified_by, docstatus) "
			"values (%s, %s, %s, 'Block 1', 'Pivot 1', 'Raised Bed 3', 'banana', now(), now(), 'Administrator', 'Administrator', 0)",
			(name, name, "Zz Key " + name))
		unit_type_list.execute()
		row = frappe.db.get_value("Production Crop", name, ["unit_label", "parent_unit_label", "sub_unit_label", "icon_key", "crop_key"], as_dict=True)
		self.assertEqual(row.unit_label, "Block")
		self.assertEqual(row.parent_unit_label, "Pivot")
		self.assertEqual(row.sub_unit_label, "Raised Bed")
		self.assertTrue(frappe.db.exists("Production Unit Type", "Raised Bed"))
		self.assertFalse(row.icon_key)
		self.assertEqual(row.crop_key, "zz-key-" + name.lower())
		unit_type_list.execute()  # idempotent
		self.assertEqual(frappe.db.get_value("Production Crop", name, "unit_label"), "Block")
