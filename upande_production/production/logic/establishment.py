"""Capital / setup costs per block: splitting a cost over leaf blocks, and totals per block.

A Block Establishment Cost names blocks or groups. `split` expands groups to their leaf blocks and
fills each row's share and amount, so everything downstream (break-even, the desk table) reads leaves only.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate

from upande_production.production.logic import analytics, blockcost
from upande_production.production.logic.units import retired_units, unit_filter


def leaf_units(unit, crop=None):
	"""The unit itself when it is a block, else every non-group descendant (by lft/rgt). With a crop,
	only that crop's blocks."""
	row = frappe.db.get_value("Production Unit", unit, ["name", "is_group", "lft", "rgt", "crop"], as_dict=True)
	if not row:
		frappe.throw(_("Production Unit {0} not found").format(unit), frappe.ValidationError)
	if not row.is_group:
		if crop and row.crop != crop:
			frappe.throw(_("{0} is not a {1} block").format(unit, crop), frappe.ValidationError)
		return [row.name]
	filters = {"is_group": 0, "lft": (">", row.lft), "rgt": ("<", row.rgt), "status": ("!=", "Retired")}
	if crop:
		filters["crop"] = crop
	return frappe.get_all(
		"Production Unit",
		filters=filters,
		pluck="name",
		order_by="lft asc",
	)


def _area(unit):
	return flt(frappe.db.get_value("Production Unit", unit, "area_ha"))


def _no_area(unit):
	frappe.throw(_("Block {0} has no area; enter its area or split manually").format(unit), frappe.ValidationError)


def split(doc):
	"""Expand group rows to leaf rows and fill share_pct / area_ha / amount on every row."""
	chosen = [r for r in doc.blocks if r.unit]
	if not chosen:
		frappe.throw(_("Choose at least one block"), frappe.ValidationError)
	manual = doc.split_method == "Manual"
	# leaf -> share (Manual only). A group's share is spread over its leaves by area.
	shares, order = {}, []
	for r in chosen:
		leaves = leaf_units(r.unit, doc.crop)
		if not leaves:
			frappe.throw(_("{0} has no blocks under it").format(r.unit), frappe.ValidationError)
		if manual:
			areas = {u: _area(u) for u in leaves}
			explicit = {c.unit for c in chosen}
			for u in leaves:
				if len(leaves) > 1 and areas[u] <= 0 and u not in explicit:
					frappe.throw(_("Block {0} has no area; add it with its own share").format(u), frappe.ValidationError)
			total = sum(areas.values())
			if len(leaves) > 1 and total <= 0:
				_no_area(r.unit)
			for u in leaves:
				part = flt(r.share_pct) * (areas[u] / total if len(leaves) > 1 else 1)
				shares[u] = shares.get(u, 0) + part
		for u in leaves:
			if u not in order:
				order.append(u)
	areas = {u: _area(u) for u in order}
	if manual:
		if abs(sum(shares.values()) - 100) > 0.01:
			frappe.throw(_("Shares must total 100% (now {0}%)").format(round(sum(shares.values()), 2)), frappe.ValidationError)
		pct = {u: shares[u] for u in order}
	else:
		for u in order:
			if areas[u] <= 0:
				_no_area(u)
		total = sum(areas.values())
		pct = {u: areas[u] / total * 100 for u in order}

	amount = flt(doc.amount)
	amounts = {u: round(amount * pct[u] / 100, 2) for u in order}
	if order:
		biggest = max(order, key=lambda u: pct[u])
		amounts[biggest] = round(amounts[biggest] + (round(amount, 2) - sum(amounts.values())), 2)
	doc.set("blocks", [])
	for u in order:
		doc.append("blocks", {"unit": u, "area_ha": areas[u], "share_pct": round(pct[u], 4), "amount": amounts[u]})
	doc.total_area_ha = sum(areas.values())


def cost_rows(units=None, to_date=None, from_date=None):
	"""Submitted split rows: [(unit, posting_date, operation, amount)]."""
	cond, args = ["c.docstatus = 1"], {}
	if units is not None:
		if not units:
			return []
		cond.append("s.unit in %(u)s")
		args["u"] = tuple(units)
	if to_date:
		cond.append("c.posting_date <= %(to)s")
		args["to"] = to_date
	if from_date:
		cond.append("c.posting_date >= %(from)s")
		args["from"] = from_date
	return frappe.db.sql(
		f"""select s.unit, c.posting_date, c.operation, s.amount
		from `tabBlock Establishment Cost Split` s join `tabBlock Establishment Cost` c on c.name = s.parent
		where {' and '.join(cond)} order by c.posting_date""",
		args,
	)


def cost_by_unit(units, to_date=None):
	"""unit -> total establishment cost (submitted docs only; Uprooting-type rows included)."""
	out = {}
	for unit, _d, _op, amount in cost_rows(list(units), to_date):
		out[unit] = out.get(unit, 0) + float(amount or 0)
	return out


# -- cycles ------------------------------------------------------------------


def cycle_on(unit, date):
	"""The cycle running on `unit` on `date`: Active, Harvesting or Closed, started on or before the date
	and (open, or closed on or after it). The newest start wins; None when no cycle was running."""
	date = getdate(date)
	best = None
	for c in frappe.get_all("Production Crop Cycle", filters={"unit": unit, "status": ("in", ["Active", "Harvesting", "Closed"])},
			fields=["name", "status", "start_date", "closed_on", "actual_harvest_end"], order_by="start_date desc, creation desc"):
		if not c.start_date or getdate(c.start_date) > date:
			continue
		if c.status == "Closed":
			end = c.closed_on or c.actual_harvest_end
			if not end or getdate(end) < date:
				continue
		best = c
		break
	return best.name if best else None


def set_cycles(doc):
	"""Stamp each split row with the cycle running on its block at the cost's posting date."""
	for r in doc.blocks:
		r.cycle = cycle_on(r.unit, doc.posting_date) if r.unit and doc.posting_date else None


# -- budgets (on the block) --------------------------------------------------


def validate_budget(unit):
	"""Capital budget rows: only on a block, Capital operations of its crop, each operation once."""
	rows = unit.get("capital_budget") or []
	if not rows:
		return
	# a group or a retired block keeps the rows it already has; only new rows are checked (and refused on a group)
	fresh = [r for r in rows if r.get("__islocal") or not r.get("name")]
	if unit.is_group and fresh:
		frappe.throw(_("Capital is budgeted on a block, not on a group ({0}).").format(unit.name), frappe.ValidationError)
	if unit.is_group or unit.status == "Retired":
		rows = fresh
	seen = set()
	for i, r in enumerate(rows, 1):
		op = frappe.db.get_value("Field Operation", r.operation, ["activity_type", "crop"], as_dict=True)
		if not op or op.activity_type != "Capital":
			frappe.throw(_("Capital budget row {0}: {1} is not a Capital activity").format(i, r.operation), frappe.ValidationError)
		if op.crop and unit.crop and op.crop != unit.crop:
			frappe.throw(_("Capital budget row {0}: {1} belongs to another section").format(i, r.operation), frappe.ValidationError)
		if r.operation in seen:
			frappe.throw(_("Capital budget row {0}: {1} is already budgeted").format(i, r.operation), frappe.ValidationError)
		seen.add(r.operation)
		if flt(r.amount) < 0:
			frappe.throw(_("Capital budget row {0}: amount cannot be negative").format(i), frappe.ValidationError)
		if not r.basis:
			r.basis = "Per ha"


def effective(basis, amount, area):
	"""Per ha: amount x area, None when the block has no area. Total: the amount."""
	if basis == "Per ha":
		return round(flt(amount) * flt(area), 2) if flt(area) else None
	return round(flt(amount), 2)


def budget_rows(units):
	"""unit -> [{operation, basis, amount, note}] from the blocks' capital budgets."""
	out = {}
	if not units:
		return out
	for r in frappe.get_all("Production Unit Capital Budget", filters={"parent": ("in", list(units)), "parenttype": "Production Unit"},
			fields=["parent", "operation", "basis", "amount", "note"], order_by="parent asc, idx asc"):
		out.setdefault(r.parent, []).append({"operation": r.operation, "basis": r.basis, "amount": flt(r.amount), "note": r.note})
	return out


def unit_budget(unit):
	"""operation -> effective budget of one block (amount x area when Per ha)."""
	area = _area(unit)
	return {r["operation"]: effective(r["basis"], r["amount"], area) for r in budget_rows([unit]).get(unit, [])}  # None: Per ha without area


def capital_activities(crop):
	"""[{operation, color, budget_per_ha, blocks}]: the Capital operations budgeted on the crop's blocks
	(budget_per_ha is the common Per ha amount, None when blocks differ or budget a total), else every
	Capital-type operation of the crop."""
	units = frappe.get_all("Production Unit", filters={"crop": crop, "is_group": 0, "status": ("!=", "Retired")}, pluck="name")
	per_op = {}
	for rows in budget_rows(units).values():
		for r in rows:
			per_op.setdefault(r["operation"], []).append(r)
	rows = []
	for op, items in per_op.items():
		per_ha = {flt(i["amount"]) for i in items if i["basis"] == "Per ha"}
		common = per_ha.pop() if len(per_ha) == 1 and all(i["basis"] == "Per ha" for i in items) else None
		rows.append({"operation": op, "budget_per_ha": common, "blocks": len(items)})
	for op in frappe.get_all("Field Operation", filters={"crop": crop, "activity_type": "Capital"}, pluck="name"):
		if op not in per_op:
			rows.append({"operation": op, "budget_per_ha": None, "blocks": 0})
	colors = dict(frappe.get_all("Field Operation", filters={"name": ("in", [r["operation"] for r in rows] or [""])},
		fields=["name", "color"], as_list=True))
	return [{**r, "color": colors.get(r["operation"]) or None} for r in rows]


def get_unit_budget(unit):
	"""{unit, area_ha, rows: [{operation, operation_name, basis, amount, note, effective, spent}],
	total_budget, total_spent} for one block. `effective` is None for a Per ha row on a block without area."""
	if not frappe.db.exists("Production Unit", unit):
		frappe.throw(_("Production Unit {0} not found").format(unit), frappe.ValidationError)
	area = _area(unit)
	spent = {}
	for _u, _d, op, amount in cost_rows([unit]):
		spent[op] = spent.get(op, 0) + float(amount or 0)
	names = dict(frappe.get_all("Field Operation", fields=["name", "operation_name"], as_list=True))
	rows = []
	for r in budget_rows([unit]).get(unit, []):
		rows.append({**r, "operation_name": names.get(r["operation"], r["operation"]),
			"effective": effective(r["basis"], r["amount"], area), "spent": round(spent.get(r["operation"], 0), 2)})
	return {"unit": unit, "area_ha": area, "rows": rows,
		"total_budget": round(sum(r["effective"] or 0 for r in rows), 2), "total_spent": round(sum(spent.values()), 2)}


def save_unit_budget(unit, rows):
	"""Replace a block's capital budget with `rows` ([{operation, basis, amount, note}])."""
	doc = frappe.get_doc("Production Unit", unit)
	doc.set("capital_budget", [{"operation": r.get("operation"), "basis": r.get("basis") or "Per ha",
		"amount": flt(r.get("amount")), "note": r.get("note")} for r in rows or [] if r.get("operation")])
	doc.save(ignore_permissions=True)  # the caller has checked manager and crop; Avocado managers only read Production Unit
	return get_unit_budget(unit)


def cycle_cost_rows(units=None, cycle=None):
	"""Submitted split rows with their cycle: [(unit, cycle, cost, posting_date, operation, amount, supplier, reference)]."""
	cond, args = ["c.docstatus = 1"], {}
	if units is not None:
		if not units:
			return []
		cond.append("s.unit in %(u)s")
		args["u"] = tuple(units)
	if cycle:
		cond.append("s.cycle = %(cy)s")
		args["cy"] = cycle
	return frappe.db.sql(
		f"""select s.unit, s.cycle, c.name, c.posting_date, c.operation, s.amount, c.supplier, c.reference
		from `tabBlock Establishment Cost Split` s join `tabBlock Establishment Cost` c on c.name = s.parent
		where {' and '.join(cond)} order by c.posting_date, c.creation""",
		args,
	)


def cycle_capital_costs(cycle):
	"""{cycle, unit, rows: [{cost, posting_date, operation, amount, supplier, reference}], total,
	by_operation: [{operation, amount, budget}]}. `budget` is the block's effective budget for the
	operation (a block budget is not split between its cycles)."""
	unit = frappe.db.get_value("Production Crop Cycle", cycle, "unit")
	if not unit:
		frappe.throw(_("Cycle {0} not found").format(cycle), frappe.ValidationError)
	rows, by_op = [], {}
	for _u, _c, cost, d, op, amount, supplier, ref in cycle_cost_rows(cycle=cycle):
		rows.append({"cost": cost, "posting_date": d, "operation": op, "amount": round(float(amount or 0), 2),
			"supplier": supplier, "reference": ref})
		by_op[op] = by_op.get(op, 0) + float(amount or 0)
	budget = unit_budget(unit)
	return {"cycle": cycle, "unit": unit, "rows": rows, "total": round(sum(by_op.values()), 2),
		"by_operation": [{"operation": op, "amount": round(a, 2), "budget": budget.get(op)} for op, a in by_op.items()]}


def list_costs(crop, farm=None, can_see_pay=True):
	filters = {"crop": crop, "docstatus": 1}
	if farm:
		filters["farm"] = farm
	docs = frappe.get_all("Block Establishment Cost", filters=filters,
		fields=["name", "posting_date", "operation", "amount", "supplier", "paid_to", "reference"],
		order_by="posting_date desc, creation desc")
	blocks = {}
	if docs:
		for b in frappe.get_all("Block Establishment Cost Split", filters={"parent": ("in", [d.name for d in docs])},
				fields=["parent", "unit", "cycle", "share_pct", "amount"], order_by="idx"):
			blocks.setdefault(b.parent, []).append({"unit": b.unit, "cycle": b.cycle, "share_pct": b.share_pct, "amount": b.amount})
	gone = retired_units()
	rows = []
	for d in docs:
		live = [b for b in blocks.get(d.name, []) if b["unit"] not in gone]
		if blocks.get(d.name) and not live:
			continue  # a cost that only touched retired blocks
		rows.append({**d, "blocks": live})

	units = [u for u in analytics.crop_units(crop) if not u.is_group]
	if farm:
		ok = set(frappe.get_all("Production Unit", filters={"crop": crop, "farm": farm}, pluck="name"))
		units = [u for u in units if u.name in ok]
	budgets = budget_rows([u.name for u in units])
	spent, per_cycle = {}, {}
	for unit, cy, _c, _d, op, amount, _s, _r in cycle_cost_rows([u.name for u in units]):
		spent.setdefault(unit, {})[op] = spent.get(unit, {}).get(op, 0) + float(amount or 0)
		ops = per_cycle.setdefault(unit, {}).setdefault(cy or None, {})
		ops[op] = ops.get(op, 0) + float(amount or 0)
	cycles = {c.name: c for c in frappe.get_all("Production Crop Cycle", filters={"unit": ("in", [u.name for u in units] or [""])},
		fields=["name", "title", "start_date", "status", "closed_on"])}
	by_unit = []
	for u in units:
		area = flt(u.area_ha)
		acts = {op: {"operation": op, "amount": round(a, 2), "budget": None} for op, a in spent.get(u.name, {}).items()}
		for b in budgets.get(u.name, []):
			acts.setdefault(b["operation"], {"operation": b["operation"], "amount": 0, "budget": None})["budget"] = \
				effective(b["basis"], b["amount"], area)
		erp = blockcost.erp_budget(u.cost_center) or None
		if not acts and not erp:
			continue
		actual = analytics._pay(round(blockcost.actual_this_fy([u.name], [u.cost_center] if u.cost_center else []), 2),
			can_see_pay) if erp else None
		cyc = []
		for cy, ops in sorted(per_cycle.get(u.name, {}).items(), key=lambda kv: str(cycles[kv[0]].start_date) if kv[0] in cycles else ""):
			info = cycles.get(cy)
			cyc.append({"cycle": cy, "title": info.title if info else None, "start_date": info.start_date if info else None,
				"status": info.status if info else None, "total": round(sum(ops.values()), 2),
				"by_activity": [{"operation": op, "amount": round(a, 2)} for op, a in ops.items()]})
		by_unit.append({"unit": u.name, "area_ha": area, "erp_budget": erp, "actual_this_fy": actual,
			"total": round(sum(a["amount"] for a in acts.values()), 2), "by_activity": list(acts.values()), "cycles": cyc})
	return {"rows": rows, "by_unit": by_unit}


def save_cost(data):
	data = dict(data)
	blocks = data.pop("blocks", None) or []
	if not data.get("farm") and blocks:
		data["farm"] = frappe.db.get_value("Production Unit", blocks[0].get("unit"), "farm")
	doc = frappe.get_doc({"doctype": "Block Establishment Cost", **{k: v for k, v in data.items() if k in {
		"crop", "farm", "posting_date", "operation", "amount", "supplier", "paid_to", "reference", "note", "split_method"}},
		"blocks": [{"unit": b.get("unit"), "share_pct": b.get("share_pct")} for b in blocks]})
	doc.insert()
	doc.submit()
	return {"name": doc.name}


def list_opening_balances(crop):
	rows = frappe.get_all("Block Opening Balance", filters=unit_filter({"crop": crop}),
		fields=["unit", "as_of_date", "setup_cost", "running_costs_to_date", "value_recovered_to_date", "planted_on", "note"],
		order_by="unit asc")
	return {"rows": rows}


def save_opening_balance(data):
	data = dict(data)
	unit = data.get("unit")
	if not unit or not frappe.db.exists("Production Unit", unit):
		frappe.throw(_("Choose a block"), frappe.ValidationError)
	if not data.get("as_of_date"):
		frappe.throw(_("As of date is required"), frappe.ValidationError)
	fields = {k: data.get(k) for k in ("as_of_date", "setup_cost", "running_costs_to_date",
		"value_recovered_to_date", "planted_on", "note")}
	fields["crop"] = data.get("crop") or frappe.db.get_value("Production Unit", unit, "crop")
	if frappe.db.exists("Block Opening Balance", unit):
		doc = frappe.get_doc("Block Opening Balance", unit)
		doc.update(fields)
		doc.save()
	else:
		doc = frappe.get_doc({"doctype": "Block Opening Balance", "unit": unit, **fields})
		doc.insert()
	return {"name": doc.name}
