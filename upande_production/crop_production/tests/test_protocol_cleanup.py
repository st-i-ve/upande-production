"""summer_flowers.cleanup.refresh_protocols and the protocol title fallback."""

from unittest import mock

import frappe
from frappe.tests import IntegrationTestCase

from upande_production.summer_flowers import cleanup
from upande_production.summer_flowers import crop_protocol as cp

DOCTYPE = "Crop Protocol"


class TestRefreshProtocols(IntegrationTestCase):
	def setUp(self):
		# approve() and the cleanup commit; a test must not.
		patcher = mock.patch.object(frappe.db, "commit")
		patcher.start()
		self.addCleanup(patcher.stop)

	def _sample(self, status=None):
		"""A summer flower protocol that can be recomputed, optionally in a given status."""
		filters = {"custom_is_summer_flower": 1}
		if status:
			filters["custom_sf_protocol_status"] = status
		for name in frappe.get_all(DOCTYPE, filters=filters, pluck="name", order_by="name asc"):
			if not cp.recompute_diff(name)["error"] and not cleanup._missing_links(name):
				return name
		self.skipTest("no recomputable summer flower protocol" + (f" in status {status}" if status else ""))

	def _stale(self, name):
		"""Make the stored derived values drift, as an older version of the code would have."""
		frappe.db.set_value(DOCTYPE, name, "custom_sf_cuttings_per_plant_required", 99.5, update_modified=False)

	def test_dry_run_writes_nothing(self):
		name = self._sample()
		self._stale(name)
		before = frappe.db.get_value(DOCTYPE, name, ["custom_sf_cuttings_per_plant_required", "modified"], as_dict=True)
		report = cleanup.refresh_protocols(apply=False, names=[name])
		self.assertFalse(report["apply"])
		row = report["protocols"][0]
		self.assertEqual(row["action"], "would refresh")
		self.assertIn("custom_sf_cuttings_per_plant_required", [c["fieldname"] for c in row["changes"]])
		self.assertEqual(before, frappe.db.get_value(
			DOCTYPE, name, ["custom_sf_cuttings_per_plant_required", "modified"], as_dict=True))

	def test_apply_recomputes_and_keeps_the_status(self):
		for status in ("Approved", "Draft"):
			name = self._sample(status)
			self._stale(name)
			report = cleanup.refresh_protocols(apply=True, names=[name])
			self.assertEqual(report["refreshed"], [name], report)
			self.assertEqual(frappe.db.get_value(DOCTYPE, name, "custom_sf_protocol_status"), status)
			self.assertNotEqual(frappe.db.get_value(
				DOCTYPE, name, "custom_sf_cuttings_per_plant_required"), 99.5)
			self.assertEqual(cp.recompute_diff(name)["changes"], [])

	def test_approved_protocol_gets_a_snapshot_noted_as_a_data_refresh(self):
		name = self._sample("Approved")
		self._stale(name)
		reason = frappe.db.get_value(DOCTYPE, name, "custom_sf_change_reason")
		seen = {}

		def fake_approve(protocol):
			seen["reason"] = frappe.db.get_value(DOCTYPE, protocol, "custom_sf_change_reason")
			return {"version": "V-TEST"}

		with mock.patch.object(cp, "diff_against_current", return_value=["stems_per_cut"]), \
				mock.patch.object(cp, "approve", side_effect=fake_approve):
			report = cleanup.refresh_protocols(apply=True, names=[name])
		self.assertEqual(seen["reason"], cleanup.REFRESH_NOTE)
		self.assertEqual(report["protocols"][0]["action"], "refreshed + snapshot")
		self.assertEqual(report["protocols"][0]["version"], "V-TEST")
		# the protocol's own reason is put back, and it is still Approved
		self.assertEqual(frappe.db.get_value(DOCTYPE, name, "custom_sf_change_reason"), reason)
		self.assertEqual(frappe.db.get_value(DOCTYPE, name, "custom_sf_protocol_status"), "Approved")

	def test_no_snapshot_when_the_approved_inputs_did_not_move(self):
		name = self._sample("Approved")
		self._stale(name)
		with mock.patch.object(cp, "approve") as approve:
			cleanup.refresh_protocols(apply=True, names=[name])
		approve.assert_not_called()

	def test_a_missing_link_target_is_reported_not_fatal(self):
		name = self._sample()
		self._stale(name)
		frappe.db.set_value(DOCTYPE, name, "custom_sf_approved_by", "nobody.here@example.invalid",
		                    update_modified=False)
		report = cleanup.refresh_protocols(apply=True, names=[name])
		self.assertEqual([s["name"] for s in report["skipped"]], [name])
		self.assertIn("nobody.here@example.invalid", report["skipped"][0]["reason"])
		self.assertEqual(frappe.db.get_value(DOCTYPE, name, "custom_sf_cuttings_per_plant_required"), 99.5)

	def test_a_failing_snapshot_skips_that_protocol_and_rolls_it_back(self):
		name = self._sample("Approved")
		self._stale(name)
		with mock.patch.object(cp, "diff_against_current", return_value=["stems_per_cut"]), \
				mock.patch.object(cp, "approve", side_effect=frappe.ValidationError("no grade allocation")):
			report = cleanup.refresh_protocols(apply=True, names=[name])
		self.assertEqual([s["name"] for s in report["skipped"]], [name])
		self.assertIn("no grade allocation", report["skipped"][0]["reason"])
		self.assertEqual(frappe.db.get_value(DOCTYPE, name, "custom_sf_cuttings_per_plant_required"), 99.5)
		self.assertEqual(frappe.db.get_value(DOCTYPE, name, "custom_sf_protocol_status"), "Approved")


class TestProtocolTitle(IntegrationTestCase):
	def test_an_empty_title_falls_back_to_the_protocol_name(self):
		doc = frappe.new_doc(DOCTYPE)
		doc.protocol_name = "TEST-TITLE-FALLBACK"
		doc.crop_type = cp.SUMMER_FLOWER
		cp.before_validate(doc)
		self.assertEqual(doc.custom_sf_title, "TEST-TITLE-FALLBACK")

	def test_the_derived_title_still_wins(self):
		doc = frappe.new_doc(DOCTYPE)
		doc.protocol_name = "TEST-TITLE-DERIVED"
		doc.crop_type = cp.SUMMER_FLOWER
		doc.custom_sf_title = "Hand set"
		cp.before_validate(doc)
		self.assertEqual(doc.custom_sf_title, "Hand set")

	def test_a_fresh_approval_does_not_differ_from_its_own_snapshot(self):
		"""None vs '' vs 0 and unsaved-row markers are not edits."""
		name = next(iter(frappe.get_all(
			DOCTYPE, filters={"custom_sf_protocol_status": "Approved", "custom_is_summer_flower": 1},
			pluck="name", limit=1)), None)
		if not name:
			self.skipTest("no approved protocol")
		doc = frappe.get_doc(DOCTYPE, name)
		a = cp._comparable(doc, True)
		for table in ("material_route", "way_stages", "flush_schedule"):
			self.assertFalse(any(k.startswith("_") for row in a[table] for k in map(str, row)))
