import unittest

from upande_production.production.logic.silage_cost import activity_labour, by_kind, cost_per_kg, cycle_cost, summarise


class TestSilageCost(unittest.TestCase):
	def test_activity_labour(self):
		self.assertEqual(activity_labour(6, 400, 999), 2400.0)  # workers x rate wins over a typed amount
		self.assertEqual(activity_labour(None, None, 1500), 1500.0)
		self.assertEqual(activity_labour(5, 0, 700), 700.0)  # no rate: the typed amount
		self.assertEqual(activity_labour(0, 400, None), 0.0)
		self.assertEqual(activity_labour(None, None, -50), 0.0)
		self.assertEqual(activity_labour("3", "350.5", None), 1051.5)

	def test_cycle_cost(self):
		c = cycle_cost(inputs=12000.456, diesel=45650, labour=2400, casual_labour=None)
		self.assertEqual(c, {"inputs": 12000.46, "diesel": 45650.0, "labour": 2400.0, "casual_labour": 0.0, "total": 60050.46})

	def test_cost_per_kg(self):
		self.assertIsNone(cost_per_kg(1000, 0))
		self.assertIsNone(cost_per_kg(1000, None))
		self.assertAlmostEqual(cost_per_kg(60000, 200000), 0.3)
		self.assertEqual(cost_per_kg(0, 100), 0.0)

	def test_by_kind(self):
		rows = by_kind(cycle_cost(inputs=250, diesel=750))
		self.assertEqual([r["kind"] for r in rows], ["inputs", "diesel", "labour", "casual_labour"])
		self.assertEqual(rows[0]["share_pct"], 25.0)
		self.assertEqual(rows[1]["share_pct"], 75.0)
		self.assertIsNone(by_kind(cycle_cost())[0]["share_pct"])

	def test_summarise_weights_by_kg_and_skips_open_cycles(self):
		cycles = [
			{"cost": cycle_cost(inputs=1000, diesel=1000), "ensiled_kg": 1000},  # 2.0 / kg
			{"cost": cycle_cost(labour=3000), "ensiled_kg": 3000},  # 1.0 / kg
			{"cost": cycle_cost(inputs=5000), "ensiled_kg": 0},  # still growing: counted in totals, not per kg
		]
		s = summarise(cycles)
		self.assertEqual(s["cost"]["total"], 10000.0)
		self.assertEqual(s["cost"]["inputs"], 6000.0)
		self.assertEqual(s["ensiled_kg"], 4000.0)
		self.assertAlmostEqual(s["cost_per_kg"], 5000 / 4000)
		self.assertEqual(s["cycles"], 3)
		self.assertIsNone(summarise([])["cost_per_kg"])
