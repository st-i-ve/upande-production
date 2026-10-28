import frappe
from frappe.tests import IntegrationTestCase

from upande_production.api import drymatter
from upande_production.api import production as prod_api


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


class TestDryMatter(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		for u in ("Kg", "Plant"):
			if not frappe.db.exists("UOM", u):
				_make("UOM", uom_name=u)
		cls.crop = _make(
			"Production Crop", crop_name="DM Crop", crop_key="dm-crop", unit_label="Block", yield_uom="Kg",
			dry_matter_testing=1, dry_matter_on="Fruit", dry_matter_target_pct=21,
		)
		cls.off = _make("Production Crop", crop_name="DM Off", crop_key="dm-off", unit_label="Block", yield_uom="Kg")
		cls.unit = _make(
			"Production Unit", unit_name="DM A", crop=cls.crop.name, unit_type="Orchard Block", company=cls.company, area_ha=1
		).name
		cls.unit_off = _make(
			"Production Unit", unit_name="DM B", crop=cls.off.name, unit_type="Orchard Block", company=cls.company, area_ha=1
		).name

	def _item(self):
		if not frappe.db.exists("Item", "DM Item"):
			_make("Item", item_code="DM Item", item_name="DM Item", item_group="All Item Groups", stock_uom="Kg", is_stock_item=1)
		return "DM Item"

	def _test(self, unit, crop, pcts, date="2026-10-01", **kw):
		return {
			"unit": unit, "crop": crop, "test_date": date,
			"samples": [{"sample_no": i + 1, "dry_matter_pct": p} for i, p in enumerate(pcts)], **kw,
		}

	def test_avg_and_ready(self):
		r = drymatter.save_test(self._test(self.unit, self.crop.name, [20, 23.5, 22]))
		self.assertEqual(r["avg_pct"], 21.83)
		self.assertTrue(r["ready"])
		doc = frappe.get_doc("Dry Matter Test", r["name"])
		self.assertEqual((doc.tested_on, doc.target_pct), ("Fruit", 21))
		r = drymatter.save_test(self._test(self.unit, self.crop.name, [18, 19]))
		self.assertEqual((r["avg_pct"], r["ready"]), (18.5, 0))

	def test_variety_target_overrides_crop(self):
		var = _make("Production Variety", crop=self.crop.name, variety_name="DM Var", item=self._item(), dry_matter_target_pct=25)
		self.assertEqual(var.dry_matter_target_pct, 25)
		r = drymatter.save_test(self._test(self.unit, self.crop.name, [23, 24], variety=var.name))
		doc = frappe.get_doc("Dry Matter Test", r["name"])
		self.assertEqual(doc.target_pct, 25)
		self.assertFalse(r["ready"])

	def test_refused_when_crop_off(self):
		doc = frappe.get_doc({"doctype": "Dry Matter Test", **self._test(self.unit_off, self.off.name, [22])})
		with self.assertRaises(frappe.ValidationError):  # save_test would roll back the class fixtures
			doc.insert()

	def test_latest_and_list(self):
		drymatter.save_test(self._test(self.unit, self.crop.name, [10], date="2026-09-01"))
		drymatter.save_test(self._test(self.unit, self.crop.name, [22], date="2026-10-05"))
		latest = drymatter.latest_by_unit(self.crop.name)
		self.assertEqual(latest[self.unit]["pct"], 22)
		self.assertEqual(latest[self.unit]["date"], "2026-10-05")
		self.assertEqual(latest[self.unit]["target"], 21)
		self.assertTrue(latest[self.unit]["ready"])
		rows = drymatter.list_tests(self.crop.name, self.unit)["rows"]
		self.assertEqual(rows[0]["test_date"].isoformat(), "2026-10-05")
		self.assertEqual(len(rows[0]["samples"]), 1)

	def test_blocks_show_plants_replaced(self):
		op = _make("Production Operation", crop=self.crop.name, operation_name="Gap filling", category="Other",
			work_uom="Plant", default_rate=1)
		for qty, st in ((30, "Approved"), (5, "Pending")):
			w = frappe.get_doc({
				"doctype": "Value Adder Work", "work_date": "2026-10-02", "unit": self.unit, "crop": self.crop.name,
				"operation": op.name, "qty": qty, "uom": "Plant", "approval_status": st,
			})
			w.flags.ignore_validate = True
			w.flags.ignore_mandatory = True
			w.insert()
		rows = {r["name"]: r for r in prod_api._unit_rows(self.crop.name)}
		self.assertEqual(rows[self.unit]["plants_replaced"], 30)
		self.assertIn("dry_matter", rows[self.unit])
		off = {r["name"]: r for r in prod_api._unit_rows(self.off.name)}[self.unit_off]
		self.assertEqual(off["plants_replaced"], 0)
		self.assertIsNone(off["dry_matter"])
