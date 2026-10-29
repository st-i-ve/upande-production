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


# -- retired units -------------------------------------------------------------
# A retired unit (a demo block, a decommissioned pond) stays in the database with its history
# but never shows on a page, map, API or KPI. Every reader goes through these.

def retired_units() -> set[str]:
	"""Names of the units whose status is Retired."""
	return set(frappe.get_all("Production Unit", filters={"status": "Retired"}, pluck="name", limit_page_length=0))


def not_retired(names):
	"""`names` (units) without the retired ones, order kept."""
	gone = retired_units()
	return [n for n in names if n not in gone]


def retired_sql() -> tuple:
	"""A tuple for `unit not in %(retired)s` (never empty, which SQL would reject)."""
	return tuple(retired_units()) or ("",)


def unit_filter(filters: dict | None = None, field: str = "unit") -> dict:
	"""`filters` plus `field not in <retired units>` for a frappe.get_all on a unit-bearing doctype."""
	out = dict(filters or {})
	gone = retired_units()
	if gone:
		out[field] = ("not in", list(gone))
	return out


def close_open_work(unit: str) -> dict:
	"""A unit has been retired: its open cycles close (no next-cycle proposal) and its open plan tasks are
	skipped with a note. Straight DB writes, so no cycle hook proposes a successor. Idempotent."""
	cycles = frappe.get_all("Production Crop Cycle", filters={"unit": unit, "status": ("in", ("Planned", "Active", "Harvesting"))},
		pluck="name")
	for c in cycles:
		frappe.db.set_value("Production Crop Cycle", c, {"status": "Closed", "current_stage": None, "protocol_flags": "",
			"flag_count": 0}, update_modified=False)
	tasks = frappe.get_all("Production Plan Task", filters={"unit": unit, "status": ("in", ("Open", "In Progress"))},
		fields=["name", "note"])
	for t in tasks:
		note = f"{t.note}\n" if t.note else ""
		frappe.db.set_value("Production Plan Task", t.name, {"status": "Skipped", "note": f"{note}unit retired"},
			update_modified=False)
	return {"cycles": len(cycles), "tasks": len(tasks)}


def retire(unit: str) -> None:
	"""Mark a unit Retired and close its open work."""
	frappe.db.set_value("Production Unit", unit, "status", "Retired", update_modified=False)
	close_open_work(unit)
