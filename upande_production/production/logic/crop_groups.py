"""The standard crop groups and the group each known crop belongs to. Used by the crop logic and the migration patches."""

import frappe

# (group, parent): the groups every site gets. Crops are made per site from what the farm grows.
STANDARD_GROUPS = [
	("Floriculture", None),
	("Summer Flowers", "Floriculture"),
	("Fruit Crops", None),
	("Vegetable Crops", None),
	("Plantation Crops", None),
	("Fodder Crops", None),
]

# crop name (lower case) -> group, for the crops this app has met
CROP_GROUPS = {
	"avocado": "Fruit Crops",
	"passion fruit": "Fruit Crops",
	"onion": "Vegetable Crops",
	"potato": "Vegetable Crops",
	"cabbage": "Vegetable Crops",
	"maize": "Fodder Crops",
	"coffee": "Plantation Crops",
}


def group_of(crop_name):
	return CROP_GROUPS.get((crop_name or "").strip().lower())


def ensure_groups() -> int:
	"""Make the standard groups that do not exist yet; returns how many were made."""
	made = 0
	for name, parent in STANDARD_GROUPS:
		if not frappe.db.exists("Production Crop Group", name):
			frappe.get_doc({"doctype": "Production Crop Group", "group_name": name, "parent_production_crop_group": parent,
				"is_group": 1}).insert(ignore_permissions=True)
			made += 1
	return made


def tree() -> list:
	"""[{name, parent, sort_order}] for every crop group, in tree order."""
	return [{"name": g.name, "parent": g.parent_production_crop_group, "sort_order": g.sort_order or 0}
		for g in frappe.get_all("Production Crop Group", fields=["name", "parent_production_crop_group", "sort_order"],
			order_by="sort_order asc, name asc", limit_page_length=0)]
