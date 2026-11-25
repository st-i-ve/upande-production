import frappe


def execute():
	"""Field Crop became Production Field Crop (it was never deployed to a live site, so this only moves the
	records of a bench that already migrated it). Runs before the JSON sync, which then finds the renamed
	doctype instead of making a second, empty one. A no-op where Field Crop does not exist."""
	if (frappe.db.get_value("DocType", "Field Crop", "module") == "Production"
			and not frappe.db.exists("DocType", "Production Field Crop")):
		frappe.rename_doc("DocType", "Field Crop", "Production Field Crop", force=True, show_alert=False)
	frappe.db.commit()
