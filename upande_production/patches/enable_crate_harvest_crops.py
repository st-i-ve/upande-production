import frappe

# crop_key -> default kg in a full crate
CRATE_CROPS = {"avocado": 18, "fruits-vegetables": 20}


def execute():
	"""Avocado and Fruits & Vegetables are picked into crates: flag them and give each a default crate weight."""
	frappe.reload_doc("production", "doctype", "production_section")
	for key, kg in CRATE_CROPS.items():
		name = frappe.db.get_value("Production Section", {"crop_key": key})
		if not name:
			continue
		frappe.db.set_value("Production Section", name, "harvests_in_crates", 1)
		if not frappe.db.get_value("Production Section", name, "avg_kg_per_crate"):
			frappe.db.set_value("Production Section", name, "avg_kg_per_crate", kg)
