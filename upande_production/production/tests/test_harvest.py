import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import flt, today

from upande_production.mobile import harvest as api
from upande_production.production.logic import harvest as H


def _make(doctype, **kw):
	doc = frappe.get_doc({"doctype": doctype, **kw})
	doc.insert()
	return doc


class TestHarvest(IntegrationTestCase):
	"""Crates -> batch -> Harvesting stock entry. Nothing here commits, so the class rolls back."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		for uom in ("Kg", "Crate"):
			if not frappe.db.exists("UOM", uom):
				_make("UOM", uom_name=uom)
		if not frappe.db.exists("Farm Type", "Has Blocks"):
			_make("Farm Type", name="Has Blocks")
		if not frappe.db.exists("Item Group", "All Item Groups"):
			_make("Item Group", item_group_name="All Item Groups", is_group=1)
		cls.farm = _make("Farm", farm_name="HV Farm", company=cls.company, abbreviation="HVF",
			farm_type=[{"farm_type": "Has Blocks"}])
		cls.crop = _make("Production Crop", crop_name="HV Crop", crop_key="hv-crop", unit_label="Block",
			yield_uom="Kg", enabled=1, harvests_in_crates=1, avg_kg_per_crate=10, uses_crop_cycles=1)
		cls.flat_crop = _make("Production Crop", crop_name="HV Flat", crop_key="hv-flat", unit_label="Pond",
			yield_uom="Kg", enabled=1, uses_crop_cycles=0)
		cls.item = _make("Item", item_code="HV Fruit", item_name="HV Fruit", item_group="All Item Groups",
			stock_uom="Kg", is_stock_item=1, valuation_rate=8)
		cls.item2 = _make("Item", item_code="HV Fruit Big", item_name="HV Fruit Big", item_group="All Item Groups",
			stock_uom="Kg", is_stock_item=1, valuation_rate=0, production_avg_kg_per_crate=25)
		cls.unit = _make("Production Unit", unit_name="HV Block 1", crop=cls.crop.name, farm=cls.farm.name,
			unit_type="Orchard Block", company=cls.company)
		cls.unit2 = _make("Production Unit", unit_name="HV Block 2", crop=cls.crop.name, farm=cls.farm.name,
			unit_type="Orchard Block", company=cls.company)
		cls.flat = _make("Production Unit", unit_name="HV Pond", crop=cls.flat_crop.name, farm=cls.farm.name,
			unit_type="Pond", company=cls.company)
		for u, item in ((cls.unit, cls.item), (cls.unit2, cls.item2)):
			_make("Production Crop Cycle", title=f"HV {u.name}", unit=u.name, crop=cls.crop.name, item=item.name,
				cycle_type="Season", start_date=today(), status="Harvesting")
		cls.leader = cls._emp("HVLeader")
		cls.p1, cls.p2 = cls._emp("HVPickerA"), cls._emp("HVPickerB")
		cls.team = _make("Harvest Team", team_number="HV-T1", team_leader=cls.leader.name, unit=cls.unit.name,
			harvestors=[{"employee": cls.p1.name}, {"employee": cls.p2.name}])
		cls.unit4 = _make("Production Unit", unit_name="HV Block 4", crop=cls.crop.name, farm=cls.farm.name,
			unit_type="Orchard Block", company=cls.company)
		_make("Production Crop Cycle", title="HV c4", unit=cls.unit4.name, crop=cls.crop.name, item=cls.item.name,
			cycle_type="Season", start_date=today(), status="Harvesting")
		_make("Harvest Team", team_number="HV-T2", team_leader=cls.leader.name, unit=cls.unit4.name,
			harvestors=[{"employee": cls.p1.name}])
		cls.warehouse = H.ensure_harvest_warehouse("HV Harvest Store", cls.company)
		frappe.db.set_single_value("Production Settings", "harvest_warehouse", cls.warehouse)
		frappe.db.set_single_value("Production Settings", "harvest_default_rate", 5)
		cls.n = 0

	@classmethod
	def _emp(cls, first):
		return _make("Employee", first_name=first, gender="Male", date_of_birth="1990-01-01",
			date_of_joining="2020-01-01", company=cls.company)

	def setUp(self):
		# tests share the class transaction: start each with no scans of ours
		frappe.db.delete("Harvest Crate Scan", {"crate_id": ("like", "HVC-%")})

	def crates(self, n):
		out = []
		for _i in range(n):
			type(self).n += 1
			cid = f"HVC-{self.n:04d}"
			_make("Harvest Crate", crate_id=cid, status="Active", farm=self.farm.name)
			out.append(cid)
		return out

	def scan(self, n, unit=None, harvestor=None, team="HV-T1"):
		res = api.scan_crates_bulk(crate_ids=self.crates(n), team_id=team, block=(unit or self.unit).name, harvestor=harvestor)
		self.assertNotIn("error", res)
		self.assertEqual(res["fail_count"], 0)
		return res

	def close(self, unit=None, team="HV-T1"):
		return api.mark_ready_for_collection(block=(unit or self.unit).name, team_id=team)

	# -- scan -> batch -> stock entry
	def test_close_batch_posts_stock_entry_and_records(self):
		self.scan(3, harvestor=self.p1.name)
		self.scan(2, harvestor=self.p2.name)
		res = self.close()
		self.assertEqual(res["crate_count"], 5)
		self.assertEqual(res["estimated_kg"], 50)  # 5 crates x crop default 10 kg
		batch = frappe.get_doc("Harvest Batch", res["batch"])
		self.assertEqual((batch.docstatus, batch.status, batch.item), (1, "Closed", self.item.name))
		se = frappe.get_doc("Stock Entry", batch.stock_entry)
		self.assertEqual((se.docstatus, se.stock_entry_type, se.purpose), (1, "Harvesting", "Material Receipt"))
		self.assertEqual(se.production_harvest_batch, batch.name)
		self.assertEqual(len(se.items), 1)
		row = se.items[0]
		self.assertEqual((row.item_code, row.qty, row.uom), (self.item.name, 50, "Kg"))
		self.assertEqual(row.t_warehouse, self.warehouse)
		self.assertEqual(row.cost_center, frappe.db.get_value("Production Unit", self.unit.name, "cost_center"))
		self.assertEqual(row.basic_rate, 8)  # the item's valuation rate
		self.assertEqual((row.production_harvest_batch, row.production_unit, row.production_crates), (batch.name, self.unit.name, 5))
		# production harvest
		ph = frappe.get_doc("Production Harvest", batch.production_harvest)
		self.assertEqual((ph.qty, ph.unit, ph.crop, ph.item, ph.harvest_batch, ph.stock_entry),
			(50, self.unit.name, self.crop.name, self.item.name, batch.name, se.name))
		# picker work: drafts, pending, qty = crates scanned by the picker
		work = frappe.get_all("Value Adder Work", filters={"harvest_batch": batch.name},
			fields=["employee", "qty", "uom", "docstatus", "approval_status", "unit", "operation"])
		self.assertEqual({w.employee: w.qty for w in work}, {self.p1.name: 3, self.p2.name: 2})
		for w in work:
			self.assertEqual((w.uom, w.docstatus, w.approval_status, w.unit), ("Crate", 0, "Pending", self.unit.name))
		self.assertEqual(frappe.db.get_value("Production Operation", work[0].operation, "work_uom"), "Crate")
		# crates are batched
		for r in batch.crates:
			self.assertEqual(frappe.db.get_value("Harvest Crate Scan", r.crate_scan, ["status", "batch_id_ref"]), ("Batched", batch.name))
		# nothing left to close
		self.assertEqual(self.close()["crate_count"], 0)

	def test_item_override_and_zero_valuation_fallback(self):
		self.scan(2, unit=self.unit2)
		res = self.close(self.unit2)
		self.assertEqual(res["avg_kg_per_crate"], 25)  # the item's own figure beats the crop's
		self.assertEqual(res["estimated_kg"], 50)
		row = frappe.get_doc("Stock Entry", res["stock_entry"]).items[0]
		self.assertEqual(row.basic_rate, 5)  # Production Settings fallback: item has no valuation rate
		self.assertEqual(frappe.get_doc("Production Operation", H.harvest_operation(self.crop.name)).work_uom, "Crate")

	def test_unassigned_crates_are_shared_over_the_team(self):
		self.scan(4)
		res = self.close()
		work = {w.employee: w.qty for w in frappe.get_all("Value Adder Work", filters={"harvest_batch": res["batch"]}, fields=["employee", "qty"])}
		self.assertEqual(work, {self.p1.name: 2, self.p2.name: 2})

	def test_cancel_reverses_everything(self):
		self.scan(3, harvestor=self.p1.name)
		res = self.close()
		batch = frappe.get_doc("Harvest Batch", res["batch"])
		scans = [r.crate_scan for r in batch.crates]
		batch.cancel()
		self.assertEqual(frappe.db.get_value("Stock Entry", res["stock_entry"], "docstatus"), 2)
		self.assertFalse(frappe.db.exists("Production Harvest", res["production_harvest"]))
		self.assertEqual(frappe.db.count("Value Adder Work", {"harvest_batch": batch.name}), 0)
		self.assertEqual(frappe.db.get_value("Harvest Batch", batch.name, "status"), "Cancelled")
		for s in scans:  # crates are open again with their team
			self.assertEqual(frappe.db.get_value("Harvest Crate Scan", s, ["status", "batch_id_ref"]), ("Filling", None))
		again = self.close()
		self.assertEqual(again["crate_count"], 3)
		self.assertNotEqual(again["batch"], batch.name)

	def test_cancel_refused_once_work_is_approved(self):
		self.scan(2, harvestor=self.p1.name)
		res = self.close()
		vaw = frappe.get_doc("Value Adder Work", frappe.get_all("Value Adder Work", filters={"harvest_batch": res["batch"]}, pluck="name")[0])
		vaw.submit()
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc("Harvest Batch", res["batch"]).cancel()
		self.assertEqual(frappe.db.get_value("Stock Entry", res["stock_entry"], "docstatus"), 1)

	# -- refusals
	def test_duplicate_scan_refused(self):
		cid = self.crates(1)[0]
		ok = api.scan_crate(crate_id=cid, team_id="HV-T1", block=self.unit.name)
		self.assertEqual((ok["status"], ok["crate_id"]), ("Filling", cid))
		dup = api.scan_crate(crate_id=cid, team_id="HV-T1", block=self.unit.name)
		self.assertEqual((dup["error"], dup["in_use"]), ("Crate already in use", True))
		bulk = api.scan_crates_bulk(crate_ids=[cid, "HV-NOPE", "", "HV-NOPE"], team_id="HV-T1", block=self.unit.name)
		self.assertEqual([r["error"] for r in bulk["results"]],
			["Crate already in use", "Not in registry", "Empty crate id", "Duplicate in this batch"])
		self.assertEqual((bulk["ok_count"], bulk["fail_count"]), (0, 4))
		self.assertIn("not in registry", api.scan_crate(crate_id="HV-NOPE", team_id="HV-T1")["error"])

	def test_scan_validations(self):
		cid = self.crates(1)[0]
		self.assertIn("required", api.scan_crate(crate_id=cid)["error"])
		self.assertIn("not found", api.scan_crate(crate_id=cid, team_id="no-such-team")["error"])
		self.assertIn("not harvested in crates", api.scan_crate(crate_id=cid, team_id="HV-T1", block=self.flat.name)["error"])
		frappe.db.set_value("Harvest Crate", cid, "status", "Damaged")
		self.assertEqual(api.scan_crate(crate_id=cid, team_id="HV-T1", block=self.unit.name)["error"], "Crate is Damaged")

	def test_batch_needs_a_current_item(self):
		unit = _make("Production Unit", unit_name="HV Block 3", crop=self.crop.name, farm=self.farm.name,
			unit_type="Orchard Block", company=self.company)
		self.scan(1, unit=unit)
		res = self.close(unit)
		self.assertIn("no current cycle", res["error"])

	# -- avocado mirror
	def test_avocado_block_writes_log_without_double_counting(self):
		code = "HVA"
		if not frappe.db.exists("Avocado Yield Block", code):
			_make("Avocado Yield Block", block_code=code, area_ha=1, farm=self.farm.name, status="Active")
		frappe.db.set_value("Production Unit", self.unit.name, "avocado_block_code", code)
		self.scan(20, harvestor=self.p1.name)  # 200 kg: a plausible day for one picker
		res = self.close()
		log = frappe.db.get_value("Harvest Batch", res["batch"], "avocado_harvest_log")
		self.assertTrue(log)
		row = frappe.db.get_value("Avocado Harvest Log", log, ["orchard_block", "total_kg", "harvest_date", "client_ref"], as_dict=True)
		self.assertEqual((row.orchard_block, row.total_kg, row.client_ref), (code, 200, H.BATCH_LOG_PREFIX + res["batch"]))
		from upande_production.api.avocadolabour import is_plausible
		self.assertTrue(is_plausible(frappe.get_doc("Avocado Harvest Log", log)))
		# the avocado seed's mirror skips batch logs, so the batch's own Production Harvest is the only one
		self.assertEqual(frappe.db.count("Production Harvest", {"harvest_batch": res["batch"]}), 1)
		frappe.get_doc("Harvest Batch", res["batch"]).cancel()
		self.assertFalse(frappe.db.exists("Avocado Harvest Log", log))

	# -- response shapes the app reads
	def test_response_shapes(self):
		self.scan(2, unit=self.unit4, harvestor=self.p1.name, team="HV-T2")
		farms = api.get_farms()
		self.assertIn({"name": self.farm.name, "farm_name": "HV Farm", "farm_code": "HVF"}, farms)
		secs = api.get_sections(farm=self.farm.name)
		self.assertEqual(secs, [{"name": "HV Crop", "label": "HV Crop", "crop": "HV Crop"}])  # the non-crate crop is not listed
		blocks = api.get_blocks(farm="HV Farm", section="HV Crop")
		self.assertTrue({self.unit.name, self.unit2.name} <= {b["name"] for b in blocks})
		self.assertTrue(all({"name", "label"} <= set(b) for b in blocks))
		self.assertEqual(api.get_blocks(farm="HVF", crop=self.flat_crop.name), [])  # flat crop harvests in no crates
		self.assertIn("error", api.get_blocks())
		leaders = [t for t in api.get_team_leaders() if t["team_number"] == "HV-T1"]
		self.assertEqual(leaders, [{"employee_code": self.leader.name, "name": "HVLeader", "team_number": "HV-T1",
			"block": self.unit.name, "label": "HVLeader — HV-T1"}])
		hv = [h for h in api.get_harvestors() if h["team_number"] == "HV-T1"]
		self.assertEqual({h["employee_code"] for h in hv}, {self.p1.name, self.p2.name})
		self.assertEqual(set(hv[0]), {"employee_code", "name", "team_number", "team_id", "block", "label"})
		state = api.get_harvesting_state(block=self.unit4.name)
		self.assertEqual(set(state), {"totals", "by_harvestor", "batches", "not_collected"})
		self.assertEqual(set(state["totals"]), {"total", "filling", "full", "in_transit", "batches", "not_collected"})
		self.assertEqual((state["totals"]["total"], state["totals"]["filling"], state["totals"]["not_collected"]), (2, 2, 2))
		self.assertEqual(state["by_harvestor"][0]["employee_code"], self.p1.name)
		self.assertEqual(set(state["not_collected"][0]), {"crate_id", "harvestor", "harvestor_name", "status", "allocated_at"})
		self.assertEqual(api.get_harvesting_state()["error"], "block is required")
		res = self.close(self.unit4, "HV-T2")
		self.assertEqual(set(res) >= {"team_id", "team_number", "resolved_team", "block", "crate_count", "crates_marked"}, True)
		self.assertEqual((res["team_number"], res["block"], len(res["crates_marked"])), ("HV-T2", self.unit4.name, 2))
		state = api.get_harvesting_state(block=self.unit4.name)
		self.assertEqual(state["totals"]["batches"], 1)
		self.assertEqual(set(state["batches"][0]), {"batch_id", "delivery_note", "status", "team_id", "creation", "stock_entry", "crates", "estimated_kg"})
		today_ = api.get_team_harvest_today(team_id="HV-T2")
		self.assertEqual(set(today_), {"team_id", "total", "filling", "full", "ready", "in_transit", "received"})
		self.assertEqual((today_["total"], today_["ready"], today_["filling"]), (2, 2, 0))
		kpi = api.get_harvest_kpis(team_id="HV-T2")
		self.assertEqual(set(kpi), {"total_today", "team_total_today", "team_not_collected", "team_collected", "me_total_today",
			"me_not_collected", "me_collected", "team_id", "user", "date"})
		self.assertEqual((kpi["team_total_today"], kpi["team_collected"], kpi["team_not_collected"]), (2, 2, 0))
		sess = api.get_session_info()
		self.assertEqual(set(sess) >= {"user", "full_name", "roles", "is_loading_clerk", "is_packhouse_receiver"}, True)
		self.assertTrue(sess["is_farm_manager"])
		rep = api.farm_manager_report(period="today")
		self.assertEqual(set(rep), {"period", "label", "plan_total", "per_team_target", "active_team_count", "totals", "teams", "blocks", "block_changes"})
		self.assertEqual(set(rep["totals"]) >= {"harvested", "in_field", "on_road", "at_packhouse", "returned", "delivery_rate_pct"}, True)
		team = next(t for t in rep["teams"] if t["team_number"] == "HV-T2")
		self.assertEqual(set(team) >= {"team_id", "team_number", "leader_name", "harvested", "in_field", "on_road", "at_packhouse", "returned",
			"delivery_rate_pct", "target", "progress_pct", "blocks", "block_change", "current_block", "last_user", "last_user_name", "last_at"}, True)
		self.assertEqual((team["harvested"], team["at_packhouse"], team["current_block"], team["estimated_kg"]), (2, 2, self.unit4.name, 20))
		self.assertIn(self.unit4.name, [b["block"] for b in rep["blocks"]])
		self.assertEqual(api.farm_manager_report(period="week")["label"], "Last 7 days")

	def test_fix_a_crate_block_and_bulk_create(self):
		cid = self.crates(1)[0]
		api.scan_crate(crate_id=cid, team_id="HV-T1", block=self.unit.name)
		look = api.lookup_crate_for_fix(crate_id=cid)
		self.assertEqual(set(look), {"crate_id", "doc_name", "block", "status", "team_id", "team_number", "leader_name", "allocated_at", "batch_id"})
		self.assertEqual((look["block"], look["team_number"], look["leader_name"]), (self.unit.name, "HV-T1", "HVLeader"))
		self.assertEqual(api.lookup_crate_for_fix(crate_id="HV-NOPE")["error"], "Crate HV-NOPE not found")
		upd = api.update_crate_block(crate_id=cid, new_block=self.unit2.name)
		self.assertEqual((upd["ok"], upd["old_block"], upd["new_block"]), (True, self.unit.name, self.unit2.name))
		self.assertEqual(set(upd), {"ok", "crate_id", "old_block", "new_block", "changed_by"})
		# a batched crate cannot move
		self.scan(1)
		res = self.close()
		moved = api.update_crate_block(crate_id=res["crates_marked"][0], new_block=self.unit2.name)
		self.assertIn("already in batch", moved["error"])
		made = api.bulk_create_crates(count=3, farm="HVF", prefix="HVB")
		self.assertEqual((made["created"], made["first"], made["last"]), (3, "HVB-00001", "HVB-00003"))
		self.assertEqual(api.bulk_create_crates(count=2, prefix="HVB")["first"], "HVB-00004")
		self.assertIn("count must be", api.bulk_create_crates(count=0)["error"])

	def test_json_list_param_and_stock_entry_type(self):
		ids = self.crates(2)
		res = api.scan_crates_bulk(crate_ids=frappe.as_json(ids), team_id="HV-T1", block=self.unit.name)  # form-encoded lists arrive as JSON text
		self.assertEqual(res["ok_count"], 2)
		self.assertEqual(frappe.db.get_value("Stock Entry Type", "Harvesting", "purpose"), "Material Receipt")
