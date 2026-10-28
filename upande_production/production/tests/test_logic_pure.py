import unittest
from datetime import date, datetime

from upande_production.production.logic.deviation import task_deviation
from upande_production.production.logic.pay import pay_value
from upande_production.production.logic.weeks import iso_of, iso_week_bounds


class TestLogicPure(unittest.TestCase):
	def test_iso_week_bounds_53(self):
		self.assertEqual(iso_week_bounds(2026, 53), (date(2026, 12, 28), date(2027, 1, 3)))
		self.assertEqual(iso_week_bounds(2027, 1)[0], date(2027, 1, 4))

	def test_iso_of(self):
		self.assertEqual(iso_of("2027-01-02"), (2026, 53))
		self.assertEqual(iso_of(date(2027, 1, 4)), (2027, 1))

	def test_deviation_cases(self):
		due = date(2026, 10, 20)
		self.assertEqual(task_deviation("Skipped", due, None, 10, 0, 1), "Skipped")
		self.assertEqual(task_deviation("Done", due, datetime(2026, 10, 22, 8, 0), 10, 10, 1), "Late")
		self.assertEqual(task_deviation("Done", due, "2026-10-21", 10, 10, 1), "")
		self.assertEqual(task_deviation("Done", due, datetime(2026, 10, 21), 10, 6, 1), "Partial")
		self.assertEqual(task_deviation("Open", due, None, 10, 0, 1), "")
		# Partial wins over Late
		self.assertEqual(task_deviation("Partly Done", due, "2026-10-30", 10, 3, 1), "Partial")

	def test_pay_value(self):
		self.assertEqual(pay_value(12.5, 40), 500.0)
		self.assertEqual(pay_value(None, 40), 0)
