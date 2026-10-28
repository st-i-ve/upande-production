from unittest import mock

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from upande_production.api import approvals as approvals_api
from upande_production.api import production as desk
from upande_production.production.logic import analytics, plans, protocols, rules, work
from upande_production.production.logic.weeks import iso_of

BEFORE, AFTER = "Not within days before harvest", "Not within days after operation"


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


class TestRules(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		if not frappe.db.exists("UOM", "Kg"):
			_make("UOM", uom_name="Kg")
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		cls.farm = _make("Farm", farm_name="TR Farm", company=cls.company, abbreviation="TRF",
			farm_type=[{"farm_type": "Has Blocks"}])
		cls.crop = _make("Production Crop", crop_name="TR Crop", crop_key="tr-crop", unit_label="Block", yield_uom="Kg").name

		def op(name, cat, harvest=0):
			return _make("Production Operation", crop=cls.crop, operation_name=name, category=cat,
				work_uom="Kg", default_rate=10, is_harvest=harvest).name

		cls.spray = op("TR Spraying", "Spraying")
		cls.weed = op("TR Weeding", "Weeding")
		cls.harvest = op("TR Harvest Picking", "Harvesting", 1)
		cls.earth = op("TR Earthing Up", "Other")
		cls.prune = op("TR Pruning", "Pruning")
		item = frappe.db.get_value("Item", {"disabled": 0}) or _make(
			"Item", item_code="TR Item", item_name="TR Item", item_group=frappe.db.get_value("Item Group", {}),
			stock_uom="Kg").name
		cls.variety = _make("Production Variety", variety_name="TR Var", crop=cls.crop, item=item, stages=[
			{"stage": "Vegetative", "start_day": 0, "length_days": 20},
			{"stage": "Tuber initiation", "start_day": 20, "length_days": 20},
			{"stage": "Bulking", "start_day": 40, "length_days": 40},
			{"stage": "Harvest", "start_day": 80, "length_days": 20, "is_harvest": 1},
		]).name
		cls.variety2 = _make("Production Variety", variety_name="TR Var2", crop=cls.crop, item=item).name

		def rule(**kw):
			return _make("Production Activity Rule", crop=cls.crop, enabled=1, **kw).name

		cls.r_phi = rule(operation_category="Spraying", rule_type=BEFORE, days=14, enforcement="Block",
			reason="Spray residues.")
		cls.r_weed = rule(operation_category="Weeding", rule_type="Not in stage", stage="Tuber initiation",
			enforcement="Warn", reason="Tubers are forming.")
		cls.r_earth = rule(operation=cls.earth, rule_type="Only in stage", stage="Vegetative", enforcement="Warn")
		cls.r_after = rule(operation_category="Harvesting", rule_type=AFTER, days=7, other_category="Spraying",
			enforcement="Block", reason="Safe period.")
		cls.emp = _make("Employee", first_name="TRE", gender="Male", date_of_birth="1990-01-01",
			date_of_joining="2020-01-01", company=cls.company).name

	def tearDown(self):
		frappe.set_user("Administrator")

	def _unit(self, crop=None, **kw):
		return _make("Production Unit", unit_name=frappe.generate_hash(length=6), crop=crop or self.crop,
			farm=self.farm.name, unit_type="Orchard Block", company=self.company, **kw).name

	def _cycle(self, ago=30, harvest_in=10, protocol=None):
		unit = self._unit()
		cy = _make("Production Crop Cycle", unit=unit, start_date=add_days(today(), -ago), status="Active",
			variety=self.variety, expected_harvest_start=add_days(today(), harvest_in), protocol=protocol)
		return unit, cy.name

	def _task(self, unit, cycle, op, due=None):
		y, w = iso_of(due or today())
		plan = plans.get_or_create_plan(self.crop, self.farm.name, y, w)
		plan.append("tasks", {"unit": unit, "cycle": cycle, "operation": op, "planned_qty": 5, "uom": "Kg",
			"rate": 10, "due_date": due or today(), "status": "Open"})
		plan.save()
		return plan, plan.tasks[-1]

	def _types(self, br):
		return {b["rule"]: b for b in br}

	# -- the engine ---------------------------------------------------------------

	def test_not_in_stage_and_worst(self):
		unit, cy = self._cycle()  # day 30: Tuber initiation
		br = rules.check(cycle=cy, operation=self.weed, on_date=today())
		self.assertEqual([b["rule"] for b in br], [self.r_weed])
		self.assertEqual((br[0]["rule_type"], br[0]["enforcement"]), ("Not in stage", "Warn"))
		self.assertIn("Tubers are forming", br[0]["message"])
		self.assertEqual(rules.worst(br), "Warn")
		# Vegetative stage (day 5): fine
		self.assertEqual(rules.check(cycle=cy, operation=self.weed, on_date=add_days(today(), -25)), [])
		self.assertEqual(rules.worst([]), "OK")

	def test_only_in_stage(self):
		unit, cy = self._cycle()
		br = rules.check(unit=unit, operation=self.earth, on_date=today())  # by unit: finds the active cycle
		self.assertEqual([b["rule_type"] for b in br], ["Only in stage"])
		self.assertEqual(rules.check(cycle=cy, operation=self.earth, on_date=add_days(today(), -28)), [])

	def test_before_harvest(self):
		unit, cy = self._cycle(harvest_in=10)
		br = rules.check(cycle=cy, operation=self.spray, on_date=today())
		self.assertEqual((br[0]["rule"], rules.worst(br)), (self.r_phi, "Block"))
		self.assertEqual(rules.check(cycle=cy, operation=self.spray, on_date=add_days(today(), -5)), [])

	def test_after_operation_both_directions_and_exclusions(self):
		unit, cy = self._cycle(harvest_in=60)
		vaw = _make("Value Adder Work", work_date=add_days(today(), -3), employee=self.emp, unit=unit, cycle=cy,
			operation=self.spray, qty=1, uom="Kg")
		# harvest 3 days after spraying: refused
		br = rules.check(cycle=cy, operation=self.harvest, on_date=today())
		self.assertEqual((br[0]["rule"], rules.worst(br)), (self.r_after, "Block"))
		self.assertIsNone(next(iter(rules.check(cycle=cy, operation=self.harvest, on_date=today(), exclude_work=vaw.name)), None))
		self.assertEqual(rules.check(cycle=cy, operation=self.harvest, on_date=add_days(today(), 5)), [])
		# a pending (draft) one counted above; the reverse: spraying with a harvest planned 2 days later
		unit2, cy2 = self._cycle(harvest_in=60)
		self._task(unit2, cy2, self.harvest, add_days(today(), 2))
		br = rules.check(cycle=cy2, operation=self.spray, on_date=today())
		self.assertEqual([b["rule"] for b in br], [self.r_after])
		self.assertIn("within 7 day", br[0]["message"])

	def test_specificity_most_specific_wins(self):
		crop_rule = _make("Production Activity Rule", crop=self.crop, operation_category="Pruning", rule_type=BEFORE,
			days=5, enforcement="Warn", enabled=1).name
		var_rule = _make("Production Activity Rule", crop=self.crop, variety=self.variety, operation=self.prune,
			rule_type=BEFORE, days=30, enforcement="Block", enabled=1).name
		self.assertEqual([r["name"] for r in rules.rules_for(self.crop, self.variety, self.prune)], [var_rule])
		self.assertEqual([r["name"] for r in rules.rules_for(self.crop, self.variety2, self.prune)], [crop_rule])
		# a different rule type is not shadowed: both apply
		other = _make("Production Activity Rule", crop=self.crop, variety=self.variety, operation_category="Pruning",
			rule_type="Not in stage", stage="Bulking", enforcement="Warn", enabled=1).name
		self.assertEqual({r["name"] for r in rules.rules_for(self.crop, self.variety, self.prune)}, {var_rule, other})
		frappe.db.set_value("Production Activity Rule", var_rule, "enabled", 0)
		self.assertEqual({r["name"] for r in rules.rules_for(self.crop, self.variety, self.prune)}, {crop_rule, other})

	def test_unit_without_cycle_uses_stocking(self):
		fish = "Aquaculture"
		if not frappe.db.exists("Production Crop", fish):
			_make("Production Crop", crop_name=fish, crop_key="aquaculture", unit_label="Pond", yield_uom="Kg",
				uses_crop_cycles=0)
		feed = _make("Production Operation", crop=fish, operation_name="TR Feeding", category="Feeding",
			work_uom="Kg", default_rate=1).name
		# operation-specific, so it wins over any crop-wide feeding rule already seeded
		r = _make("Production Activity Rule", crop=fish, operation=feed, rule_type=BEFORE, days=1,
			enforcement="Warn", enabled=1).name
		pond = _make("Production Unit", unit_name=frappe.generate_hash(length=6), crop=fish, farm=self.farm.name,
			unit_type="Pond", company=self.company).name
		self.assertEqual(rules.check(unit=pond, operation=feed, on_date=today()), [])  # no stocking, no harvest date
		_make("Pond Stocking", pond=pond, species="Tilapia", stocking_date=add_days(today(), -90), status="Growing",
			fingerlings_count=1000, avg_weight_g=5, target_harvest_date=add_days(today(), 1))
		br = rules.check(unit=pond, operation=feed, on_date=today())
		self.assertEqual([b["rule"] for b in br], [r])
		self.assertEqual(rules.check(unit=pond, operation=feed, on_date=add_days(today(), -5)), [])

	# -- enforcement --------------------------------------------------------------

	@mock.patch.object(frappe.db, "rollback")  # the desk envelope rolls back refusals: keep the class fixtures
	def test_add_task_desk(self, _rb):
		unit, cy = self._cycle()
		y, w = iso_of(today())

		def add(op, **kw):
			return desk.save_plan_tasks(self.crop, self.farm.name, y, w, [
				{"unit": unit, "cycle": cy, "operation": op, "planned_qty": 3, "due_date": today()}], **kw)

		res = add(self.spray)  # Block
		self.assertIn("error", res)
		self.assertEqual(res["rule_status"], "Block")
		res = add(self.weed)  # Warn: needs a reason
		self.assertIn("error", res)
		self.assertTrue(res["needs_override_reason"])
		res = add(self.weed, override_reason="Weeds choking the rows")
		self.assertIn("name", res)
		plan = frappe.get_doc("Production Work Plan", res["name"])
		row = [t for t in plan.tasks if t.unit == unit][-1]
		self.assertEqual((row.rule_status, row.override_reason), ("Warn", "Weeds choking the rows"))
		self.assertIn("Tubers", row.rule_notes)
		self.assertEqual(len([t for t in plan.tasks if t.unit == unit]), 1)  # the refused ones left nothing

	def test_tick_off_block_and_warn(self):
		unit, cy = self._cycle()
		entries = [{"employee": self.emp, "qty": 2}]
		plan, t = self._task(unit, cy, self.spray)
		with self.assertRaises(frappe.ValidationError) as c:
			work.record_task_work(plan.name, t.name, "Done", entries)
		self.assertIn("harvest", str(c.exception).lower())
		self.assertFalse(frappe.db.exists("Value Adder Work", {"plan_task": t.name}))

		plan, t = self._task(unit, cy, self.weed)
		with self.assertRaises(frappe.ValidationError):
			work.record_task_work(plan.name, t.name, "In Progress", entries)
		res = work.record_task_work(plan.name, t.name, "In Progress", entries, override_reason="Urgent")
		self.assertEqual((res["task"]["rule_status"], res["task"]["override_reason"]), ("Warn", "Urgent"))
		v = frappe.get_doc("Value Adder Work", res["work"][0])
		self.assertEqual((v.rule_status, v.override_reason), ("Warn", "Urgent"))
		self.assertIn("Tubers", v.rule_notes)
		# the reason stays on the task: closing it needs no new one
		self.assertEqual(work.record_task_work(plan.name, t.name, "Done", [])["task"]["status"], "Done")

		# a clean operation is stamped OK
		plan, t = self._task(unit, cy, self.prune)
		res = work.record_task_work(plan.name, t.name, "In Progress", entries)
		self.assertEqual(frappe.db.get_value("Value Adder Work", res["work"][0], "rule_status"), "OK")

	def test_unplanned_work(self):
		unit, cy = self._cycle()
		with self.assertRaises(frappe.ValidationError):
			work.record_unplanned_work(unit, self.spray, [{"employee": self.emp, "qty": 1}], today())
		with self.assertRaises(frappe.ValidationError):
			work.record_unplanned_work(unit, self.weed, [{"employee": self.emp, "qty": 1}], today())
		names = work.record_unplanned_work(unit, self.weed, [{"employee": self.emp, "qty": 1}], today(),
			override_reason="Needed")
		self.assertEqual(frappe.db.get_value("Value Adder Work", names[0], ["rule_status", "override_reason"]),
			("Warn", "Needed"))

	def test_generation_skips_block_marks_warn(self):
		proto = _make("Production Protocol", protocol_name="TR Proto", crop=self.crop, version_status="Active", key_activities=[
			{"operation": self.spray, "week": 5, "planned_qty": 1},
			{"operation": self.weed, "week": 5, "planned_qty": 1},
			{"operation": self.prune, "week": 5, "planned_qty": 1}]).name
		unit, cy = self._cycle(ago=28, protocol=proto)  # today is day 28 = the first day of week 5
		y, w = iso_of(today())
		plan = plans.get_or_create_plan(self.crop, self.farm.name, y, w)
		res = plans.generate_week_detail(plan.name)
		self.assertEqual(res["created"], 2)
		self.assertEqual([s["operation"] for s in res["skipped"]], [self.spray])
		self.assertIn("harvest", res["skipped"][0]["message"].lower())
		plan.reload()
		mine = {t.operation: t for t in plan.tasks if t.cycle == cy}
		self.assertNotIn(self.spray, mine)
		self.assertEqual(mine[self.weed].rule_status, "Warn")
		self.assertEqual(mine[self.prune].rule_status, "OK")
		self.assertTrue(frappe.db.exists("Comment", {"reference_doctype": "Production Work Plan",
			"reference_name": plan.name, "content": ("like", "Not planned: TR Spraying%")}))
		self.assertEqual(plans.generate_week(plan.name), 0)  # idempotent

		# protocol check shows the breaches per block
		chk = analytics.protocol_check(self.crop, y, w, unit)
		block = chk["blocks"][0]
		self.assertTrue(any(b["enforcement"] == "Block" for b in block["breaches"]))
		self.assertEqual({s["operation"]: s["rule_status"] for s in block["steps"]},
			{self.spray: "Block", self.weed: "Warn", self.prune: "OK"})

	def test_approvals_carry_flags(self):
		unit, cy = self._cycle()
		plan, t = self._task(unit, cy, self.weed)
		work.record_task_work(plan.name, t.name, "In Progress", [{"employee": self.emp, "qty": 2}],
			override_reason="Urgent")
		data = approvals_api.list_approvals(crop=self.crop, unit=unit)
		card = data["groups"][0]
		self.assertEqual((card["rule_status"], card["override_reason"]), ("Warn", "Urgent"))
		self.assertIn("Tubers", card["rule_notes"])
		self.assertEqual(card["entries"][0]["rule_status"], "Warn")
		self.assertEqual(card["entries"][0]["override_reason"], "Urgent")

	def test_protocol_rule_check(self):
		proto = _make("Production Protocol", protocol_name="TR Check", crop=self.crop, variety=self.variety,
			version_status="Active", key_activities=[
				{"operation": self.weed, "week": 4, "planned_qty": 1},  # day 21: Tuber initiation
				{"operation": self.spray, "week": 6, "planned_qty": 1},  # day 35: fine
				{"operation": self.earth, "week": 8, "planned_qty": 1},  # day 49: Bulking, not Vegetative
				{"operation": self.spray, "week": 11, "planned_qty": 1},  # day 70: 10 days before harvest (day 80)
				{"operation": self.harvest, "week": 11, "planned_qty": 1}])  # same day as the spray
		out = rules.rule_check(proto)
		by = {(o["operation"], o["day"]): o for o in out}
		self.assertEqual(by[(self.spray, 70)]["rule_status"], "Block")
		self.assertNotIn((self.spray, 35), by)
		self.assertEqual(by[(self.weed, 21)]["stage"], "Tuber initiation")
		self.assertEqual(by[(self.earth, 49)]["rule_status"], "Warn")
		self.assertIn((self.harvest, 70), by)  # harvest the same day as the spray
		self.assertIn("day 80", by[(self.spray, 70)]["breaches"][0]["message"])
		# the manager sees them with the diff
		d = protocols.diff(proto.name)
		self.assertEqual(len(d["rule_check"]), len(out))
		self.assertEqual(len(protocols.rule_check(proto.name)), len(out))

	# -- protocol buffers (establishment period, pre-harvest interval) ---------------

	def _buffer_cycle(self, ago=14, harvest_in=9, **row):
		op = frappe.db.get_value("Production Operation", {"crop": self.crop, "operation_name": "TR Buffer Op"}) or _make(
			"Production Operation", crop=self.crop, operation_name="TR Buffer Op", category="Other",
			work_uom="Kg", default_rate=10).name
		proto = _make("Production Protocol", protocol_name=frappe.generate_hash(length=6), crop=self.crop,
			version_status="Active", cultural_activities=[{"operation": op, "schedule": "Interval", "interval_weeks": 1,
				"establishment_period_weeks": 3, "pre_harvest_interval_days": 14, **row}]).name
		unit, cy = self._cycle(ago=ago, harvest_in=harvest_in, protocol=proto)
		return op, unit, cy

	def test_phi_breach_warns(self):
		op, unit, cy = self._buffer_cycle(ago=30)
		br = rules.check(cycle=cy, operation=op, on_date=today())
		b = next(x for x in br if x["rule_type"] == "Pre-harvest interval")
		self.assertEqual(b["enforcement"], "Warn")
		self.assertTrue(b["rule"].startswith("protocol:"))
		self.assertEqual(b["message"], "TR Buffer Op is planned 9 days before harvest; the protocol's pre-harvest interval is 14 days.")

	def test_establishment_breach_warns(self):
		op, unit, cy = self._buffer_cycle(ago=10, harvest_in=100)
		br = rules.check(cycle=cy, operation=op, on_date=today())
		self.assertEqual([b["rule_type"] for b in br], ["Establishment period"])
		self.assertIn("week 2", br[0]["message"])
		self.assertIn("3 weeks after planting", br[0]["message"])

	def test_buffer_never_blocks(self):
		op, unit, cy = self._buffer_cycle(ago=10, harvest_in=5)
		br = rules.check(cycle=cy, operation=op, on_date=today())
		self.assertEqual(len(br), 2)
		self.assertEqual(rules.worst(br), "Warn")

	def test_no_harvest_no_phi(self):
		op, unit, cy = self._buffer_cycle(ago=30)
		frappe.db.set_value("Production Crop Cycle", cy, "expected_harvest_start", None)
		with mock.patch("upande_production.production.logic.stages.harvest_start", return_value=None):
			br = rules.check(cycle=cy, operation=op, on_date=today())
		self.assertEqual(br, [])

	def test_record_work_inside_phi_needs_reason(self):
		op, unit, cy = self._buffer_cycle(ago=30)
		entries = [{"employee": self.emp, "qty": 2}]
		plan, t = self._task(unit, cy, op)
		with self.assertRaises(rules.RuleBreach) as c:
			work.record_task_work(plan.name, t.name, "In Progress", entries)
		self.assertEqual(c.exception.rule_status, "Warn")
		res = work.record_task_work(plan.name, t.name, "In Progress", entries, override_reason="Urgent")
		self.assertEqual(frappe.db.get_value("Value Adder Work", res["work"][0], "rule_status"), "Warn")
