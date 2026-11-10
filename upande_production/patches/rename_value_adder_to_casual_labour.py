import frappe

OLD, NEW = "Value Adder Work", "Casual Labour Work"


def execute():
	"""Rename the Value Adder Work doctype to Casual Labour Work in place (table, rows, links kept),
	and the "Value Adder" Employee Designation (the crew picker's filter) to "Casual Labourer".

	Guarded: a no-op on a fresh site, when the old doctype is absent, or when the new one exists.
	There are no value_adder-named fields to rename; the rename covers every Link to the doctype."""
	if frappe.db.exists("DocType", OLD) and not frappe.db.exists("DocType", NEW):
		if frappe.db.get_value("DocType", OLD, "module") == "Production":
			frappe.rename_doc("DocType", OLD, NEW, force=True, show_alert=False)
	if frappe.db.exists("DocType", "Designation") and frappe.db.exists("Designation", "Value Adder") \
			and not frappe.db.exists("Designation", "Casual Labourer"):
		frappe.rename_doc("Designation", "Value Adder", "Casual Labourer", force=True, show_alert=False)
	frappe.db.commit()
