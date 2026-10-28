import frappe
from frappe.utils import cint, flt


def execute():
	"""Weeks from the old day fields (rounded) and plants per m2 from plants per ha, where not yet set."""
	frappe.reload_doctype("Production Variety")
	for v in frappe.get_all("Production Variety", fields=["name", "days_to_first_harvest", "harvest_window_days",
			"plants_per_ha", "weeks_to_first_harvest", "harvest_window_weeks", "plants_per_m2"]):
		vals = {}
		if cint(v.days_to_first_harvest) and not cint(v.weeks_to_first_harvest):
			vals["weeks_to_first_harvest"] = round(cint(v.days_to_first_harvest) / 7)
		if cint(v.harvest_window_days) and not cint(v.harvest_window_weeks):
			vals["harvest_window_weeks"] = round(cint(v.harvest_window_days) / 7)
		if flt(v.plants_per_ha) and not flt(v.plants_per_m2):
			vals["plants_per_m2"] = round(flt(v.plants_per_ha) / 10000, 6)
		if vals:
			frappe.db.set_value("Production Variety", v.name, vals, update_modified=False)
