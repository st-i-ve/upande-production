"""Capital costs move from the protocol to the block.

Copies each Active protocol's capital rows (the old Production Protocol Capital Activity table, which a
model sync leaves in place) to the blocks as Per ha budget rows, then stamps the running cycle on the
existing establishment cost split rows. Idempotent; nothing is deleted.
"""

import frappe
from frappe.utils import flt

OLD = "Production Protocol Capital Activity"
RUNNING = ["Active", "Harvesting"]  # the same meaning as establishment.cycle_on, as of today


def _units_for(protocol, units=None):
	crop = protocol.crop
	filters = {"crop": crop, "is_group": 0, "status": ("!=", "Retired")}
	if units is not None:
		filters["name"] = ("in", list(units) or [""])
	names = frappe.get_all("Production Unit", filters=filters, pluck="name")
	scope = {}
	if protocol.get("variety"):
		scope["variety"] = protocol.variety
	elif protocol.get("field_crop"):
		scope["field_crop"] = protocol.field_crop
	if not scope or not names:
		return names
	running = set(frappe.get_all("Production Crop Cycle", filters={
		"unit": ("in", names), "status": ("in", RUNNING), **scope}, pluck="unit"))
	running |= set(frappe.get_all("Production Crop Cycle", filters={
		"unit": ("in", names), "status": ("in", RUNNING), "protocol": protocol.name}, pluck="unit"))
	return [n for n in names if n in running]


def _log_unreached():
	"""Draft and Pending Approval protocols still hold capital rows: not copied, so say which."""
	for p in frappe.get_all("Production Protocol", filters={"version_status": ("in", ["Draft", "Pending Approval"])},
			fields=["name", "crop", "version_status"]):
		n = frappe.db.count(OLD, {"parent": p.name, "parenttype": "Production Protocol"})
		if n:
			msg = f"{p.name} ({p.crop}, {p.version_status}) still has {n} capital rows; they are kept in the old table but not copied to blocks"
			print(f"capital_costs_to_blocks: {msg}")
			frappe.log_error(msg, "capital_costs_to_blocks")


def copy_protocol_capital(protocols=None, units=None) -> int:
	"""Per ha budget rows written on blocks; returns how many."""
	if not frappe.db.table_exists(OLD):
		return 0
	made = 0
	filters = {"version_status": "Active"}
	if protocols is not None:
		filters["name"] = ("in", list(protocols) or [""])
	found = frappe.get_all("Production Protocol", filters=filters, fields=["name", "crop", "variety", "field_crop", "modified"])
	# variety-specific protocols first, then crop-wide ones; newest first within each. The first to budget an
	# operation on a block keeps it.
	found = [p for _k, grp in ((k, [x for x in found if (0 if x.variety else 1) == k]) for k in (0, 1))
		for p in sorted(grp, key=lambda x: str(x.modified), reverse=True)]
	if protocols is None:
		_log_unreached()
	for p in found:
		rows = frappe.db.get_all(OLD, filters={"parent": p.name, "parenttype": "Production Protocol"},
			fields=["operation", "budget_per_ha", "description"], order_by="idx asc")
		if not rows:
			continue
		added = 0
		for unit in _units_for(frappe._dict(p), units):
			have = set(frappe.get_all("Production Unit Capital Budget", filters={"parent": unit, "parenttype": "Production Unit"},
				pluck="operation"))
			idx = len(have)
			for r in rows:
				if r.operation in have:
					continue
				idx += 1
				frappe.get_doc({"doctype": "Production Unit Capital Budget", "parent": unit, "parenttype": "Production Unit",
					"parentfield": "capital_budget", "idx": idx, "operation": r.operation, "basis": "Per ha",
					"amount": flt(r.budget_per_ha), "note": r.description}).insert(ignore_permissions=True)
				have.add(r.operation)
				added += 1
		made += added
		print(f"capital_costs_to_blocks: {p.name} ({p.crop}): {added} budget rows written")
	return made


def fill_split_cycles(parents=None) -> int:
	"""Stamp `cycle` on split rows that have none; returns how many were set."""
	from upande_production.production.logic.establishment import cycle_on

	filters = {"cycle": ("is", "not set")}
	if parents is not None:
		filters["parent"] = ("in", list(parents) or [""])
	rows = frappe.get_all("Block Establishment Cost Split", filters=filters, fields=["name", "parent", "unit"])
	dates = {}
	n = 0
	for r in rows:
		if r.parent not in dates:
			dates[r.parent] = frappe.db.get_value("Block Establishment Cost", r.parent, "posting_date")
		cy = cycle_on(r.unit, dates[r.parent]) if r.unit and dates[r.parent] else None
		if cy:
			frappe.db.set_value("Block Establishment Cost Split", r.name, "cycle", cy, update_modified=False)
			n += 1
	return n


def execute():
	frappe.reload_doc("production", "doctype", "production_unit_capital_budget")
	budgets = copy_protocol_capital()
	cycles = fill_split_cycles()
	print(f"capital_costs_to_blocks: {budgets} budget rows, {cycles} cost rows given a cycle")
