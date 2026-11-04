import frappe

OLD, NEW = "Production " + "Operation", "Field Operation"


def execute():
	"""Rename the doctype in place before the JSON sync, keeping every record and link.

	It goes straight to its final name, Field Operation, never through "Field Activity": that name
	belongs to upande_summer_flowers on some sites and must not be touched or collided with. A no-op
	unless Production Operation exists (and Field Operation does not).
	"""
	if frappe.db.exists("DocType", OLD) and not frappe.db.exists("DocType", NEW):
		frappe.rename_doc("DocType", OLD, NEW, force=True, show_alert=False)
		frappe.db.commit()
