# The avocado model moved from constants in the API modules onto Production Crop and
# Production Variety. Give an existing avocado crop and its varieties today's values
# where they are still empty, so a site's forecast does not change on update. After
# this a manager owns the figures (Settings, Crop model).

import frappe

from upande_production.production import avocado_defaults


def execute():
	frappe.reload_doc("production", "doctype", "production_crop_count_size")
	frappe.reload_doc("production", "doctype", "production_variety_yield_age")
	frappe.reload_doc("production", "doctype", "production_crop")
	frappe.reload_doc("production", "doctype", "production_variety")
	crop = frappe.db.get_value("Production Crop", {"crop_key": "avocado"})
	if not crop:
		return
	avocado_defaults.apply_to_crop(crop)
	for v in frappe.get_all("Production Variety", filters={"crop": crop}, pluck="name"):
		avocado_defaults.apply_to_variety(v)
