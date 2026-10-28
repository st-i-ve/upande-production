import frappe
from frappe.tests import IntegrationTestCase

from upande_production.api import establishment as api
from upande_production.production.logic import establishment


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


class TestEstablishment(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make("Farm", farm_name="EST Farm", company=cls.company, abbreviation="ESF",
			farm_type=[{"farm_type": "Has Blocks"}])
		cls.crop = _make("Production Crop", crop_name="EST Crop", crop_key="est-crop", unit_label="Block", yield_uom="Kg")
		cls.op = _make("Production Operation", crop=cls.crop.name, operation_name="EST Land Prep",
			category="Other", work_uom="Kg", activity_type="Capital")
		cls.group = cls._unit("EST Group", unit_type="Pivot", is_group=1)
		cls.a = cls._unit("EST A", parent_production_unit=cls.group.name, area_ha=3)
		cls.b = cls._unit("EST B", parent_production_unit=cls.group.name, area_ha=1)
		cls.group.reload()

	@classmethod
	def _unit(cls, name, **kw):
		return _make("Production Unit", unit_name=name, crop=cls.crop.name, farm=cls.farm.name,
			unit_type=kw.pop("unit_type", "Orchard Block"), company=cls.company, **kw)

	def _cost(self, blocks, amount=1000, method="By area", submit=True):
		doc = frappe.get_doc({"doctype": "Block Establishment Cost", "crop": self.crop.name, "farm": self.farm.name,
			"posting_date": "2026-01-10", "operation": self.op.name, "amount": amount, "split_method": method,
			"blocks": blocks})
		doc.insert()
		if submit:
			doc.submit()
		return doc

	def test_split_by_area(self):
		doc = self._cost([{"unit": self.group.name}])
		got = {r.unit: (r.share_pct, r.amount) for r in doc.blocks}
		self.assertEqual(got[self.a.name], (75, 750))
		self.assertEqual(got[self.b.name], (25, 250))
		self.assertEqual(doc.total_area_ha, 4)

	def test_split_rounding_sums_to_amount(self):
		c = self._unit("EST C", parent_production_unit=self.group.name, area_ha=1)
		doc = self._cost([{"unit": self.a.name}, {"unit": self.b.name}, {"unit": c.name}], amount=100, submit=False)
		self.assertEqual(round(sum(r.amount for r in doc.blocks), 2), 100)
		self.assertEqual(len(doc.blocks), 3)

	def test_manual_split_must_total_100(self):
		with self.assertRaises(frappe.ValidationError):
			self._cost([{"unit": self.a.name, "share_pct": 60}, {"unit": self.b.name, "share_pct": 30}], method="Manual")
		doc = self._cost([{"unit": self.a.name, "share_pct": 60}, {"unit": self.b.name, "share_pct": 40}], method="Manual")
		self.assertEqual({r.unit: r.amount for r in doc.blocks}, {self.a.name: 600, self.b.name: 400})

	def test_split_group_without_areas_refused(self):
		g = self._unit("EST NoArea G", unit_type="Pivot", is_group=1)
		self._unit("EST NA1", parent_production_unit=g.name)
		g.reload()
		with self.assertRaises(frappe.ValidationError) as cm:
			self._cost([{"unit": g.name}])
		self.assertIn("has no area", str(cm.exception))

	def test_cost_by_unit_counts_submitted_only(self):
		self._cost([{"unit": self.a.name}], amount=500)
		self._cost([{"unit": self.a.name}], amount=900, submit=False)
		self.assertEqual(establishment.cost_by_unit([self.a.name]), {self.a.name: 500})
		cancelled = self._cost([{"unit": self.b.name}], amount=70)
		cancelled.cancel()
		self.assertEqual(establishment.cost_by_unit([self.b.name]), {})

	def test_api_round_trip(self):
		r = api.save_cost({"crop": self.crop.name, "farm": self.farm.name, "posting_date": "2026-02-01",
			"operation": self.op.name, "amount": 400, "split_method": "By area", "blocks": [{"unit": self.group.name}]})
		self.assertIn("name", r)
		out = api.list_costs(self.crop.name, self.farm.name)
		self.assertEqual(out["rows"][0]["blocks"][0]["unit"], self.a.name)
		row = next(u for u in out["by_unit"] if u["unit"] == self.a.name)
		self.assertEqual(row["total"], 300)
		self.assertEqual(api.cancel_cost(r["name"]), {"ok": True})
		acts = api.capital_activities(self.crop.name)["rows"]
		self.assertEqual(acts[0]["operation"], self.op.name)
		ob = api.save_opening_balance({"crop": self.crop.name, "unit": self.a.name, "as_of_date": "2026-01-01",
			"setup_cost": 5, "running_costs_to_date": 1, "value_recovered_to_date": 2})
		self.assertNotIn("error", ob)
		self.assertEqual(api.list_opening_balances(self.crop.name)["rows"][0]["setup_cost"], 5)

	def test_leaf_units_only_of_the_costs_crop(self):
		other = _make("Production Crop", crop_name="EST Other Crop", crop_key="est-other", unit_label="Block", yield_uom="Kg")
		g = self._unit("EST Mixed G", unit_type="Pivot", is_group=1)
		mine = self._unit("EST Mixed Mine", parent_production_unit=g.name, area_ha=1)
		_make("Production Unit", unit_name="EST Mixed Theirs", crop=other.name, farm=self.farm.name,
			unit_type="Orchard Block", company=self.company, parent_production_unit=g.name, area_ha=1)
		g.reload()
		self.assertEqual(establishment.leaf_units(g.name, self.crop.name), [mine.name])
		doc = self._cost([{"unit": g.name}], submit=False)
		self.assertEqual([r.unit for r in doc.blocks], [mine.name])

	def test_manual_group_with_zero_area_leaf_refused(self):
		g = self._unit("EST Zero G", unit_type="Pivot", is_group=1)
		self._unit("EST Z1", parent_production_unit=g.name, area_ha=2)
		self._unit("EST Z2", parent_production_unit=g.name, area_ha=0)
		g.reload()
		with self.assertRaises(frappe.ValidationError) as cm:
			self._cost([{"unit": g.name, "share_pct": 100}], method="Manual")
		self.assertIn("EST Z2", str(cm.exception))

	def test_manual_leaf_rows_with_zero_area_leaf_ok(self):
		g = self._unit("EST Zero2 G", unit_type="Pivot", is_group=1)
		z1 = self._unit("EST Y1", parent_production_unit=g.name, area_ha=2)
		z2 = self._unit("EST Y2", parent_production_unit=g.name, area_ha=0)
		doc = self._cost([{"unit": z1.name, "share_pct": 70}, {"unit": z2.name, "share_pct": 30}], method="Manual")
		self.assertEqual({r.unit: r.amount for r in doc.blocks}, {z1.name: 700, z2.name: 300})

	def test_pay_gated_reads_for_viewer(self):
		email = "est_viewer@example.com"
		if not frappe.db.exists("User", email):
			_make("User", email=email, first_name="ESTViewer", send_welcome_email=0, roles=[{"role": "Production Viewer"}])
		frappe.set_user(email)
		try:
			ob = api.list_opening_balances(self.crop.name)
			acts = api.capital_activities(self.crop.name)
		finally:
			frappe.set_user("Administrator")
		self.assertIn("error", ob)
		self.assertNotIn("rows", ob)
		self.assertIn("rows", acts)
