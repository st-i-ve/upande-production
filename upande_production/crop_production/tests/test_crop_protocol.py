# Copyright (c) 2026, Upande and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_production.tests import default_uom


class TestCropProtocol(FrappeTestCase):
    def _item(self, name="TEST-GRADEMIX-VARIETY"):
        if not frappe.db.exists("Item", name):
            frappe.get_doc({
                "doctype": "Item", "item_code": name, "item_name": name,
                "item_group": "All Item Groups", "stock_uom": default_uom(),
            }).insert(ignore_permissions=True, ignore_mandatory=True)
        return name

    def _protocol(self, name, grade_mix):
        if frappe.db.exists("Crop Protocol", name):
            frappe.delete_doc("Crop Protocol", name, force=True, ignore_permissions=True)
        doc = {
            "doctype": "Crop Protocol", "protocol_name": name,
            "variety_item": self._item(), "grade_mix": grade_mix,
        }
        # Margin Par's live schema makes Crop Type mandatory on a protocol
        if frappe.get_meta("Crop Protocol").get_field("crop_type") and frappe.get_meta("Crop Protocol").get_field("crop_type").reqd:
            if not frappe.db.exists("Crop Type", "Roses"):
                frappe.get_doc({"doctype": "Crop Type", "crop_type_name": "Roses"}).insert(ignore_permissions=True)
            doc["crop_type"] = "Roses"
        return frappe.get_doc(doc)

    def test_grade_mix_over_100_percent_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            self._protocol("TEST-GRADEMIX-OVER", [
                {"length_cm": 60, "pct": 70}, {"length_cm": 50, "pct": 40},
            ]).insert(ignore_permissions=True)

    def test_grade_mix_at_100_percent_is_allowed(self):
        doc = self._protocol("TEST-GRADEMIX-EXACT", [
            {"length_cm": 60, "pct": 63.8}, {"length_cm": 50, "pct": 36.2},
        ]).insert(ignore_permissions=True)
        # the doc is named by the site's naming rule (protocol name here, variety-farm on Margin Par's live schema)
        self.assertTrue(doc.name)
        self.assertEqual(len(doc.grade_mix), 2)
