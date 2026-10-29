import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, today

from upande_production.production.logic import cycle_chain, stages


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


def _stages(*rows):
	return [{"stage": n, "start_day": s, "length_days": ln, "is_harvest": 1 if h else 0} for n, s, ln, h in rows]


class TestCycleChain(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make("Farm", farm_name="CC Farm", company=cls.company, abbreviation="CCF",
			farm_type=[{"farm_type": "Has Blocks"}])
		cls.crop = _make("Production Crop", crop_name="CC Crop", crop_key="cc-crop", unit_label="Block", yield_uom="Kg")
		cls.unit = _make("Production Unit", unit_name="CC Block A", unit_type="Orchard Block", crop=cls.crop.name,
			farm=cls.farm.name, company=cls.company)
		cls.item = _make("Item", item_code="CC Hass", item_name="CC Hass", item_group="All Item Groups",
			stock_uom="Kg", is_stock_item=1).name
		cls.hass = _make("Production Variety", variety_name="CC Hass", crop=cls.crop.name, item=cls.item,
			is_flowering=1, harvest_pattern="Interval", harvest_interval_weeks=52, lifespan_years=25,
			flowering_pattern="Interval", flowering_interval_weeks=52,
			weeks_to_first_flowering=8, weeks_flowering_to_harvest=30, weeks_to_reflower_after_harvest=6,
			harvest_window_weeks=8,
			stages=_stages(("Planting", 0, 56, 0), ("Flowering", 56, 28, 0), ("Fruit set", 84, 182, 0),
				("Harvest", 266, 56, 1))).name
		cls.fl = _make("Production Variety", variety_name="CC Fl", crop=cls.crop.name, item=cls.item,
			is_flowering=1, stage_anchor="Flowering", harvest_pattern="Interval", harvest_interval_weeks=52,
			lifespan_years=25, weeks_flowering_to_harvest=36, weeks_to_reflower_after_harvest=12,
			flowering_pattern="Interval", flowering_interval_weeks=64, harvest_window_weeks=8,
			stages=_stages(("Flowering", 0, 28, 0), ("Fruit set", 28, 224, 0), ("Harvest", 252, 56, 1))).name
		cls.once = _make("Production Variety", variety_name="CC Once", crop=cls.crop.name, item=cls.item,
			harvest_pattern="Once", weeks_to_first_harvest=10,
			stages=_stages(("Planting", 0, 7, 0), ("Harvest", 70, 14, 1))).name
		cls.short = _make("Production Variety", variety_name="CC Short", crop=cls.crop.name, item=cls.item,
			harvest_pattern="Interval", harvest_interval_weeks=52, lifespan_years=1, is_flowering=1,
			weeks_to_first_flowering=8, weeks_flowering_to_harvest=30, weeks_to_reflower_after_harvest=6,
			stages=_stages(("Planting", 0, 56, 0), ("Flowering", 56, 28, 0), ("Harvest", 266, 56, 1))).name

	def _cycle(self, variety=None, start=None, **kw):
		return _make("Production Crop Cycle", unit=self.unit.name, crop=self.crop.name, variety=variety or self.hass,
			start_date=start or add_days(today(), -100), status="Active", **kw)

	def test_flowering_actual_shifts_harvest(self):
		c = self._cycle(start="2026-01-01")
		self.assertEqual(c.expected_flowering_date, getdate("2026-02-26"))
		before = stages.harvest_start(self._doc_without_explicit(c))
		c.actual_flowering_date = "2026-03-19"  # 3 weeks late
		c.save()
		self.assertEqual(stages.stage_start(c, "Flowering"), getdate("2026-03-19"))
		self.assertEqual(c.expected_flowering_date, getdate("2026-02-26"))  # the plan stays
		self.assertEqual(stages.stage_start(c, "Harvest"), add_days(before, 21))
		self.assertEqual([str(r.actual_date) for r in c.stage_actuals if r.stage == "Flowering"], ["2026-03-19"])

	def _doc_without_explicit(self, c):
		d = frappe.get_doc("Production Crop Cycle", c.name)
		d.expected_harvest_start = None
		return d

	def test_flag_late_flowering(self):
		c = self._cycle(start=add_days(today(), -120))
		c.actual_flowering_date = add_days(c.expected_flowering_date, 21)
		c.save()
		fl = cycle_chain.flags(c)
		self.assertEqual(len(fl), 1)
		self.assertIn("3 weeks late", fl[0])
		self.assertEqual(c.flag_count, 1)
		self.assertIn("3 weeks late", c.protocol_flags)

	def test_flag_within_tolerance_none(self):
		c = self._cycle(start=add_days(today(), -120))
		c.actual_flowering_date = add_days(c.expected_flowering_date, 14)
		c.save()
		self.assertEqual(cycle_chain.flags(c), [])
		self.assertEqual(c.flag_count, 0)

	def test_flag_missing_actual(self):
		c = self._cycle(start=add_days(today(), -200))
		fl = cycle_chain.flags(c)
		self.assertTrue(any("flowering" in f and "nothing recorded" in f for f in fl), fl)
		c2 = self._cycle(start=add_days(today(), -300))
		self.assertTrue(any("harvest due" in f and "nothing recorded" in f for f in cycle_chain.flags(c2)))
		self.assertEqual(cycle_chain.refresh_flags(c2.name), c2.reload().flag_count)
		self.assertGreaterEqual(cycle_chain.refresh_flags_all(), 1)

	def _close(self, c, end=None):
		c.status = "Closed"
		c.actual_harvest_end = end or add_days(today(), -3)
		c.save()
		return c

	def test_close_proposes_next_with_reflower(self):
		c = self._close(self._cycle(start=add_days(today(), -400)))
		self.assertTrue(c.proposed_next_cycle)
		n = frappe.get_doc("Production Crop Cycle", c.proposed_next_cycle)
		self.assertEqual((n.status, n.previous_cycle, n.cycle_no, n.unit, n.variety),
			("Planned", c.name, 2, c.unit, self.hass))
		self.assertEqual(n.start_date, getdate(c.actual_harvest_end))
		self.assertEqual(n.expected_flowering_date, add_days(c.expected_flowering_date, 52 * 7))
		self.assertEqual(n.expected_harvest_start, add_days(n.expected_flowering_date, 210))

	def test_close_proposes_once(self):
		c = self._close(self._cycle(start=add_days(today(), -400)))
		first = c.proposed_next_cycle
		c.notes = "again"
		c.save()
		self.assertEqual(c.proposed_next_cycle, first)
		self.assertIsNone(cycle_chain.propose_next(c))
		self.assertEqual(frappe.db.count("Production Crop Cycle", {"previous_cycle": c.name}), 1)

	def test_once_variety_no_proposal(self):
		c = self._close(self._cycle(variety=self.once, start=add_days(today(), -100)))
		self.assertFalse(c.proposed_next_cycle)
		self.assertEqual(frappe.db.count("Production Crop Cycle", {"previous_cycle": c.name}), 0)

	def test_lifespan_marks_uprooting(self):
		c = self._close(self._cycle(variety=self.short, start=add_days(today(), -400)))
		self.assertFalse(c.proposed_next_cycle)
		self.assertEqual(c.due_for_uprooting, 1)

	def test_cycle_flags_api(self):
		from upande_production.api import production as api

		c = self._cycle(start=add_days(today(), -200))
		r = api.cycle_flags(self.crop.name)
		rows = r.get("rows") if "rows" in r else r["message"]["rows"]
		self.assertTrue(any(x["cycle"] == c.name and x["flags"] for x in rows))

	def test_save_cycle_returns_proposed(self):
		from upande_production.api import production as api

		c = self._cycle(start=add_days(today(), -400))
		r = api.save_cycle({"name": c.name, "status": "Closed", "actual_harvest_end": str(add_days(today(), -2))})
		r = r.get("message", r)
		self.assertTrue(r["proposed_next_cycle"])
		r2 = api.save_cycle({"name": c.name, "notes": "x"})
		self.assertIsNone(r2.get("message", r2)["proposed_next_cycle"])


	# ---- review fixes

	def _prev_closed(self, variety=None):
		return self._close(self._cycle(variety=variety, start=add_days(today(), -400)))

	def test_numbering_by_pattern(self):
		prev = self._prev_closed()
		c = _make("Production Crop Cycle", unit=self.unit.name, crop=self.crop.name, variety=self.hass,
			start_date=add_days(today(), -2), status="Planned", previous_cycle=prev.name).reload()
		self.assertEqual(c.cycle_no, prev.cycle_no + 1)
		self.assertEqual(c.expected_flowering_date, add_days(prev.expected_flowering_date, 52 * 7))
		self.assertEqual(c.expected_harvest_start, add_days(c.expected_flowering_date, 210))
		prev_once = self._close(self._cycle(variety=self.once, start=add_days(today(), -100)))
		o = _make("Production Crop Cycle", unit=self.unit.name, crop=self.crop.name, variety=self.once,
			start_date=add_days(today(), -2), status="Planned", previous_cycle=prev_once.name)
		self.assertEqual(o.cycle_no, 1)

	def test_renumber_patch(self):
		from upande_production.patches import renumber_cycles_by_pattern

		prev_once = self._close(self._cycle(variety=self.once, start=add_days(today(), -100)))
		o = _make("Production Crop Cycle", unit=self.unit.name, crop=self.crop.name, variety=self.once,
			start_date=add_days(today(), -2), status="Planned", previous_cycle=prev_once.name)
		prev = self._prev_closed()
		n = frappe.get_doc("Production Crop Cycle", prev.proposed_next_cycle)
		frappe.db.set_value("Production Crop Cycle", o.name, "cycle_no", 2)
		renumber_cycles_by_pattern.execute()
		self.assertEqual(frappe.db.get_value("Production Crop Cycle", o.name, "cycle_no"), 1)
		self.assertEqual(frappe.db.get_value("Production Crop Cycle", n.name, "cycle_no"), 2)

	def test_picks_set_actual_harvest_start(self):
		c = self._cycle(start=add_days(today(), -300))
		self.assertTrue(any("harvest due" in f for f in cycle_chain.flags(c)))
		d1, d2 = add_days(today(), -20), add_days(today(), -10)
		for d in (d2, d1):
			_make("Production Harvest", harvest_date=d, unit=self.unit.name, crop=self.crop.name, cycle=c.name, qty=5)
		c.reload()
		self.assertEqual(c.actual_harvest_start, getdate(d1))
		self.assertFalse(any("harvest due" in f for f in cycle_chain.flags(c)))
		c.reload()
		c.actual_harvest_start = None
		c.save()
		self.assertEqual(c.actual_harvest_start, getdate(d1))

	def test_no_flowering_flag_when_flowering_is_anchor(self):
		c = self._cycle(variety=self.fl, start=add_days(today(), -300))
		c.actual_flowering_date = add_days(c.start_date, -190)
		c.save()
		self.assertFalse(any("flower" in f for f in cycle_chain.flags(c)), cycle_chain.flags(c))

	def test_later_cycle_day0_is_flowering(self):
		prev = self._prev_closed(self.fl)
		c = _make("Production Crop Cycle", unit=self.unit.name, crop=self.crop.name, variety=self.fl,
			start_date=add_days(today(), -2), status="Planned", previous_cycle=prev.name).reload()
		self.assertEqual(c.cycle_no, 2)
		ef = add_days(prev.expected_flowering_date, 64 * 7)
		self.assertEqual(c.expected_flowering_date, ef)
		self.assertEqual(stages.stage_start(c, "Flowering"), ef)
		self.assertEqual(stages.stage_start(c, "Harvest"), add_days(ef, 252))
		self.assertEqual(stages.anchor_date(c), ef)
		self.assertEqual(stages.stage_on(c, ef)["stage"], "Flowering")

	def test_actual_flowering_moves_expected_harvest(self):
		prev = self._prev_closed(self.fl)
		c = _make("Production Crop Cycle", unit=self.unit.name, crop=self.crop.name, variety=self.fl,
			start_date=add_days(today(), -2), status="Planned", previous_cycle=prev.name).reload()
		c.actual_flowering_date = add_days(c.expected_flowering_date, 21)
		c.save()
		c.reload()
		self.assertEqual(c.expected_harvest_start, add_days(c.actual_flowering_date, 252))
		self.assertEqual(stages.harvest_start(c), add_days(c.actual_flowering_date, 252))
		self.assertEqual(c.expected_harvest_end, add_days(c.expected_harvest_start, 56))
		# an explicit change in the same save wins
		c.actual_flowering_date = add_days(c.expected_flowering_date, 28)
		c.expected_harvest_start = add_days(today(), 400)
		c.save()
		c.reload()
		self.assertEqual(c.expected_harvest_start, getdate(add_days(today(), 400)))

	def test_flags_manager_only(self):
		from upande_production.api import production as api

		c = self._cycle(start=add_days(today(), -200))
		self.assertTrue(cycle_chain.flags(c))
		user = "ccflags@example.com"
		if not frappe.db.exists("User", user):
			frappe.get_doc({"doctype": "User", "email": user, "first_name": "CCF", "send_welcome_email": 0,
				"roles": [{"role": "Production Operator"}] if frappe.db.exists("Role", "Production Operator") else []}).insert()
		try:
			frappe.set_user(user)
			self.assertFalse(api._can_see_flags())
			frappe.set_user("Administrator")
			self.assertTrue(api._can_see_flags())
		finally:
			frappe.set_user("Administrator")
		rows = api.list_cycles(self.crop.name)
		rows = rows.get("cycles") or rows["message"]["cycles"]
		self.assertTrue(any(r["name"] == c.name and r["flags"] for r in rows))


	# ---- Addendum 2026-10-29: maturity, seasons, intervals, juvenile

	@classmethod
	def _seasonal(cls, name="CC Seasonal", maturity=130, shares=(80, 20), anchor="Planting"):
		return _make("Production Variety", variety_name=name, crop=cls.crop.name, item=cls.item, is_flowering=1,
			harvest_pattern="Interval", harvest_interval_weeks=52, lifespan_years=25, weeks_to_maturity=maturity,
			flowering_pattern="Seasonal", stage_anchor=anchor, harvest_window_weeks=8,
			flowering_seasons=[
				{"season_name": "Main", "start_month": "August", "weeks_flowering_to_harvest": 36, "crop_share_pct": shares[0]},
				{"season_name": "Off", "start_month": "February", "weeks_flowering_to_harvest": 30, "crop_share_pct": shares[1]}],
			stages=_stages(("Planting", 0, 56, 0), ("Flowering", 56, 28, 0), ("Harvest", 266, 56, 1))).name

	def _unit(self, name):
		return _make("Production Unit", unit_name=name, unit_type="Orchard Block", crop=self.crop.name,
			farm=self.farm.name, company=self.company)

	def test_seasonal_first_season_after_maturity(self):
		v = self._seasonal("CC Seasonal 1")
		d = cycle_chain.first_season_date(getdate("2023-04-10"), v)  # + 130 weeks = 2025-11-03
		self.assertEqual(d, getdate("2026-02-01"))
		self.assertEqual(cycle_chain.first_season_date(getdate("2023-01-02"), v), getdate("2025-08-01"))  # 2025-07-07 ->
		u = self._unit("CC Block Seas1")
		c = _make("Production Crop Cycle", unit=u.name, crop=self.crop.name, variety=v, start_date="2023-04-10",
			status="Planned").reload()
		self.assertEqual((c.expected_flowering_date, c.flowering_season), (getdate("2026-02-01"), "Off"))
		self.assertEqual(c.expected_harvest_start, add_days(getdate("2026-02-01"), 30 * 7))

	def test_seasonal_next_season_by_calendar(self):
		v = self._seasonal("CC Seasonal 2")
		row, d = cycle_chain.next_season(v, getdate("2026-02-01"))
		self.assertEqual((row["season_name"], d), ("Main", getdate("2026-08-01")))
		row, d = cycle_chain.next_season(v, getdate("2026-08-20"))
		self.assertEqual((row["season_name"], d), ("Off", getdate("2027-02-01")))
		u = self._unit("CC Block Seas2")
		c = _make("Production Crop Cycle", unit=u.name, crop=self.crop.name, variety=v, start_date="2023-04-10",
			status="Active")
		c = self._close(c, end="2026-11-30")
		n = frappe.get_doc("Production Crop Cycle", c.proposed_next_cycle)
		self.assertEqual((n.flowering_season, n.expected_flowering_date), ("Off", getdate("2027-02-01")))
		self.assertEqual(n.expected_harvest_start, add_days(getdate("2027-02-01"), 30 * 7))

	def test_interval_next_flowering(self):
		v = _make("Production Variety", variety_name="CC Passion", crop=self.crop.name, item=self.item, is_flowering=1,
			harvest_pattern="Continuous", harvest_interval_weeks=1, weeks_to_maturity=30, flowering_pattern="Interval",
			flowering_interval_weeks=4, weeks_to_first_flowering=20, weeks_flowering_to_harvest=10, lifespan_years=3,
			harvest_window_weeks=6, stages=_stages(("Planting", 0, 140, 0), ("Flowering", 140, 70, 0), ("Harvest", 210, 60, 1))).name
		u = self._unit("CC Block Int")
		c = self._close(_make("Production Crop Cycle", unit=u.name, crop=self.crop.name, variety=v,
			start_date=add_days(today(), -100), status="Active"))
		n = frappe.get_doc("Production Crop Cycle", c.proposed_next_cycle)
		self.assertGreaterEqual(n.expected_flowering_date, n.start_date)
		self.assertEqual((n.expected_flowering_date - c.expected_flowering_date).days % 28, 0)
		self.assertEqual(n.expected_harvest_start, add_days(n.expected_flowering_date, 70))

	def test_juvenile_cycle_no_projection_yield(self):
		from upande_production.production.logic import analytics, breakeven

		v = self._seasonal("CC Seasonal 3", maturity=130)
		u = self._unit("CC Block Juv")
		c = _make("Production Crop Cycle", unit=u.name, crop=self.crop.name, variety=v, start_date=add_days(today(), -30),
			status="Active", expected_harvest_start=add_days(today(), 100)).reload()
		# planted a year ago, mature only in ~2.5 years: the first harvest is before maturity
		_make("Block Opening Balance", unit=u.name, as_of_date=today(), planted_on=add_days(today(), -365),
			crop=self.crop.name, setup_cost=0, running_costs_to_date=0, value_recovered_to_date=0)
		c = frappe.get_doc("Production Crop Cycle", c.name)
		self.assertTrue(cycle_chain.is_juvenile(c))
		c.save()
		self.assertEqual(c.reload().juvenile, 1)
		self.assertEqual(analytics.current_cycles(self.crop.name)[u.name].juvenile, 1)
		fc = _make("Production Forecast", unit=u.name, crop=self.crop.name, cycle=c.name,
			weeks=[{"week_start": add_days(today(), 7), "expected_qty": 100}]) if frappe.db.exists("DocType", "Production Forecast") else None
		if fc:
			self.assertIsNone(breakeven._forecast_value([u.name], self.crop.name))
		old = frappe.get_doc("Production Crop Cycle", c.name)
		old.expected_harvest_start = add_days(today(), 365 * 3)
		self.assertFalse(cycle_chain.is_juvenile(old))

	def test_seasonal_flowering_flag_late(self):
		v = self._seasonal("CC Seasonal 4", anchor="Flowering")
		u = self._unit("CC Block Late")
		c = _make("Production Crop Cycle", unit=u.name, crop=self.crop.name, variety=v, start_date=add_days(today(), -100),
			status="Active")
		# first cycle of a seasonal variety is no longer exempt: flowering 3 weeks after its season start
		c.actual_flowering_date = add_days(c.expected_flowering_date, 21)
		c.save()
		fl = cycle_chain.flags(c)
		self.assertTrue(any("3 weeks late" in f for f in fl), fl)

	def test_existing_seasonal_cycle_backfills_season(self):
		v = self._seasonal("CC Seasonal Back")
		u = self._unit("CC Block Back")
		c = _make("Production Crop Cycle", unit=u.name, crop=self.crop.name, variety=v, start_date="2023-04-10",
			status="Active")
		frappe.db.set_value(c.doctype, c.name, {"flowering_season": None, "expected_flowering_date": "2026-09-05",
			"expected_harvest_start": "2027-01-01", "actual_flowering_date": "2026-08-22"})
		c = frappe.get_doc(c.doctype, c.name)
		c.save()  # season whose start is nearest on or before the actual flowering (2026-08-22): Main (August)
		c.reload()
		self.assertEqual((c.flowering_season, c.expected_flowering_date), ("Main", getdate("2026-08-01")))
		self.assertEqual(c.expected_harvest_start, add_days(getdate("2026-08-22"), 36 * 7))

	def test_shares_must_total_100(self):
		with self.assertRaises(frappe.ValidationError):
			self._seasonal("CC Seasonal Bad", shares=(80, 30))
		with self.assertRaises(frappe.ValidationError):
			_make("Production Variety", variety_name="CC Seasonal None", crop=self.crop.name, item=self.item,
				is_flowering=1, flowering_pattern="Seasonal")
		with self.assertRaises(frappe.ValidationError):
			_make("Production Variety", variety_name="CC Int None", crop=self.crop.name, item=self.item,
				is_flowering=1, flowering_pattern="Interval", harvest_pattern="Interval", harvest_interval_weeks=4)
		self._seasonal("CC Seasonal OK", shares=(0, 0))  # no shares set is fine
