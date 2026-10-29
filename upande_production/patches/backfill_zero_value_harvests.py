import frappe
from frappe.utils import flt


def execute():
	"""Value every Production Harvest booked at zero: qty x the item's valuation rate, else buyer price,
	else the crop's Price per Kg (Production Harvest.validate does this for new rows)."""
	from upande_production.production.logic.harvest import valuation_rate

	for h in frappe.get_all("Production Harvest", filters={"value": 0, "docstatus": ("<", 2)},
			fields=["name", "item", "crop", "qty", "price_per_uom"]):
		rate = flt(h.price_per_uom) or valuation_rate(h.item, h.crop)
		if rate > 0:
			frappe.db.set_value("Production Harvest", h.name, {"price_per_uom": rate, "value": flt(h.qty) * rate},
				update_modified=False)
