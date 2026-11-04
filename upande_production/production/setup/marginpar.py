"""Margin Par's Production crops (roses and summer flowers). Inert unless run; safe to re-run.

bench --site marginpar.local execute upande_production.production.setup.marginpar.setup_marginpar

Follows the model the F&V demo uses (see production/demo/varieties_seed.py: Potatoes -> Shangi):
Production Crop -> Production Variety.product (an Item) -> Production Variety (the varieties themselves are real data, not
created here). Flowers are sold by
the stem, so the yield UOM is Nos, the units are Greenhouse -> Bed, and nothing is packed in crates.
Their launcher tiles open the Crop Production desk pages (desk_launcher), not the Production app.
"""

import frappe

DESK = "Crop Production desk"
UOM = "Nos"
PARENT = "Farm"

CROPS = [
	# No demo varieties: Margin Par's real varieties come with its data (the summer flowers carry 61 of them,
	# their items named by the real codes), and a re-run must never recreate a stand-in such as "Orion".
	{"name": "Standard Roses", "key": "standard-roses", "accent": "#b8335a", "icon": "rose", "sort": 1,
	 "product": "Rose", "unit": "Greenhouse"},
	{"name": "Spray Roses", "key": "spray-roses", "accent": "#d46a8c", "icon": "spray-rose", "sort": 2,
	 "product": "Rose", "unit": "Greenhouse"},
	# The summer flowers are planted per block of beds, not per greenhouse.
	{"name": "Summer Flowers", "key": "summer-flowers", "accent": "#3b6fb6", "icon": "eryngium", "sort": 3,
	 "product": None, "unit": "Block"},
]


def _item_group():
	for g in ("Products", "All Item Groups"):
		if frappe.db.exists("Item Group", g):
			return g
	return frappe.db.get_value("Item Group", {"is_group": 0}) or "All Item Groups"


def _ensure_item(code):
	if frappe.db.exists("Item", code):
		return code
	frappe.get_doc({
		"doctype": "Item", "item_code": code, "item_name": code, "item_group": _item_group(),
		"stock_uom": UOM, "is_stock_item": 1, "include_item_in_manufacturing": 0,
	}).insert(ignore_permissions=True)
	return code


def _ensure_uom():
	if not frappe.db.exists("UOM", UOM):
		frappe.get_doc({"doctype": "UOM", "uom_name": UOM}).insert(ignore_permissions=True)


def _ensure_crop(c):
	vals = {
		"crop_key": c["key"], "accent_color": c["accent"], "icon_key": c["icon"],
		"parent_unit_label": PARENT, "unit_label": c["unit"], "sub_unit_label": "Bed",
		"yield_uom": UOM, "uses_crop_cycles": 1, "default_cycle_type": "Planting",
		"enabled": 1, "sort_order": c["sort"], "harvests_in_crates": 0, "desk_launcher": DESK,
	}
	name = frappe.db.get_value("Production Crop", {"crop_key": c["key"]}) or frappe.db.get_value(
		"Production Crop", {"crop_name": c["name"]})
	if name:
		doc = frappe.get_doc("Production Crop", name)
		doc.update(vals)
		doc.save(ignore_permissions=True)
		return doc.name
	doc = frappe.get_doc({"doctype": "Production Crop", "crop_name": c["name"], **vals})
	doc.insert(ignore_permissions=True)
	return doc.name


def setup_marginpar():
	_ensure_uom()
	for c in CROPS:
		if c["product"]:
			_ensure_item(c["product"])
		_ensure_crop(c)
	frappe.db.commit()
	return [c["name"] for c in CROPS]
