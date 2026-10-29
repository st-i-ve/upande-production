import frappe
from frappe.utils import cint


def execute():
	"""Flowering varieties get a flowering pattern: Interval, with the flowering interval taken from the
	harvest interval, else weeks to reflower + weeks flowering to harvest (the old reflower field stays,
	hidden). Seasonal varieties are set up by hand (or by the demo seed)."""
	frappe.reload_doctype("Production Variety")
	for v in frappe.get_all("Production Variety", filters={"is_flowering": 1, "flowering_pattern": ("in", ["", None])},
			fields=["name", "harvest_pattern", "harvest_interval_weeks", "weeks_to_reflower_after_harvest",
				"weeks_flowering_to_harvest", "flowering_interval_weeks"]):
		vals = {"flowering_pattern": "Interval"}
		if (v.harvest_pattern or "Once") != "Once" and not cint(v.flowering_interval_weeks):
			vals["flowering_interval_weeks"] = cint(v.harvest_interval_weeks) or (
				cint(v.weeks_to_reflower_after_harvest) + cint(v.weeks_flowering_to_harvest))
		frappe.db.set_value("Production Variety", v.name, vals, update_modified=False)
