"""Whitelisted field-execution endpoints (ported from upande_agriculture.api).

mark_cycle_harvestable, submit_production_plan and list_active_cycles live here. The old
`upande_agriculture.api.*` paths resolve to these through override_whitelisted_methods in hooks.
Budget, projection and week-summary endpoints belong to upande_crop_material_planning;
promote_trial_to_cycle belongs to upande_propagation.
"""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _


# ---------------------------------------------------------------------------
# 3. mark_cycle_harvestable
# ---------------------------------------------------------------------------

@frappe.whitelist()
def mark_cycle_harvestable(crop_cycle_name: str) -> dict:
    """Ensure an Item exists for the cycle's variety and return its name."""
    cycle = frappe.get_doc("Crop Cycle", crop_cycle_name)
    variety = cycle.get("variety")
    if not variety:
        frappe.throw(_("Crop Cycle has no variety set."))

    item_code = variety
    if not frappe.db.exists("Item", variety):
        item_group = (
            "Flower"
            if frappe.db.exists("Item Group", "Flower")
            else "All Item Groups"
        )
        item_doc = frappe.get_doc({
            "doctype": "Item",
            "item_code": variety,
            "item_name": variety,
            "item_group": item_group,
            "stock_uom": "Nos",
        }).insert(ignore_permissions=True, ignore_mandatory=True)
        item_code = item_doc.name

    return {"item": item_code}


# ---------------------------------------------------------------------------
# 5. submit_production_plan
# ---------------------------------------------------------------------------

@frappe.whitelist()
def submit_production_plan(payload: str | dict) -> dict:
    """Insert a Production Plan Form from a JSON payload.

    Note: Production Plan Form is NOT submittable (docstatus never set to 1).
    We use insert() only; the on_update hook creates ToDos automatically.
    """
    if isinstance(payload, str):
        payload = json.loads(payload)

    plan = frappe.get_doc({"doctype": "Production Plan Form", **payload})
    plan.insert(ignore_permissions=True, ignore_mandatory=True)

    todos = frappe.db.count(
        "ToDo",
        {
            "reference_type": "Production Plan Form",
            "reference_name": plan.name,
        },
    )
    return {"production_plan_form": plan.name, "todos_created": int(todos)}


# ---------------------------------------------------------------------------
# 6. list_active_cycles
# ---------------------------------------------------------------------------

@frappe.whitelist()
def list_active_cycles(greenhouse: str | None = None) -> list[dict]:
    """Return all Active Crop Cycles, optionally filtered by greenhouse.

    """
    filters: dict[str, Any] = {"status": "Active"}
    if greenhouse:
        filters["greenhouse"] = greenhouse

    rows = frappe.db.get_all(
        "Crop Cycle",
        filters=filters,
        fields=[
            "name",
            "greenhouse",
            "variety",
            "crop_protocol",
            "planting_date",
            "first_bending_date",
            "second_bending_date",
            "planned_uprooting_date",
            "qty_planted",
            "status",
        ],
        order_by="planting_date desc",
    )
    return rows
