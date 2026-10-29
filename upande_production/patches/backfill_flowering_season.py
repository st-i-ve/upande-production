import frappe


def execute():
	"""Open cycles of Seasonal varieties without a flowering season take the season nearest (on or before)
	their flowering date; saving re-derives expected flowering / harvest from the season."""
	frappe.reload_doctype("Production Crop Cycle")
	for name in frappe.get_all("Production Crop Cycle", filters={"flowering_season": ("in", ["", None]),
			"variety": ("is", "set"), "status": ("not in", ["Closed", "Cancelled"])}, pluck="name"):
		doc = frappe.get_doc("Production Crop Cycle", name)
		doc.flags.ignore_permissions = True
		doc.save()
