"""Tests for upande_production.api.crop_production -- mark_cycle_harvestable, list_active_cycles,
submit_production_plan."""

from __future__ import annotations

import datetime
import unittest

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_production.tests import default_company, default_employee, default_uom, make_warehouse

from upande_production.api import crop_production as api


class TestApi(FrappeTestCase):
    # ------------------------------------------------------------------
    # Shared fixtures (re-use helpers from test_controllers where possible)
    # ------------------------------------------------------------------

    def _make_warehouse(self, name="TEST GH 1", supervisor="Administrator"):
        return make_warehouse(name, supervisor)

    def _make_item(self, name="TEST-VARIETY-A"):
        if not frappe.db.exists("Item", name):
            frappe.get_doc({
                "doctype": "Item",
                "item_code": name,
                "item_name": name,
                "item_group": "All Item Groups",
                "stock_uom": default_uom(),
            }).insert(ignore_permissions=True, ignore_mandatory=True)
        return name

    def _make_protocol(self, name="TEST-PROTO-1"):
        """Idempotent: refresh values on re-run so a stale row can't skew a test."""
        values = {
            "variety_item": self._make_item(),
            "weeks_to_first_bending": 5,
            "weeks_to_second_bending": 5,
            "weeks_between_cuts": 7,
            "stems_per_plant_first_harvest": 0.7,
            "stems_per_cut": 1.5,
            "max_stems_per_plant_per_cut": 1.61,
            "productive_life_weeks": 260,
        }
        if frappe.db.exists("Crop Protocol", name):
            doc = frappe.get_doc("Crop Protocol", name)
            doc.update(values)
            doc.save(ignore_permissions=True)
            return doc.name
        return frappe.get_doc({
            "doctype": "Crop Protocol", "protocol_name": name, **values,
        }).insert(ignore_permissions=True).name

    def _make_cycle(self, gh=None, proto=None, variety=None):
        """Ensure the greenhouse has one Active cycle; return that child row."""
        gh = gh or self._make_warehouse()
        proto = proto or self._make_protocol()
        variety = variety or self._make_item()

        existing = frappe.db.get_value(
            "Crop Cycle", {"greenhouse": gh, "variety": variety, "status": "Active"}, "name"
        )
        if existing:
            return frappe.get_doc("Crop Cycle", existing)
        return frappe.get_doc({
            "doctype": "Crop Cycle",
            "greenhouse": gh, "variety": variety, "crop_protocol": proto,
            "planting_date": datetime.date(2026, 1, 5),
            "status": "Active", "qty_planted": 10000,
        }).insert(ignore_permissions=True)

    # ------------------------------------------------------------------
    # 2. mark_cycle_harvestable
    # ------------------------------------------------------------------

    def test_mark_cycle_harvestable_creates_item(self):
        """Creates an Item for the variety if it does not exist, returns its name."""
        cycle = self._make_cycle()
        result = api.mark_cycle_harvestable(cycle.name)
        self.assertTrue(result.get("item"),
                        "result must contain a non-empty 'item' key")
        self.assertTrue(
            frappe.db.exists("Item", result["item"]),
            f"Item {result['item']} should exist in the database",
        )

    # ------------------------------------------------------------------
    # 4. list_active_cycles
    # ------------------------------------------------------------------

    def test_list_active_cycles_filters_by_status(self):
        """All returned rows must have cycle_status == 'Active'."""
        # Ensure at least one active cycle exists
        self._make_cycle()
        rows = api.list_active_cycles()
        self.assertIsInstance(rows, list)
        for r in rows:
            self.assertEqual(
                r["status"], "Active",
                f"Unexpected status {r['status']} in row {r['name']}",
            )

    def test_list_active_cycles_filters_by_greenhouse(self):
        """Greenhouse filter narrows the result set."""
        gh = self._make_warehouse()
        self._make_cycle(gh=gh)
        rows = api.list_active_cycles(greenhouse=gh)
        self.assertIsInstance(rows, list)
        for r in rows:
            self.assertEqual(r["greenhouse"], gh)

    # ------------------------------------------------------------------
    # 5. submit_production_plan
    # ------------------------------------------------------------------

    def test_submit_production_plan_inserts_doc(self):
        """Inserts a Production Plan Form and returns its name plus todo count."""
        gh = self._make_warehouse()
        payload = {
            "company": default_company(),
            "greenhouse": gh,
            "plan_year": 2026,
            "plan_week": 28,
            "plan_period": "2026-W28",
            "tasks": [
                {
                    "task_name": "API test task",
                    "due_date": datetime.date(2026, 7, 6),
                    "assigned_to": default_employee(),
                    "status": "Open",
                }
            ],
        }
        result = api.submit_production_plan(payload)
        self.assertIn("production_plan_form", result)
        self.assertIn("todos_created", result)
        self.assertTrue(
            frappe.db.exists("Production Plan Form", result["production_plan_form"]),
            "Production Plan Form doc must exist after insert",
        )
        self.assertIsInstance(result["todos_created"], int)
