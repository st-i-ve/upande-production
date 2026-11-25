"""Desk API for Field Crops (Cabbage, Maize ... inside a farm section). Same envelope as api.production."""

import frappe
from frappe import _

from upande_production.api.envelope import as_dict, run
from upande_production.api.production import _need, _save
from upande_production.production.logic import crop_groups, field_crops
from upande_production.production.logic.settings import is_manager

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


def _managers_only():
	if not is_manager():
		frappe.throw(_("Only a Production Manager can change crops."), frappe.PermissionError)


@frappe.whitelist(methods=["POST"])
@run
def get_crop_tree():
	"""{groups: [{name, parent, sort_order}], crops: [list_for rows]}"""
	_need("Production Field Crop")
	return {"groups": crop_groups.tree(), "crops": field_crops.list_for(None)}


@frappe.whitelist(methods=["POST"])
@run
def save_crop_group(data):
	"""Insert, or update when data.name is set. Keys: name, group_name, parent, sort_order. Managers only."""
	_managers_only()
	data = dict(as_dict(data) or {})
	keys = {"parent": "parent_production_crop_group", "sort_order": "sort_order"}
	row = {col: (data.get(k) or (None if k == "parent" else 0)) for k, col in keys.items() if k in data}
	if data.get("name"):  # an update changes only the keys that were sent
		doc = frappe.get_doc("Production Crop Group", data["name"])
		doc.update(row)
		doc.save()
	else:
		doc = frappe.get_doc({"doctype": "Production Crop Group", "is_group": 1, "group_name": data.get("group_name"), **row}).insert()
	return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
@run
def save_field_crop(data):
	"""Insert, or update when data.name is set. The name of a crop in use is fixed. Managers only."""
	_managers_only()
	data = dict(as_dict(data) or {})
	data = {k: v for k, v in data.items() if k in FIELDS}
	if data.get("name"):
		data.pop("crop_name", None)
	return {"name": _save("Production Field Crop", data).name}


SUB_FIELDS = ["name", "sub_crop_name", "field_crop", "product", "harvest_uom", "enabled"]


@frappe.whitelist(methods=["POST"])
@run
def save_sub_crop(data):
	"""Insert, or update when data.name is set. Managers only."""
	_managers_only()
	data = dict(as_dict(data) or {})
	data = {k: v for k, v in data.items() if k in SUB_FIELDS}
	if data.get("name"):
		data.pop("sub_crop_name", None)
	return {"name": _save("Production Sub Crop", data).name}
