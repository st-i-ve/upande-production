"""Set `occurrences` on cultural rows converted from steps before the field existed."""

import frappe

from upande_production.patches.convert_protocol_steps import backfill_occurrences


def execute():
	frappe.reload_doctype("Production Protocol Cultural Activity")
	print(f"backfill_cultural_occurrences: {backfill_occurrences()} rows")
