from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from upande_production.api import establishment as api
from upande_production.production.logic import establishment


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


class TestCapitalOnBlock(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make("Farm", farm_name="COB Farm", company=cls.company, abbreviation="COB",
			farm_type=[{"farm_type": "Has Blocks"}])
		cls.crop = _make("Production Section", crop_name="COB Crop", crop_key="cob-crop", unit_label="Block", yield_uom="Kg")
		mk = lambda n, t: _make("Field Operation", crop=cls.crop.name, operation_name=n, category="Other",
			work_uom="Kg", default_rate=1, activity_type=t).name
		cls.clear, cls.rip, cls.key = mk("COB Clear", "Capital"), mk("COB Rip", "Capital"), mk("COB Prune", "Key activity")
		cls.item = _make("Item", item_code="COB Item", item_name="COB Item", item_group="All Item Groups",
			stock_uom="Kg", is_stock_item=1).name
		cls.variety = _make("Production Variety", variety_name="COB Once", crop=cls.crop.name, item=cls.item,
			harvest_pattern="Once", weeks_to_first_harvest=10,
			stages=[{"stage": "Planting", "start_day": 0, "length_days": 7, "is_harvest": 0},
				{"stage": "Harvest", "start_day": 70, "length_days": 14, "is_harvest": 1}]).name

	def _unit(self, name, area=4, **kw):
		return _make("Production Unit", unit_name=name, crop=self.crop.name, farm=self.farm.name,
			unit_type="Orchard Block", company=self.company, area_ha=area, **kw)

	def _cycle(self, unit, start, status="Active", closed_on=None):
		c = _make("Production Crop Cycle", unit=unit.name, crop=self.crop.name, variety=self.variety,
			start_date=start, status="Active")
		frappe.db.set_value("Production Crop Cycle", c.name,
			{"start_date": start, "status": status, "closed_on": closed_on})
		return c

	def _cost(self, unit, date, amount=1000, op=None):
		doc = frappe.get_doc({"doctype": "Block Establishment Cost", "crop": self.crop.name, "farm": self.farm.name,
			"posting_date": date, "operation": op or self.clear, "amount": amount, "split_method": "By area",
			"blocks": [{"unit": unit.name}]})
		doc.insert()
		doc.submit()
		return doc

	def _budget(self, unit, rows):
		unit.reload()
		unit.set("capital_budget", rows)
		unit.save()
		return unit

	# -- budget
	def test_per_ha_budget_times_area(self):
		u = self._budget(self._unit("COB U1", area=4), [{"operation": self.clear, "basis": "Per ha", "amount": 100}])
		out = establishment.unit_budget(u.name)
		self.assertEqual(out[self.clear], 400)

	def test_total_basis_ignores_area(self):
		u = self._budget(self._unit("COB U2", area=4), [{"operation": self.clear, "basis": "Total", "amount": 100}])
		self.assertEqual(establishment.unit_budget(u.name)[self.clear], 100)

	def test_budget_refuses_non_capital_operation_and_duplicates(self):
		u = self._unit("COB U3")
		with self.assertRaises(frappe.ValidationError):
			self._budget(u, [{"operation": self.key, "basis": "Total", "amount": 1}])
		with self.assertRaises(frappe.ValidationError):
			self._budget(u, [{"operation": self.clear, "basis": "Total", "amount": 1},
				{"operation": self.clear, "basis": "Total", "amount": 2}])

	# -- cycle on the split row
	def test_split_row_gets_running_cycle(self):
		u = self._unit("COB U4")
		c = self._cycle(u, "2026-01-01")
		doc = self._cost(u, "2026-03-01")
		self.assertEqual(doc.blocks[0].cycle, c.name)

	def test_no_cycle_leaves_cycle_empty(self):
		u = self._unit("COB U5")
		self.assertFalse(self._cost(u, "2026-03-01").blocks[0].cycle)

	def test_picks_the_right_cycle_across_clear_and_replant(self):
		u = self._unit("COB U6")
		old = self._cycle(u, "2025-01-01", "Closed", "2025-12-31")
		new = self._cycle(u, "2026-02-01")
		self.assertEqual(self._cost(u, "2025-06-01").blocks[0].cycle, old.name)
		self.assertEqual(self._cost(u, "2026-03-01").blocks[0].cycle, new.name)
		self.assertFalse(self._cost(u, "2026-01-15").blocks[0].cycle)  # fallow gap
		self.assertFalse(self._cost(u, "2024-06-01").blocks[0].cycle)  # before any cycle

	# -- protocols
	def test_protocol_refuses_capital_rows(self):
		from upande_production.production.doctype.production_protocol.production_protocol import validate_tables

		doc = frappe._dict({"key_activities": [], "cultural_activities": [],
			"capital_activities": [{"operation": self.clear}]})
		with self.assertRaises(frappe.ValidationError):
			validate_tables(doc)
		self.assertIsNone(frappe.get_meta("Production Protocol").get_field("capital_activities"))

	# -- patch
	def test_patch_copies_protocol_capital_to_blocks_and_fills_cycles(self):
		from upande_production.patches import capital_costs_to_blocks as patch

		a, b = self._unit("COB P1", area=2), self._unit("COB P2", area=3)
		self._budget(b, [{"operation": self.clear, "basis": "Total", "amount": 7}])  # already budgeted: kept
		p = _make("Production Protocol", protocol_name="COB Proto", crop=self.crop.name)
		frappe.db.set_value("Production Protocol", p.name, "version_status", "Active")
		for op, amt in ((self.clear, 50), (self.rip, 20)):
			frappe.get_doc({"doctype": "Production Protocol Capital Activity", "parent": p.name,
				"parenttype": "Production Protocol", "parentfield": "capital_activities",
				"operation": op, "budget_per_ha": amt}).insert()
		c = self._cycle(a, "2026-01-01")
		doc = self._cost(a, "2026-03-01")
		frappe.db.set_value("Block Establishment Cost Split", doc.blocks[0].name, "cycle", None)
		made = patch.copy_protocol_capital(protocols=[p.name], units=[a.name, b.name])
		self.assertEqual(made, 3)
		self.assertEqual(establishment.unit_budget(a.name), {self.clear: 100, self.rip: 40})
		self.assertEqual(establishment.unit_budget(b.name), {self.clear: 7, self.rip: 60})
		self.assertEqual(patch.copy_protocol_capital(protocols=[p.name], units=[a.name, b.name]), 0)  # idempotent
		self.assertEqual(patch.fill_split_cycles(parents=[doc.name]), 1)
		self.assertEqual(frappe.db.get_value("Block Establishment Cost Split", doc.blocks[0].name, "cycle"), c.name)
		self.assertEqual(frappe.db.count("Production Protocol Capital Activity", {"parent": p.name}), 2)  # kept

	# -- summaries and API
	def test_summary_uses_block_budgets_and_spend_per_cycle(self):
		u = self._budget(self._unit("COB S1", area=2), [{"operation": self.clear, "basis": "Per ha", "amount": 500},
			{"operation": self.rip, "basis": "Total", "amount": 300}])
		old = self._cycle(u, "2025-01-01", "Closed", "2025-12-31")
		new = self._cycle(u, "2026-02-01")
		self._cost(u, "2025-06-01", 100)
		self._cost(u, "2026-03-01", 250)
		self._cost(u, "2026-04-01", 50, op=self.rip)
		out = api.list_costs(self.crop.name, self.farm.name)
		row = next(r for r in out["by_unit"] if r["unit"] == u.name)
		budgets = {a["operation"]: a["budget"] for a in row["by_activity"]}
		self.assertEqual(budgets, {self.clear: 1000, self.rip: 300})
		per = {c["cycle"]: c["total"] for c in row["cycles"]}
		self.assertEqual(per, {old.name: 100, new.name: 300})
		acts = {r["operation"]: r for r in api.capital_activities(self.crop.name)["rows"]}
		self.assertTrue({self.clear, self.rip} <= set(acts))  # blocks of the crop differ, so no common per-ha figure
		cc = api.cycle_capital_costs(new.name)
		self.assertEqual(cc["unit"], u.name)
		self.assertEqual(cc["total"], 300)
		self.assertEqual({r["operation"]: r["amount"] for r in cc["by_operation"]}, {self.clear: 250, self.rip: 50})
		self.assertEqual(len(cc["rows"]), 2)

	def test_get_and_save_unit_budget_api(self):
		u = self._unit("COB A1", area=5)
		out = api.save_unit_capital_budget(u.name, [{"operation": self.clear, "basis": "Per ha", "amount": 10, "note": "x"}])
		self.assertNotIn("error", out)
		got = api.get_unit_capital_budget(u.name)
		self.assertEqual(got["area_ha"], 5)
		self.assertEqual(got["rows"][0]["effective"], 50)
		self.assertEqual(got["total_budget"], 50)

	def test_permissions(self):
		u = self._unit("COB A2")
		email = "cob_viewer@example.com"
		if not frappe.db.exists("User", email):
			_make("User", email=email, first_name="COBViewer", send_welcome_email=0, roles=[{"role": "Production Viewer"}])
		frappe.set_user(email)
		try:
			with patch.object(frappe.db, "rollback"):  # the envelope rolls back on an error, which would drop the fixtures
				saved = api.save_unit_capital_budget(u.name, [{"operation": self.clear, "basis": "Total", "amount": 1}])
			read = api.get_unit_capital_budget(u.name)
		finally:
			frappe.set_user("Administrator")
		self.assertIn("Only a manager", saved["error"])
		self.assertNotIn("error", read)

	# -- review fixes
	def _avo_user(self):
		email = "cob_avo@example.com"
		if not frappe.db.exists("User", email):
			_make("User", email=email, first_name="COBAvo", send_welcome_email=0,
				roles=[{"role": "Avocado Production Manager"}])
		return email

	def test_avocado_manager_saves_on_avocado_block_only(self):
		avo = frappe.db.get_value("Production Section", {"crop_key": "avocado"})
		if not avo:
			self.skipTest("no avocado crop on this site")
		avo_op = _make("Field Operation", crop=avo, operation_name="COB Avo Cap", category="Other",
			work_uom="Kg", default_rate=1, activity_type="Capital").name
		avo_unit = _make("Production Unit", unit_name="COB Avo Block", crop=avo, farm=self.farm.name,
			unit_type="Orchard Block", company=self.company, area_ha=2)
		other = self._unit("COB NotAvo")
		cyc = self._cycle(other, "2026-01-01")
		frappe.set_user(self._avo_user())
		try:
			with patch.object(frappe.db, "rollback"):
				ok = api.save_unit_capital_budget(avo_unit.name, [{"operation": avo_op, "basis": "Per ha", "amount": 5}])
				no_save = api.save_unit_capital_budget(other.name, [{"operation": self.clear, "basis": "Total", "amount": 1}])
				no_get = api.get_unit_capital_budget(other.name)
				no_cycle = api.cycle_capital_costs(cyc.name)
				missing = api.cycle_capital_costs("NO-SUCH-CYCLE")
		finally:
			frappe.set_user("Administrator")
		self.assertNotIn("error", ok)
		self.assertEqual(ok["total_budget"], 10)
		for out in (no_save, no_get, no_cycle):
			self.assertIn("not permitted to see this crop", out["error"])
		self.assertIn("not found", missing["error"])

	def test_per_ha_without_area_has_no_effective_budget(self):
		u = self._budget(self._unit("COB Z0", area=0), [{"operation": self.clear, "basis": "Per ha", "amount": 100}])
		self.assertIsNone(establishment.unit_budget(u.name)[self.clear])
		self.assertEqual(api.get_unit_capital_budget(u.name)["total_budget"], 0)

	def test_retired_block_keeps_rows_and_group_refuses_new(self):
		u = self._budget(self._unit("COB R1"), [{"operation": self.clear, "basis": "Total", "amount": 1}])
		frappe.db.set_value("Field Operation", self.clear, "activity_type", "Key activity")
		try:
			u.reload()
			u.status = "Retired"
			u.save()  # existing rows are not re-checked
		finally:
			frappe.db.set_value("Field Operation", self.clear, "activity_type", "Capital")
		g = _make("Production Unit", unit_name="COB G1", crop=self.crop.name, farm=self.farm.name,
			unit_type="Pivot", company=self.company, is_group=1)
		with self.assertRaises(frappe.ValidationError):
			self._budget(g, [{"operation": self.clear, "basis": "Total", "amount": 1}])

	def test_capital_activities_lists_unbudgeted_operations_too(self):
		self._budget(self._unit("COB L1"), [{"operation": self.clear, "basis": "Total", "amount": 1}])
		acts = {r["operation"]: r for r in api.capital_activities(self.crop.name)["rows"]}
		self.assertGreaterEqual(acts[self.clear]["blocks"], 1)
		self.assertIn(self.rip, acts)
