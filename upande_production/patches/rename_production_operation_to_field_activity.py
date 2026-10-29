import frappe

OLD, NEW = "Production " + "Operation", "Field Activity"


def execute():
	"""Rename the doctype in place before the JSON sync, keeping every record and link."""
	if frappe.db.exists("DocType", OLD) and not frappe.db.exists("DocType", NEW):
		frappe.rename_doc("DocType", OLD, NEW, force=True, show_alert=False)
		frappe.db.commit()
