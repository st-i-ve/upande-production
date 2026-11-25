import frappe
from frappe.tests import IntegrationTestCase

from upande_production.api import field_crops as api
from upande_production.api import production as prod
from upande_production.production.logic import crop_groups


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


class TestCropTreeApi(IntegrationTestCase):
	"""Crop tree endpoints and the bootstrap's crop lists; rolled back per test."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		crop_groups.ensure_groups()
		cls.fv = _make("Production Crop", crop_name="CTA Mixed", crop_key="cta-mixed", unit_label="Block", yield_uom="Kg", enabled=1)
		cls.single = _make("Production Crop", crop_name="CTA Single", crop_key="cta-single", unit_label="Block", yield_uom="Kg", enabled=1)
		cls.empty = _make("Production Crop", crop_name="CTA Empty", crop_key="cta-empty", unit_label="Block", yield_uom="Kg", enabled=1)
		if not frappe.db.exists("Item Group", "All Item Groups"):
			_make("Item Group", item_group_name="All Item Groups", is_group=1)
		cls.users = {}
		for role in ("Production Viewer", "Production Manager"):
			email = role.lower().replace(" ", "") + "@cta.test"
			if not frappe.db.exists("User", email):
				_make("User", email=email, first_name=role.split()[1], roles=[{"role": role}], send_welcome_email=0)
			cls.users[role] = email

	def setUp(self):
		frappe.db.savepoint("cta_test")
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point="cta_test")

	def _varieties(self, section, names):
		"""A variety per crop name, in the section."""
		for n in names:
			fc = frappe.db.get_value("Production Field Crop", {"crop_name": n}) or _make(
				"Production Field Crop", crop_name=n, crop_group="Vegetable Crops", harvest_uom="Kg").name
			code = "CTA " + n
			if not frappe.db.exists("Item", code):
				_make("Item", item_code=code, item_name=code, item_group="All Item Groups", stock_uom="Kg", is_stock_item=1)
			v = _make("Production Variety", variety_name="CTA V " + n, crop=section, product=code, item=code)
			frappe.db.set_value("Production Variety", v.name, "field_crop", fc)

	def test_tree_shape(self):
		out = api.get_crop_tree()
		self.assertNotIn("error", out)
		groups = {g["name"]: g for g in out["groups"]}
		self.assertEqual(set(groups["Summer Flowers"]), {"name", "parent", "sort_order"})
		self.assertEqual(groups["Summer Flowers"]["parent"], "Floriculture")
		self.assertIsNone(groups["Fruit Crops"]["parent"])
		self.assertIsInstance(out["crops"], list)

	def test_save_group_and_crops(self):
		g = api.save_crop_group({"group_name": "CTA Group", "parent": "Fruit Crops", "sort_order": 3})
		self.assertEqual(g["name"], "CTA Group")
		self.assertEqual(frappe.db.get_value("Production Crop Group", "CTA Group", "parent_production_crop_group"), "Fruit Crops")
		c = api.save_field_crop({"crop_name": "CTA Fig", "crop_group": "CTA Group", "harvest_uom": "Kg", "production_crop": "x"})
		self.assertNotIn("error", c)
		s = api.save_sub_crop({"sub_crop_name": "CTA Fig Black", "field_crop": c["name"], "harvest_uom": "Kg"})
		self.assertNotIn("error", s)
		row = next(r for r in api.get_crop_tree()["crops"] if r["name"] == c["name"])
		self.assertEqual([x["name"] for x in row["sub_crops"]], [s["name"]])
		s2 = api.save_sub_crop({"name": s["name"], "sub_crop_name": "CTA Fig Black", "field_crop": c["name"], "enabled": 0})
		self.assertEqual(s2["name"], s["name"])
		g2 = api.save_crop_group({"name": "CTA Group", "group_name": "CTA Group", "parent": None, "sort_order": 5})
		self.assertEqual(frappe.db.get_value("Production Crop Group", "CTA Group", "sort_order"), 5)

	def test_writes_are_manager_only(self):
		frappe.set_user(self.users["Production Viewer"])
		for fn, data in (
			(api.save_crop_group, {"group_name": "CTA Nope"}),
			(api.save_field_crop, {"crop_name": "CTA Nope", "crop_group": "Fruit Crops"}),
			(api.save_sub_crop, {"sub_crop_name": "CTA Nope", "field_crop": "x"}),
		):
			out = fn(data)
			self.assertIn("error", out, fn.__name__)
		frappe.set_user("Administrator")
		self.assertFalse(frappe.db.exists("Production Crop Group", "CTA Nope"))
		frappe.set_user(self.users["Production Manager"])
		self.assertNotIn("error", api.save_crop_group({"group_name": "CTA Mgr", "parent": "Fruit Crops"}))

	def test_bootstrap_single_mixed_empty(self):
		self._varieties(self.fv.name, ["CTA Cabbage", "CTA Maize", "CTA Onion", "CTA Potato", "CTA Kale"])
		self._varieties(self.single.name, ["CTA Avocado"])
		out = prod.get_bootstrap()
		by = {c["name"]: c for c in out["crops"]}
		self.assertEqual(len(by[self.fv.name]["field_crops"]), 5)
		self.assertEqual(by[self.fv.name]["has_field_crops"], 1)
		self.assertTrue(all(r["crop_group"] for r in by[self.fv.name]["field_crops"]))
		self.assertEqual(len(by[self.single.name]["field_crops"]), 1)
		self.assertEqual(by[self.single.name]["has_field_crops"], 0)
		self.assertEqual(by[self.empty.name]["field_crops"], [])
		self.assertEqual(by[self.empty.name]["has_field_crops"], 0)
		self.assertIn("Floriculture", [g["name"] for g in out["crop_groups"]])
