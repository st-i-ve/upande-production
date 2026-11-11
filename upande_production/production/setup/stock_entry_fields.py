"""Stock Entry fields that link a diesel issue back to the machine allocation that burnt it.

Declared here and rebuilt on every ``after_migrate`` (the pattern upande_scp uses in
serverscripts/store/stock_entry_fields.py), not exported as fixtures: Stock Entry is shared by
several installed apps, and a fixture only restores whatever some site last exported. Declaring
the fields means a fresh install, a new site and a reset all converge.

Only the fields below are managed. The older production fields on Stock Entry
(``production_harvest_batch`` and the Stock Entry Detail ones) are still fixtures and are left
alone: nothing here deletes a field.
"""

import frappe

MODULE = "Production"


def field_spec() -> dict:
	return {
		"Stock Entry": [
			{
				"fieldname": "production_asset_allocation",
				"label": "Production Asset Allocation",
				"fieldtype": "Link",
				"options": "Production Asset Allocation",
				"insert_after": "remarks",
				"read_only": 1,
				"no_copy": 1,
				"search_index": 1,
				"module": MODULE,
			},
			{
				"fieldname": "production_machine",
				"label": "Production Machine",
				"fieldtype": "Link",
				"options": "Production Machine",
				"insert_after": "production_asset_allocation",
				"read_only": 1,
				"no_copy": 1,
				"in_standard_filter": 1,
				"module": MODULE,
			},
		],
	}


def ensure_stock_entry_fields():
	"""Create or update the fields above. Idempotent; a no-op before ERPNext's tables (or this
	app's doctypes) exist."""
	if not frappe.db.table_exists("Stock Entry") or not frappe.db.table_exists("Production Asset Allocation"):
		return
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(field_spec(), update=True)
	frappe.clear_cache(doctype="Stock Entry")


def after_migrate():
	try:
		ensure_stock_entry_fields()
	except Exception:
		frappe.log_error(title="upande_production: Stock Entry machine fields", message=frappe.get_traceback())
