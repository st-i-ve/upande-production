"""Desk API for Field Crops (Cabbage, Maize ... inside a farm section). Same envelope as api.production."""

import frappe
from frappe import _

from upande_production.api.envelope import as_dict, run
from upande_production.api.production import _need, _save
from upande_production.production.logic import field_crops

FIELDS = ["name", "crop_name", "crop_group", "product", "harvest_uom", "color", "enabled"]


@frappe.whitelist(methods=["POST"])
@run
def list_field_crops(crop):
	"""{field_crops: [{name, crop_name, crop_group, product, product_name, harvest_uom, color, enabled, varieties}]}"""
	_need("Production Field Crop")
	rows = field_crops.list_for(crop)
	counts = dict(frappe.db.sql("select field_crop, count(*) from `tabProduction Variety` where crop = %s and ifnull(field_crop, '') != '' group by field_crop", (crop,)))
	for r in rows:
		r["varieties"] = int(counts.get(r["name"], 0))
		r["product_name"] = frappe.db.get_value("Item", r["product"], "item_name") if r["product"] else None
	return {"field_crops": rows}


@frappe.whitelist(methods=["POST"])
@run
def save_field_crop(data):
	"""Insert, or update when data.name is set. The name of a crop in use is fixed."""
	data = dict(as_dict(data) or {})
	data = {k: v for k, v in data.items() if k in FIELDS}
	if data.get("name"):
		data.pop("crop_name", None)
	return {"name": _save("Production Field Crop", data).name}
