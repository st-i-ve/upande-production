import unittest
from datetime import timedelta

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, flt, get_datetime, getdate, now_datetime, today

from upande_production.api import asset_allocation as api
from upande_production.production.logic import asset_allocation as aa
from upande_production.production.logic import geo, qr
from upande_production.production.setup.stock_entry_fields import ensure_stock_entry_fields
from upande_production.production.logic.harvest import new_warehouse


class TestAssetAllocationPure(unittest.TestCase):
	def test_hours_between(self):
		self.assertEqual(aa.hours_between("2026-11-10 07:00:00", "2026-11-10 09:30:00"), 2.5)
		self.assertEqual(aa.hours_between(None, "2026-11-10 09:30:00"), 0.0)

	def test_split_hours_over_midnight(self):
		split = aa.split_hours_by_day("2026-11-10 22:00:00", "2026-11-11 03:00:00")
		self.assertEqual(split, {"2026-11-10": 2.0, "2026-11-11": 3.0})

	def test_split_hours_clipped_to_period(self):
		split = aa.split_hours_by_day("2026-11-09 20:00:00", "2026-11-11 02:00:00", "2026-11-10", "2026-11-10")
		self.assertEqual(split, {"2026-11-10": 24.0})

	def test_day_totals_every_day_and_diesel_on_issue_day(self):
		days = aa.day_totals("2026-11-09", "2026-11-11",
			[{"start_time": "2026-11-10 08:00:00", "end_time": "2026-11-10 12:00:00"}],
			[{"posting_date": "2026-11-10", "litres": 40, "cost": 6400.0},
				{"posting_date": "2026-11-20", "litres": 5, "cost": 800.0}])
		self.assertEqual([d["date"] for d in days], ["2026-11-09", "2026-11-10", "2026-11-11"])
		self.assertEqual(days[1], {"date": "2026-11-10", "diesel_litres": 40.0, "diesel_cost": 6400.0, "machine_hours": 4.0})
		self.assertEqual(days[0]["machine_hours"], 0.0)

	def test_parse_scan_code(self):
		self.assertEqual(qr.parse_scan_code("https://farm.example/production_app?machine=AB12CD#/_/scan"), "AB12CD")
		self.assertEqual(qr.parse_scan_code("  AB12CD "), "AB12CD")
		self.assertEqual(qr.parse_scan_code(""), "")


class TestAssetAllocation(IntegrationTestCase):
	"""Machine -> scan to start -> scan to close -> submit posts the diesel Material Issue."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		ensure_stock_entry_fields()
		cls.company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
		cls.cc = frappe.get_cached_value("Company", cls.company, "cost_center")
		if not frappe.db.exists("UOM", "Litre"):
			frappe.get_doc({"doctype": "UOM", "uom_name": "Litre"}).insert()
		if not frappe.db.exists("Item Group", "All Item Groups"):
			frappe.get_doc({"doctype": "Item Group", "item_group_name": "All Item Groups", "is_group": 1}).insert()
		cls.diesel = frappe.get_doc({"doctype": "Item", "item_code": "AA Diesel", "item_name": "AA Diesel",
			"item_group": "All Item Groups", "stock_uom": "Litre", "is_stock_item": 1}).insert()
		# Through the app's own helper: it sets the Farm another installed app makes mandatory on Warehouse.
		cls.wh = new_warehouse("AA Fuel Store", cls.company,
			farm=frappe.db.get_value("Farm", {}, "name") if frappe.db.exists("DocType", "Farm") else None)
		receipt = frappe.get_doc({"doctype": "Stock Entry", "stock_entry_type": "Material Receipt",
			"purpose": "Material Receipt", "company": cls.company, "set_posting_time": 1,
			"posting_date": add_days(today(), -30), "items": [{"item_code": cls.diesel.name, "qty": 1000,
				"t_warehouse": cls.wh, "basic_rate": 160, "cost_center": cls.cc}]})
		receipt.insert()
		receipt.submit()
		frappe.db.set_single_value("Production Settings", {"fuel_warehouse": cls.wh, "feedlot_cost_center": cls.cc})
		cls.op = frappe.get_doc({"doctype": "Employee", "first_name": "AAOperator", "gender": "Male",
			"date_of_birth": "1990-01-01", "date_of_joining": "2020-01-01", "company": cls.company}).insert()
		cls.tractor = frappe.get_doc({"doctype": aa.MACHINE, "machine_name": "AA Tractor 1", "machine_type": "Tractor",
			"fuel_item": cls.diesel.name}).insert()

	def setUp(self):
		frappe.set_user("Administrator")
		for name in frappe.get_all(aa.ALLOCATION, filters={"machine": self.tractor.name, "docstatus": 0}, pluck="name"):
			frappe.delete_doc(aa.ALLOCATION, name, force=True)

	def _start(self, **kw):
		return aa.start_allocation({"code": qr.scan_url(self.tractor.qr_code), "operator": self.op.name,
			"latitude": 0.0612, "longitude": 36.7531, "accuracy": 6, **kw})

	def test_machine_gets_stable_token(self):
		token = self.tractor.qr_code
		self.assertTrue(token)
		self.tractor.reload()
		self.tractor.notes = "serviced"
		self.tractor.save()
		self.assertEqual(self.tractor.qr_code, token)
		self.assertEqual(aa.machine_by_code(token).name, self.tractor.name)
		self.assertEqual(aa.machine_by_code(qr.scan_url(token)).name, self.tractor.name)

	def test_start_by_scan_records_gps_and_feedlot_cost_center(self):
		doc = self._start()
		self.assertEqual((doc.status, doc.scanned, doc.allocated_to, doc.cost_center), ("Open", 1, "Feedlot", self.cc))
		self.assertAlmostEqual(flt(doc.start_latitude), 0.0612)
		machine = frappe.db.get_value(aa.MACHINE, self.tractor.name, ["last_latitude", "last_longitude", "last_seen_at"], as_dict=True)
		self.assertAlmostEqual(flt(machine.last_longitude), 36.7531)
		self.assertTrue(machine.last_seen_at)

	def test_one_open_allocation_per_machine(self):
		self._start()
		self.assertRaises(frappe.ValidationError, self._start)
		manual = frappe.get_doc({"doctype": aa.ALLOCATION, "machine": self.tractor.name, "allocated_to": "Other",
			"operator": self.op.name, "cost_center": self.cc, "start_time": now_datetime()})
		self.assertRaises(frappe.ValidationError, manual.insert)

	def test_bad_gps_refused(self):
		self.assertRaises(frappe.ValidationError, geo.check_fix, 91, 36)
		self.assertRaises(frappe.ValidationError, geo.check_fix, 0, 0)
		self.assertRaises(frappe.ValidationError, geo.check_fix, 0.06, None)
		self.assertIsNone(geo.check_fix(None, ""))

	def test_close_computes_duration_and_submit_issues_diesel(self):
		start = now_datetime() - timedelta(hours=3)
		self._start(scanned_at=str(start))
		doc = aa.close_allocation(None, {"code": self.tractor.qr_code, "latitude": 0.0601, "longitude": 36.7502,
			"diesel_litres": 25, "submit": 1})
		self.assertEqual(doc.docstatus, 1)
		self.assertEqual(doc.status, "Posted")
		self.assertAlmostEqual(flt(doc.duration_hours), 3.0, places=1)
		se = frappe.get_doc("Stock Entry", doc.diesel_stock_entry)
		self.assertEqual((se.docstatus, se.purpose), (1, "Material Issue"))
		self.assertEqual((se.production_asset_allocation, se.production_machine), (doc.name, self.tractor.name))
		row = se.items[0]
		self.assertEqual((row.item_code, flt(row.qty), row.s_warehouse, row.cost_center), (self.diesel.name, 25.0, self.wh, self.cc))
		self.assertAlmostEqual(flt(doc.diesel_cost), flt(se.total_outgoing_value))
		self.assertAlmostEqual(flt(doc.diesel_cost), 25 * 160, places=0)

		costs = aa.allocation_costs(add_days(today(), -1), today(), cost_center=self.cc)
		self.assertTrue(costs["ok"])
		mine = [r for r in costs["rows"] if r["allocation"] == doc.name]
		self.assertEqual(len(mine), 1)
		self.assertEqual(set(mine[0]), {"allocation", "machine", "operator", "operator_name", "start_time", "end_time",
			"duration_hours", "diesel_litres", "diesel_cost", "cost_center", "reference_doctype", "reference_name"})
		self.assertEqual(set(costs["days"][0]), {"date", "diesel_litres", "diesel_cost", "machine_hours"})
		self.assertGreaterEqual(sum(d["diesel_cost"] for d in costs["days"]) + 0.01, flt(doc.diesel_cost))

		doc.cancel()
		self.assertEqual(frappe.db.get_value("Stock Entry", se.name, "docstatus"), 2)
		self.assertEqual(frappe.db.get_value(aa.ALLOCATION, doc.name, "status"), "Cancelled")
		after = aa.allocation_costs(add_days(today(), -1), today(), cost_center=self.cc)
		self.assertFalse([r for r in after["rows"] if r["allocation"] == doc.name])

	def test_no_litres_posts_no_stock_entry(self):
		self._start(scanned_at=str(now_datetime() - timedelta(hours=1)))
		doc = aa.close_allocation(None, {"code": self.tractor.qr_code, "submit": 1})
		self.assertEqual(doc.docstatus, 1)
		self.assertFalse(doc.diesel_stock_entry)
		self.assertEqual(flt(doc.diesel_cost), 0)

	def test_submit_needs_end_time(self):
		doc = self._start()
		self.assertRaises(frappe.ValidationError, doc.submit)

	def test_end_before_start_refused(self):
		doc = self._start()
		doc.end_time = get_datetime(doc.start_time) - timedelta(hours=1)
		self.assertRaises(frappe.ValidationError, doc.save)

	def test_reference_must_match_target(self):
		doc = frappe.get_doc({"doctype": aa.ALLOCATION, "machine": self.tractor.name, "allocated_to": "Silage Cycle",
			"reference_doctype": "Production Unit", "reference_name": "nothing", "operator": self.op.name,
			"cost_center": self.cc, "start_time": now_datetime()})
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_allocation_costs_is_read_guarded(self):
		user = "aa-nobody@example.com"
		if not frappe.db.exists("User", user):
			frappe.get_doc({"doctype": "User", "email": user, "first_name": "AA Nobody", "send_welcome_email": 0}).insert()
		frappe.set_user(user)
		try:
			out = api.allocation_costs(today(), today())
		finally:
			frappe.set_user("Administrator")
		self.assertIn("error", out)

	def test_allocation_costs_api_shape(self):
		out = api.allocation_costs(today(), today())
		self.assertTrue(out["ok"])
		self.assertEqual(len(out["days"]), 1)
		self.assertEqual(out["days"][0]["date"], getdate(today()).isoformat())

	def test_labels_and_scan_endpoints(self):
		label = api.machine_qr(self.tractor.name)
		self.assertEqual(label["qr_code"], self.tractor.qr_code)
		self.assertIn("machine=" + self.tractor.qr_code, label["url"])
		self.assertTrue((label["image"] or "").startswith("data:image/"))
		scan = api.scan_machine(label["url"])
		self.assertEqual(scan["machine"]["name"], self.tractor.name)
		self.assertIsNone(scan["open_allocation"])
		started = api.start_allocation({"code": label["url"], "operator": self.op.name})
		self.assertEqual(started["allocation"]["status"], "Open")
		self.assertEqual(api.scan_machine(label["url"])["open_allocation"]["name"], started["allocation"]["name"])
