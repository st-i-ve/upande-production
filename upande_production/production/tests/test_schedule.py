from datetime import date

from frappe import _dict
from frappe.tests import IntegrationTestCase

from upande_production.production.logic import schedule as S

START = date(2026, 1, 5)


def cyc(no=1):
	return _dict(name="CY", start_date=START, cycle_no=no)


def proto(key=(), cultural=()):
	return _dict(key_activities=[_dict(name=f"k{i}", **r) for i, r in enumerate(key)],
		cultural_activities=[_dict(name=f"c{i}", **r) for i, r in enumerate(cultural)])


def spray(**kw):
	return {"operation": "Spray", "schedule": "Interval", "interval_weeks": 1, "establishment_period_weeks": 0,
		"pre_harvest_interval_days": 0, **kw}


class TestSchedule(IntegrationTestCase):
	def test_key_week_7(self):
		p = proto(key=[{"operation": "Prune", "week": 7, "repeats": "Every cycle"}])
		r = S.due_items(cyc(), p, date(2026, 1, 1), date(2026, 12, 31), None)
		self.assertEqual([(i["due_date"], i["ref"], i["kind"]) for i in r], [(date(2026, 2, 16), "CY:k0:k", "key")])

	def test_first_cycle_only_skipped_in_cycle_2(self):
		p = proto(key=[{"operation": "Plant", "week": 1, "repeats": "First cycle only"}])
		self.assertEqual(len(S.due_items(cyc(1), p, START, date(2026, 3, 1), None)), 1)
		self.assertEqual(S.due_items(cyc(2), p, START, date(2026, 3, 1), None), [])

	def test_interval_after_establishment(self):
		p = proto(cultural=[spray(interval_weeks=2, establishment_period_weeks=3)])
		r = S.due_items(cyc(), p, START, date(2026, 3, 1), None)
		self.assertEqual([i["due_date"] for i in r][:3], [date(2026, 1, 26), date(2026, 2, 9), date(2026, 2, 23)])
		self.assertEqual(r[1]["ref"], "CY:c0:1")

	def test_phi_suppresses_last_spray(self):
		p = proto(cultural=[spray(interval_weeks=1, establishment_period_weeks=3, pre_harvest_interval_days=14)])
		r = S.due_items(cyc(), p, START, date(2026, 3, 15), date(2026, 3, 2))
		dues = [i["due_date"] for i in r]
		self.assertIn(date(2026, 2, 9), dues)
		self.assertFalse([d for d in dues if date(2026, 2, 17) <= d < date(2026, 3, 2)])

	def test_continuous_phi_between_picks(self):
		p = proto(cultural=[spray(interval_weeks=1, pre_harvest_interval_days=3)])
		r = S.due_items(cyc(), p, date(2026, 3, 2), date(2026, 3, 8), date(2026, 3, 2), picks=[date(2026, 3, 2)],
			harvest_interval_weeks=1)
		dues = [i["due_date"] for i in r]
		# weekly from Monday 2026-01-05: 03-02 is a spray day; 03-02 is a pick day (inside PHI)
		self.assertNotIn(date(2026, 3, 2), dues)
		p2 = proto(cultural=[spray(interval_weeks=1, pre_harvest_interval_days=3, establishment_period_weeks=0)])
		self.assertEqual(S.next_pick(date(2026, 3, 4), date(2026, 3, 2), [date(2026, 3, 2)], 1), date(2026, 3, 9))
		self.assertEqual(S.next_pick(date(2026, 3, 7), date(2026, 3, 2), [date(2026, 3, 2)], 1), date(2026, 3, 9))
		# a daily-offset schedule: 5 days before the pick is kept, 2 days before is dropped
		kept = proto(cultural=[spray(interval_weeks=1, pre_harvest_interval_days=3)])
		kept.cultural_activities[0].establishment_period_weeks = 8  # first due 2026-03-02 + 0
		ds = S.due_items(_dict(name="CY", start_date=date(2026, 3, 4), cycle_no=1), kept, date(2026, 3, 4),
			date(2026, 3, 11), date(2026, 3, 2), picks=[date(2026, 3, 2)], harvest_interval_weeks=1)
		self.assertEqual(ds, [])  # first due = start + 8 weeks, outside the window
		ds = S.due_items(_dict(name="CY", start_date=date(2026, 3, 4), cycle_no=1), proto(cultural=[spray(
			interval_weeks=1, pre_harvest_interval_days=3)]), date(2026, 3, 4), date(2026, 3, 11), date(2026, 3, 2),
			picks=[date(2026, 3, 2)], harvest_interval_weeks=1)
		self.assertEqual([i["due_date"] for i in ds], [date(2026, 3, 4), date(2026, 3, 11)])  # 5 days before 03-09 kept

	def test_as_needed_never_generated(self):
		p = proto(cultural=[{"operation": "Spray", "schedule": "As needed", "interval_weeks": 0}])
		self.assertEqual(S.due_items(cyc(), p, START, date(2027, 1, 1), None), [])

	def test_due_items_without_harvest_date(self):
		p = proto(cultural=[spray(interval_weeks=2, establishment_period_weeks=30, pre_harvest_interval_days=14)])
		r = S.due_items(cyc(), p, START, date(2026, 12, 1), None)
		self.assertTrue(r)
		self.assertEqual(S.next_pick(date(2026, 3, 1), None, [], None), None)
