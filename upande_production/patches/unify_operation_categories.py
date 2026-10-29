import frappe

# old category -> category of the activity-rule vocabulary; Field Care / Husbandry / Planting depend on the name
SIMPLE = {"Spray": "Spraying", "Nutrition": "Fertilising", "Harvest": "Harvesting", "Irrigation": "Irrigation"}
BY_NAME = (("weed", "Weeding"), ("prun", "Pruning"), ("feed", "Feeding"), ("spray", "Spraying"),
	("fertili", "Fertilising"), ("top dress", "Fertilising"), ("harvest", "Harvesting"), ("irrigat", "Irrigation"))
NEW = {"Spraying", "Weeding", "Fertilising", "Irrigation", "Harvesting", "Pruning", "Feeding", "Other"}


def execute():
	frappe.reload_doc("production", "doctype", "field_activity")
	for op in frappe.get_all("Field Activity", fields=["name", "operation_name", "category"]):
		if op.category in NEW or not op.category:
			continue
		new = SIMPLE.get(op.category)
		if not new:
			low = (op.operation_name or "").lower()
			new = next((c for frag, c in BY_NAME if frag in low), "Other")
		frappe.db.set_value("Field Activity", op.name, "category", new, update_modified=False)
