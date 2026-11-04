import frappe

OLD, NEW = "Field " + "Activity", "Field Operation"


def execute():
	"""Rename Production's Field Activity to Field Operation in place (table, links, records kept).

	Guarded: only a "Field Activity" whose module is "Production" is renamed. One owned by another
	module (upande_summer_flowers: "Summer Flowers") is never touched. A no-op on a fresh site, when
	there is no such doctype, or when Field Operation already exists.
	"""
	if not frappe.db.exists("DocType", OLD) or frappe.db.exists("DocType", NEW):
		return
	if frappe.db.get_value("DocType", OLD, "module") != "Production":
		return
	frappe.rename_doc("DocType", OLD, NEW, force=True, show_alert=False)
	frappe.db.commit()
