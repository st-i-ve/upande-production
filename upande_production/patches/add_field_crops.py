import frappe

from upande_production.production.logic import field_crops


def execute():
	"""Field Crops (Cabbage, Maize, Onion ...) for the sections that grow several products, and the links on
	their varieties, protocols, cycles and harvest records. Matches by item name and variety, never by item code;
	safe on a site with no such section and safe to run twice."""
	for dt in ("Production Crop Group", "Production Sub Crop", "Production Field Crop", "Production Variety", "Production Protocol", "Production Crop Cycle", "Production Harvest",
			"Harvest Batch", "Yield Sample", "Crop Forecast", "Buyer Commitment", "Harvest Grading Log"):
		frappe.reload_doc("production", "doctype", frappe.scrub(dt))
	made = field_crops.create_from_varieties()
	counts = field_crops.link_records()
	for fc in frappe.get_all("Production Field Crop", pluck="name"):
		field_crops.align_items(fc)
	frappe.logger().info(f"add_field_crops: created {made}, linked {counts}")
	print(f"add_field_crops: created {made}, linked {counts}")
