import frappe
from frappe.tests import IntegrationTestCase

from upande_production.patches import crop_hierarchy
from upande_production.production.logic import field_crops

LINKED = crop_hierarchy.LINKED
MUTARA = {"Avocado": "Fruit Crops", "Passion Fruit": "Fruit Crops", "Onion": "Vegetable Crops", "Potato": "Vegetable Crops",
	"Cabbage": "Vegetable Crops", "Maize": "Fodder Crops"}


def _counts():
	return {
		"groups": frappe.db.count("Production Crop Group"),
		"crops": frappe.db.count("Production Field Crop"),
		**{dt: frappe.db.count(dt, {"field_crop": ("is", "set")}) for dt in LINKED},
	}


class TestCropHierarchyMigration(IntegrationTestCase):
	"""Runs against the migrated mutara.local data; each test rolls back."""

	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint("ch_test")

	def tearDown(self):
		frappe.db.rollback(save_point="ch_test")

	def test_standard_groups_exist(self):
		for name, parent in crop_hierarchy.STANDARD_GROUPS:
			self.assertTrue(frappe.db.exists("Production Crop Group", name), name)
			self.assertEqual(frappe.db.get_value("Production Crop Group", name, "parent_production_crop_group") or None, parent)
		self.assertEqual([g for g, _p in crop_hierarchy.STANDARD_GROUPS][:2], ["Floriculture", "Summer Flowers"])
		self.assertEqual(frappe.db.get_value("Production Crop Group", "Summer Flowers", "parent_production_crop_group"), "Floriculture")

	def test_mutara_crops_grouped(self):
		for crop, group in MUTARA.items():
			if not frappe.db.exists("Production Field Crop", crop):
				self.skipTest(f"{crop} is not on this site")
			self.assertEqual(frappe.db.get_value("Production Field Crop", crop, "crop_group"), group, crop)

	def test_avocado_is_a_crop(self):
		section = frappe.db.get_value("Production Crop", {"crop_key": "avocado"}, "name")
		if not section:
			self.skipTest("no avocado section on this site")
		self.assertTrue(frappe.db.exists("Production Field Crop", "Avocado"))
		for v in ("Hass", "Fuerte"):
			if frappe.db.exists("Production Variety", v):
				self.assertEqual(frappe.db.get_value("Production Variety", v, "field_crop"), "Avocado", v)
		for dt in ("Production Crop Cycle", "Production Protocol"):
			self.assertFalse(frappe.db.exists(dt, {"crop": section, "field_crop": ("!=", "Avocado")}), dt)
			self.assertFalse(frappe.db.exists(dt, {"crop": section, "field_crop": ("is", "not set")}), dt)

	def test_single_crop_section_fills_its_crop_silently(self):
		"""Avocado has one crop: it is not a section 'with crops' (no crop required, no crop column) and a cycle
		saved without field_crop ends with field_crop Avocado."""
		section = frappe.db.get_value("Production Crop", {"crop_key": "avocado"}, "name")
		unit = section and frappe.db.get_value("Production Unit", {"crop": section}, "name")
		if not unit or not frappe.db.exists("Production Variety", "Hass"):
			self.skipTest("no avocado section with units on this site")
		self.assertFalse(field_crops.has_field_crops(section))
		self.assertEqual(field_crops.only_crop(section), "Avocado")
		frappe.db.set_value("Production Variety", "Hass", "field_crop", None)
		cyc = frappe.get_doc({"doctype": "Production Crop Cycle", "unit": unit, "crop": section, "variety": "Hass", "cycle_type": "Season",
			"start_date": frappe.utils.today(), "status": "Closed"})
		cyc.insert()  # must not throw
		self.assertEqual(cyc.field_crop, "Avocado")
		self.assertEqual(frappe.db.get_value("Production Crop Cycle", cyc.name, "field_crop"), "Avocado")

	def test_crop_hierarchy_patch_idempotent(self):
		crop_hierarchy.execute()
		before = _counts()
		crop_hierarchy.execute()
		self.assertEqual(_counts(), before)

	def test_fresh_site_patch_order(self):
		"""A section whose varieties grow different products and has no crops yet: create_from_varieties then
		crop_hierarchy give Production Field Crops that have a group."""
		for uom in ("Kg", "Pieces"):
			if not frappe.db.exists("UOM", uom):
				frappe.get_doc({"doctype": "UOM", "uom_name": uom}).insert()
		if not frappe.db.exists("Item Group", "All Item Groups"):
			frappe.get_doc({"doctype": "Item Group", "item_group_name": "All Item Groups", "is_group": 1}).insert()
		section = frappe.get_doc({"doctype": "Production Crop", "crop_name": "CHM Mixed", "crop_key": "chm-mixed", "unit_label": "Block",
			"yield_uom": "Kg", "enabled": 1, "uses_crop_cycles": 1}).insert()
		for code, name in (("CHM Beetroot", "CHM Beetroot"), ("CHM Coffee", "Coffee")):
			frappe.get_doc({"doctype": "Item", "item_code": code, "item_name": name, "item_group": "All Item Groups", "stock_uom": "Kg",
				"is_stock_item": 1}).insert()
			frappe.get_doc({"doctype": "Production Variety", "variety_name": f"{name} V", "crop": section.name, "product": code,
				"item": code}).insert()
		made = field_crops.create_from_varieties()
		crop_hierarchy.execute()
		field_crops.link_records()
		self.assertEqual(sorted(made), ["CHM Beetroot", "Coffee"])
		self.assertIsNone(frappe.get_meta("Production Field Crop").get_field("production_crop"))
		self.assertEqual(frappe.db.get_value("Production Field Crop", "Coffee", "crop_group"), "Plantation Crops")
		# a crop the map does not know stays without a group, for a manager to set
		self.assertFalse(frappe.db.get_value("Production Field Crop", "CHM Beetroot", "crop_group"))
		self.assertEqual(frappe.db.get_value("Production Variety", {"variety_name": "Coffee V"}, "field_crop"), "Coffee")

	def test_section_links_labelled_section(self):
		bad = []
		for dt in frappe.get_all("DocType", filters={"module": "Production", "istable": 0}, pluck="name"):
			for df in frappe.get_meta(dt).get("fields", {"fieldtype": "Link", "options": "Production Crop"}):
				if df.label != "Section":
					bad.append((dt, df.fieldname, df.label))
		for dt in frappe.get_all("DocType", filters={"module": "Production", "istable": 1}, pluck="name"):
			for df in frappe.get_meta(dt).get("fields", {"fieldtype": "Link", "options": "Production Crop"}):
				if df.label != "Section":
					bad.append((dt, df.fieldname, df.label))
		self.assertEqual(bad, [])


class TestRenameCopyPath(IntegrationTestCase):
	"""The rename patch's copy path, with a throwaway source doctype so no real data is touched."""

	SRC = "Throwaway Crop Src"

	def setUp(self):
		frappe.set_user("Administrator")
		if frappe.db.exists("DocType", self.SRC):
			frappe.delete_doc("DocType", self.SRC, force=True)
		frappe.get_doc({"doctype": "DocType", "name": self.SRC, "module": "Production", "custom": 1, "autoname": "field:crop_name",
			"fields": [
				{"fieldname": "crop_name", "fieldtype": "Data", "label": "Crop", "unique": 1},
				{"fieldname": "product", "fieldtype": "Data", "label": "Product"},
				{"fieldname": "harvest_uom", "fieldtype": "Data", "label": "Harvest Unit"},
				{"fieldname": "color", "fieldtype": "Data", "label": "Colour"},
				{"fieldname": "enabled", "fieldtype": "Check", "label": "Enabled"},
			], "permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1}]}).insert()
		for n, uom, enabled in (("TRC Alpha", "Kg", 1), ("Maize", "Pieces", 0), ("TRC Beta", "Pieces", 0)):
			frappe.get_doc({"doctype": self.SRC, "crop_name": n, "harvest_uom": uom, "color": "#112233", "enabled": enabled}).insert()
		self.new = "Production Field Crop"
		self.existing = frappe.db.exists(self.new, "Maize")

	def tearDown(self):
		frappe.delete_doc("DocType", self.SRC, force=True)
		for n in ("TRC Alpha", "TRC Beta"):
			if frappe.db.exists(self.new, n):
				frappe.delete_doc(self.new, n, force=True)
		frappe.db.commit()

	def test_copy_rows_keeps_every_row_and_skips_existing(self):
		from upande_production.patches import rename_field_crop_doctype as p

		before_maize = frappe.db.get_value(self.new, "Maize", ["harvest_uom", "enabled"]) if self.existing else None
		copied = p.copy_rows(self.SRC, self.new)
		self.assertEqual(copied, 3 if not self.existing else 2)
		alpha = frappe.db.get_value(self.new, "TRC Alpha", ["crop_name", "harvest_uom", "color", "enabled", "crop_group"], as_dict=True)
		self.assertEqual((alpha.harvest_uom, alpha.color, alpha.enabled, alpha.crop_group), ("Kg", "#112233", 1, None))
		self.assertEqual(frappe.db.get_value(self.new, "TRC Beta", "enabled"), 0)
		if self.existing:  # a name already present is left as it is
			self.assertEqual(frappe.db.get_value(self.new, "Maize", ["harvest_uom", "enabled"]), before_maize)
		self.assertEqual(p.copy_rows(self.SRC, self.new), 0)  # idempotent
