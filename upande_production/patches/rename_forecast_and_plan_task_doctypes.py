import frappe

RENAMES = (
	("Production Forecast", "Crop Forecast"),
	("Production Forecast Week", "Crop Forecast Week"),
	("Production Plan Task", "Work Plan Task"),
)


def execute():
	"""Rename the doctypes in place before the JSON sync, keeping every record and link.

	The names clashed with upande_agriculture's doctypes, which are ported into this app."""
	for old, new in RENAMES:
		if frappe.db.exists("DocType", old) and not frappe.db.exists("DocType", new):
			frappe.rename_doc("DocType", old, new, force=True, show_alert=False)
	frappe.db.commit()
