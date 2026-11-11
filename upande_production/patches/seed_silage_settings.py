"""Silage settings: seed the labour day rate with the farm's current figure (the feedlot sheet's 400 a
day) where it is still empty. Idempotent; a rate a manager has set is never touched."""

import frappe

DAY_RATE = 400


def execute():
	frappe.reload_doc("production", "doctype", "production_settings")
	if not frappe.db.get_single_value("Production Settings", "silage_labour_day_rate"):
		frappe.db.set_single_value("Production Settings", "silage_labour_day_rate", DAY_RATE)
