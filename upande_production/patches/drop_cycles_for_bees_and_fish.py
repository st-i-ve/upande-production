import frappe

from upande_production.production.logic.cycles import remove_cycles_for_cycleless_crops

NO_CYCLES = ("apiary", "aquaculture")


def execute():
	"""Bees and fish have no crop cycles: flag the crops, then remove their cycles."""
	frappe.reload_doc("production", "doctype", "production_section")
	for key in NO_CYCLES:
		name = frappe.db.get_value("Production Section", {"crop_key": key})
		if name:
			frappe.db.set_value("Production Section", name, "uses_crop_cycles", 0)
	remove_cycles_for_cycleless_crops()
