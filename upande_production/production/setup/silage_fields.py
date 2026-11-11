"""Declarative owner of the silage module's custom fields on shared doctypes.

Stock Entry is ERPNext's and shared with every other installed app, so the field is stated here and
rebuilt on every ``after_migrate`` (the pattern upande_scp's ``store.stock_entry_fields`` uses) rather than
shipped as a fixture: a fixture only restores what some site last exported, while a declaration makes a
fresh install, a reset and a new site converge.

* ``Stock Entry.production_silage_cycle`` - the Silage Cycle an input issue (Material Issue) is charged to,
  and the cycle whose closing posted a pit receipt (Material Receipt).
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

MODULE = "Production"


def field_spec() -> dict:
	return {
		"Stock Entry": [
			{
				"fieldname": "production_silage_cycle",
				"label": "Silage Cycle",
				"fieldtype": "Link",
				"options": "Silage Cycle",
				"insert_after": "stock_entry_type",
				"no_copy": 1,
				"in_standard_filter": 1,
				"search_index": 1,
				"module": MODULE,
				"description": "Inputs issued to a silage cycle count in its cost; the cycle's pit receipt carries it too.",
			},
		],
	}


def ensure_silage_fields():
	"""after_migrate: create or update the fields (needs the Silage Cycle doctype, which migrate has synced)."""
	if not frappe.db.exists("DocType", "Silage Cycle"):
		return
	create_custom_fields(field_spec(), ignore_validate=True, update=True)
