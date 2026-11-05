"""Bed Work Order against the live Crop Cycle schema (no company, no number_of_beds, one uproot_log table).

Runs on a real block cycle inside a savepoint that is rolled back, so no live record is left changed.
"""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import cint


class TestBedWorkOrder(IntegrationTestCase):
	def setUp(self):
		self.cycle = None
		for c in frappe.get_all("Crop Cycle", filters={"custom_block": ["is", "set"],
		                        "custom_live_plant_count": [">", 1000]},
		                        fields=["name", "custom_block"], order_by="name asc"):
			beds = frappe.get_all("Bed", filters={"custom_block": c.custom_block},
			                      fields=["name", "bed", "custom_bed_status"], order_by="bed asc", limit=4)
			if len(beds) >= 2:
				self.cycle, self.beds = c.name, beds
				break
		if not self.cycle:
			self.skipTest("no block cycle with beds on this site")
		frappe.db.savepoint("bwo_test")

	def tearDown(self):
		frappe.db.rollback(save_point="bwo_test")

	def _plants(self):
		return cint(frappe.db.get_value("Crop Cycle", self.cycle, "custom_live_plant_count"))

	def _statuses(self):
		return {b.name: frappe.db.get_value("Bed", b.name, "custom_bed_status") for b in self.beds}

	def _order(self, work_type="Uprooting"):
		lo, hi = self.beds[0].bed, self.beds[1].bed
		doc = frappe.get_doc({
			"doctype": "Bed Work Order", "work_type": work_type, "crop_cycle": self.cycle,
			"from_bed": lo, "to_bed": hi, "plants_per_bed": 100, "reason": "Other",
		})
		doc.flags.ignore_permissions = True
		return doc.insert()

	def test_insert_pulls_context_without_company_or_bed_count(self):
		doc = self._order()
		self.assertEqual(doc.crop_cycle, self.cycle)
		self.assertTrue(doc.block)
		self.assertEqual(doc.status, "Not Started")

	def test_complete_uprooting_logs_and_moves_plants(self):
		before = self._plants()
		doc = self._order()
		doc.log_progress(beds_done=doc.total_beds)
		doc.reload()
		self.assertEqual(doc.status, "Completed")
		self.assertEqual(self._plants(), before - 200)
		self.assertTrue(cint(doc.logged_to_cycle))
		log = frappe.get_all("Crop Cycle Uproot", filters={"parent": self.cycle}, fields=["plants", "bed_range"])
		self.assertTrue(any(cint(r.plants) == 200 for r in log))
		after = self._statuses()
		self.assertEqual({after[self.beds[0].name], after[self.beds[1].name]}, {"Uprooted"})

	def test_cancel_restores_plants_and_beds_exactly_once(self):
		before, statuses = self._plants(), self._statuses()
		doc = self._order()
		doc.log_progress(beds_done=1)
		self.assertEqual(self._plants(), before - 100)
		doc.reload()
		doc.cancel_job("test")
		self.assertEqual(self._plants(), before)
		self.assertEqual(self._statuses(), statuses)
		doc.reload()
		self.assertEqual(doc.status, "Cancelled")
		self.assertEqual(cint(doc.plants_applied), 0)
		doc.save()  # a later save must not re-apply
		self.assertEqual(self._plants(), before)

	def test_cancel_after_completion_restores(self):
		before, statuses = self._plants(), self._statuses()
		doc = self._order("Replanting")
		doc.log_progress(beds_done=doc.total_beds)
		self.assertEqual(self._plants(), before + 200)
		doc.reload()
		doc.cancel_job("test")
		self.assertEqual(self._plants(), before)
		self.assertEqual(self._statuses(), statuses)
