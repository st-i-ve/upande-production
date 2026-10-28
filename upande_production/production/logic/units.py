import frappe

from upande_production.production.logic.settings import get_company


def _as_doc(unit):
	return frappe.get_doc("Production Unit", unit) if isinstance(unit, str) else unit


def _make_group(cc_name: str):
	if not frappe.db.get_value("Cost Center", cc_name, "is_group"):
		frappe.db.set_value("Cost Center", cc_name, "is_group", 1)


def _new_cc(name: str, parent: str, company: str, is_group: int) -> str:
	existing = frappe.db.get_value("Cost Center", {"cost_center_name": name, "company": company})
	if existing:
		return existing
	cc = frappe.get_doc({
		"doctype": "Cost Center", "cost_center_name": name, "parent_cost_center": parent,
		"company": company, "is_group": is_group,
	})
	cc.insert(ignore_permissions=True)
	return cc.name


def ensure_unit_cost_center(unit) -> str:
	unit = _as_doc(unit)
	if unit.get("cost_center") and frappe.db.exists("Cost Center", unit.cost_center):
		return unit.cost_center
	company = unit.company or get_company()
	root = frappe.db.get_value("Cost Center", {"company": company, "is_group": 1, "parent_cost_center": ("is", "not set")})
	parent = None
	if unit.parent_production_unit:
		parent = ensure_unit_cost_center(unit.parent_production_unit)
		_make_group(parent)
	else:
		base = frappe.db.get_single_value("Production Settings", "cost_center_parent") or root
		crop_name = frappe.db.get_value("Production Crop", unit.crop, "crop_name") or unit.crop
		abbr = frappe.db.get_value("Company", company, "abbr")
		crop_cc = frappe.db.get_value("Cost Center", f"{crop_name} - {abbr}")
		if not crop_cc:
			_make_group(base)
			crop_cc = _new_cc(crop_name, base, company, 1)
		parent = crop_cc
	name = _new_cc(unit.unit_name, parent, company, 1 if unit.is_group else 0)
	unit.cost_center = name
	if unit.get("name") and frappe.db.exists("Production Unit", unit.name):
		unit.db_set("cost_center", name, update_modified=False)
	return name


def subtree(unit_name: str) -> list[str]:
	lft, rgt = frappe.db.get_value("Production Unit", unit_name, ["lft", "rgt"]) or (None, None)
	if lft is None:
		return [unit_name]
	return frappe.get_all(
		"Production Unit", filters={"lft": (">=", lft), "rgt": ("<=", rgt)}, pluck="name", order_by="lft"
	)
