import frappe
from frappe.tests import IntegrationTestCase

from upande_production.api import drymatter_monitor as api
from upande_production.production.logic import drymatter_monitor as mon


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


def pts(*pairs):
	return [{"date": d, "dm_pct": v} for d, v in pairs]


class TestMonitorMath(IntegrationTestCase):
	def test_microwave_percent(self):
		self.assertEqual(mon.microwave_pct(50, 12.5), 25.0)
		# the dish comes off both weighings: (14.5 - 4.5) / (24.5 - 4.5)
		self.assertEqual(mon.microwave_pct(24.5, 14.5, 4.5), 50.0)
		self.assertIsNone(mon.microwave_pct(None, None))

	def test_microwave_refuses_impossible_weights(self):
		for args in ((50, None), (None, 10), (50, 60), (5, 3, 6), (30, 4, 5)):
			with self.assertRaises(frappe.ValidationError, msg=str(args)):
				mon.microwave_pct(*args)

	def test_combine_averages_when_both(self):
		self.assertEqual(mon.combine(24, 26), 25)
		self.assertEqual(mon.combine(24, None), 24)
		self.assertEqual(mon.combine(None, 26.5), 26.5)
		self.assertIsNone(mon.combine(None, None))

	def test_projection(self):
		# 1 point a week, +1 point a week: from 21 on the 15th, 24 is three weeks on
		p = mon.projection(pts(("2026-10-01", 18), ("2026-10-08", 19), ("2026-10-15", 20), ("2026-10-22", 21)), 24)
		self.assertEqual((p["state"], p["date"], p["slope_per_week"]), ("rising", "2026-11-12", 1.0))
		self.assertEqual(mon.projection(pts(("2026-10-01", 18)), 24)["state"], "few")
		self.assertEqual(mon.projection(pts(("2026-10-01", 20), ("2026-10-08", 19)), 24)["state"], "flat")
		r = mon.projection(pts(("2026-10-01", 22), ("2026-10-08", 25), ("2026-10-15", 26)), 24)
		self.assertEqual((r["state"], r["date"]), ("reached", "2026-10-08"))
		self.assertEqual(mon.projection(pts(("2026-10-01", 20), ("2026-10-08", 20.05)), 24)["state"], "far")
		self.assertEqual(mon.projection(pts(("2026-10-01", 20), ("2026-10-08", 21)), None)["state"], "none")


class TestMonitor(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		cls.crop = _make("Production Crop", crop_name="DM Mon Crop", crop_key="dm-mon", unit_label="Block", yield_uom="Kg",
			dry_matter_testing=1, dry_matter_on="Fruit", dry_matter_target_pct=24, dry_matter_max_pct=34).name
		cls.unit = _make("Production Unit", unit_name="DMM A", crop=cls.crop, unit_type="Orchard Block", company=company, area_ha=1).name

	def tearDown(self):
		for n in frappe.get_all(mon.TAG, filters={"unit": self.unit}, pluck="name"):
			frappe.delete_doc(mon.TAG, n, force=1)

	def _tag(self, tree="R12-T7", fruit="1", **kw):
		return mon.create_tag({"unit": self.unit, "tree_label": tree, "fruit_tag": fruit, "tagged_on": "2026-10-01", **kw})

	def test_tag_takes_block_context_and_refuses_a_duplicate(self):
		doc = self._tag()
		self.assertEqual((doc.crop, doc.status), (self.crop, "Active"))
		with self.assertRaises(frappe.ValidationError):
			self._tag()
		self._tag(fruit="2")
		self._tag(tree="R12-T8")

	def test_reading_both_methods(self):
		doc = self._tag()
		doc = mon.add_reading(doc.name, {"reading_date": "2026-10-10", "fresh_g": 24.5, "dish_g": 4.5, "dry_g": 14.5,
			"machine_pct": 24, "instrument": "NIR-1"})
		r = doc.readings[0]
		self.assertEqual((r.microwave_pct, r.machine_pct, r.dm_pct, r.method), (50.0, 24, 37.0, "Both"))
		self.assertEqual((doc.latest_pct, str(doc.latest_on)), (37.0, "2026-10-10"))

	def test_machine_only_reading_has_no_microwave_values(self):
		doc = self._tag()
		mon.add_reading(doc.name, {"reading_date": "2026-10-10", "machine_pct": 22.5})
		row = mon.tag_row(frappe.get_doc(mon.TAG, doc.name))["readings"][0]
		self.assertEqual((row["method"], row["microwave_pct"], row["fresh_g"], row["machine_pct"], row["dm_pct"]),
			("Machine", None, None, 22.5, 22.5))

	def test_reading_rules(self):
		doc = self._tag()
		for bad in ({"reading_date": "2026-10-10"},  # no method
				{"reading_date": "2026-09-01", "machine_pct": 22},  # before the tag
				{"reading_date": "2099-01-01", "machine_pct": 22},  # future
				{"reading_date": "2026-10-10", "machine_pct": 120},
				{"reading_date": "2026-10-10", "fresh_g": 20, "dry_g": 25}):
			with self.assertRaises(frappe.ValidationError, msg=str(bad)):
				mon.add_reading(doc.name, bad)
		self.assertEqual(len(frappe.get_doc(mon.TAG, doc.name).readings), 0)

	def test_series_projection_and_ready(self):
		a = self._tag(fruit="1")
		b = self._tag(fruit="2", tree="R12-T8")
		for d, mw, mc in (("2026-10-05", 20, None), ("2026-10-12", 21, 21), ("2026-10-19", None, 22)):
			mon.add_reading(a.name, {"reading_date": d, **({"fresh_g": 100, "dry_g": mw} if mw else {}), **({"machine_pct": mc} if mc else {})})
		mon.add_reading(b.name, {"reading_date": "2026-10-19", "machine_pct": 26})
		m = mon.monitor(self.crop)
		self.assertEqual((m["target_pct"], m["max_pct"]), (24, 34))
		self.assertEqual(m["blocks"], [{"unit": self.unit, "farm": frappe.db.get_value("Production Unit", self.unit, "farm")}])
		by = {t["fruit_tag"] + t["tree_label"]: t for t in m["tags"]}
		self.assertFalse(by["1R12-T7"]["ready"])
		self.assertTrue(by["2R12-T8"]["ready"])
		fruit = m["series"]["fruit"][a.name]
		self.assertEqual([p["dm_pct"] for p in fruit["points"]], [20, 21, 22])
		self.assertEqual(fruit["projection"]["state"], "rising")
		blk = m["series"]["block"][self.unit]
		# 15th-21st: fruit one 22, fruit two 26
		last = blk["points"][-1]
		self.assertEqual((last["date"], last["dm_pct"], last["fruit"]), ("2026-10-19", 24.0, 2))
		self.assertIn(f"{self.unit}||R12-T8", m["series"]["tree"])
		self.assertEqual(blk["projection"]["state"], "reached")
		# a farm filter that excludes the block
		self.assertEqual(mon.monitor(self.crop, unit="nope")["tags"], [])

	def test_delete_reading_and_status(self):
		doc = self._tag()
		doc = mon.add_reading(doc.name, {"reading_date": "2026-10-10", "machine_pct": 22})
		doc = mon.add_reading(doc.name, {"reading_date": "2026-10-17", "machine_pct": 23})
		doc = mon.delete_reading(doc.name, doc.readings[1].name)
		self.assertEqual((len(doc.readings), doc.latest_pct), (1, 22))
		self.assertEqual(mon.update_tag(doc.name, "Harvested").status, "Harvested")
		with self.assertRaises(frappe.ValidationError):
			mon.update_tag(doc.name, "Eaten")

	def test_api_gates(self):
		frappe.set_user("Guest")
		try:
			self.assertIn("error", api.get_monitor(self.crop))
			self.assertIn("error", api.save_tag({"unit": self.unit, "tree_label": "x", "fruit_tag": "1"}))
		finally:
			frappe.set_user("Administrator")
		r = api.save_tag({"unit": self.unit, "tree_label": "R1-T1", "fruit_tag": "9", "tagged_on": "2026-10-01",
			"reading": {"reading_date": "2026-10-03", "machine_pct": 21}})
		self.assertEqual((r["latest_pct"], r["ready"]), (21, False))
		r = api.add_reading(r["name"], {"reading_date": "2026-10-10", "fresh_g": 50, "dry_g": 13})
		self.assertEqual((r["latest_pct"], r["ready"]), (26.0, True))
