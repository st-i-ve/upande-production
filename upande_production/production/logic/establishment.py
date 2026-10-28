"""Capital / setup costs per block: splitting a cost over leaf blocks, and totals per block.

A Block Establishment Cost names blocks or groups. `split` expands groups to their leaf blocks and
fills each row's share and amount, so everything downstream (break-even, the desk table) reads leaves only.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate

from upande_production.production.logic import analytics


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
	filters = {"is_group": 0, "lft": (">", row.lft), "rgt": ("<", row.rgt)}
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


# -- budgets -----------------------------------------------------------------


def capital_activities(crop):
	"""[{operation, color, budget_per_ha}]: capital rows of the crop's Active protocols, else every
	Capital-type operation of the crop."""
	rows, seen = [], set()
	protocols = frappe.get_all("Production Protocol", filters={"crop": crop, "version_status": "Active"}, pluck="name")
	for p in protocols:
		for r in frappe.get_all("Production Protocol Capital Activity", filters={"parent": p},
				fields=["operation", "budget_per_ha"], order_by="idx"):
			if r.operation not in seen:
				seen.add(r.operation)
				rows.append({"operation": r.operation, "budget_per_ha": flt(r.budget_per_ha)})
	if not rows:
		for op in frappe.get_all("Production Operation", filters={"crop": crop, "activity_type": "Capital"}, pluck="name"):
			rows.append({"operation": op, "budget_per_ha": None})
	colors = dict(frappe.get_all("Production Operation", filters={"name": ("in", [r["operation"] for r in rows] or [""])},
		fields=["name", "color"], as_list=True))
	return [{"operation": r["operation"], "color": colors.get(r["operation"]) or None,
		"budget_per_ha": r["budget_per_ha"]} for r in rows]


def list_costs(crop, farm=None):
	filters = {"crop": crop, "docstatus": 1}
	if farm:
		filters["farm"] = farm
	docs = frappe.get_all("Block Establishment Cost", filters=filters,
		fields=["name", "posting_date", "operation", "amount", "supplier", "paid_to", "reference"],
		order_by="posting_date desc, creation desc")
	blocks = {}
	if docs:
		for b in frappe.get_all("Block Establishment Cost Split", filters={"parent": ("in", [d.name for d in docs])},
				fields=["parent", "unit", "share_pct", "amount"], order_by="idx"):
			blocks.setdefault(b.parent, []).append({"unit": b.unit, "share_pct": b.share_pct, "amount": b.amount})
	rows = [{**d, "blocks": blocks.get(d.name, [])} for d in docs]

	units = [u for u in analytics.crop_units(crop) if not u.is_group]
	if farm:
		ok = set(frappe.get_all("Production Unit", filters={"crop": crop, "farm": farm}, pluck="name"))
		units = [u for u in units if u.name in ok]
	budgets = {r["operation"]: flt(r["budget_per_ha"]) for r in capital_activities(crop)}
	spent = {}
	for unit, _d, op, amount in cost_rows([u.name for u in units]):
		spent.setdefault(unit, {})[op] = spent.get(unit, {}).get(op, 0) + float(amount or 0)
	by_unit = []
	for u in units:
		area = flt(u.area_ha)
		acts = {op: {"operation": op, "amount": round(a, 2), "budget": None} for op, a in spent.get(u.name, {}).items()}
		for op, per_ha in budgets.items():
			if per_ha and area:
				acts.setdefault(op, {"operation": op, "amount": 0, "budget": None})["budget"] = round(per_ha * area, 2)
		if not acts:
			continue
		by_unit.append({"unit": u.name, "area_ha": area,
			"total": round(sum(a["amount"] for a in acts.values()), 2), "by_activity": list(acts.values())})
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
	rows = frappe.get_all("Block Opening Balance", filters={"crop": crop},
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
