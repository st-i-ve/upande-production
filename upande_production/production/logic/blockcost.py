"""What is happening on a block, in money: links check, ERP budget and the cost breakdown.

Everything done on a block is charged to its cost centre. SCP's chemical plan issues stock against the
cost centre whose name equals the *block warehouse* name, so the block's warehouse and cost centre must
carry the same name (`links` checks it). Labour is the casual Value Adders' recorded pay only; payroll never
enters here. ERPNext v16 keeps one account and one amount on a Budget (no Budget Account table), with a
fiscal year range, so a block's ERP budget is the sum of its submitted Budgets overlapping the fiscal year.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from upande_production.production.logic import analytics
from upande_production.production.logic.analytics import _pay, merge_uoms


# -- links check -------------------------------------------------------------


def links(crop: str) -> list[dict]:
	"""[{unit, cost_center, warehouse, ok, problems}] for every leaf block of the crop."""
	rows = frappe.get_all("Production Unit", filters={"crop": crop, "is_group": 0},
		fields=["name", "cost_center", "warehouse"], order_by="lft asc")
	out = []
	for r in rows:
		problems = []
		if not r.cost_center:
			problems.append(_("No cost centre"))
		if not r.warehouse:
			problems.append(_("No warehouse"))
		if r.cost_center and r.warehouse and r.cost_center != r.warehouse:
			problems.append(_("Warehouse '{0}' and cost centre '{1}' differ — chemicals issued to this block are charged elsewhere")
				.format(r.warehouse, r.cost_center))
		out.append({"unit": r.name, "cost_center": r.cost_center, "warehouse": r.warehouse,
			"ok": not problems, "problems": problems})
	return out


# -- ERP budget --------------------------------------------------------------


def fiscal_year_range(company: str | None = None, fiscal_year: str | None = None):
	"""(name, start, end) of the given fiscal year, else the one holding today. None when there is none."""
	if fiscal_year:
		row = frappe.db.get_value("Fiscal Year", fiscal_year, ["name", "year_start_date", "year_end_date"])
	else:
		row = frappe.db.sql("""select name, year_start_date, year_end_date from `tabFiscal Year`
			where disabled = 0 and %s between year_start_date and year_end_date
			order by year_start_date desc limit 1""", (today(),))
		row = row[0] if row else None
	return (row[0], getdate(row[1]), getdate(row[2])) if row else None


def erp_budget(cost_center: str | None, fiscal_year: str | None = None) -> float:
	"""Sum of the submitted ERPNext Budgets (budget_against Cost Center) on `cost_center` whose period
	overlaps the fiscal year (default: the current one). 0 when there is none."""
	if not cost_center:
		return 0.0
	fy = fiscal_year_range(None, fiscal_year)
	if not fy:
		return 0.0
	row = frappe.db.sql("""select sum(budget_amount) from `tabBudget` where docstatus = 1
		and budget_against = 'Cost Center' and cost_center = %s
		and budget_start_date <= %s and budget_end_date >= %s""", (cost_center, fy[2], fy[1]))
	return flt(row[0][0]) if row and row[0][0] else 0.0


# -- breakdown ---------------------------------------------------------------


def _scope(unit: str):
	"""(units, cost centres, area_ha): the block, or a group and every unit below it."""
	row = frappe.db.get_value("Production Unit", unit, ["name", "lft", "rgt", "is_group", "area_ha", "cost_center"], as_dict=True)
	if not row:
		frappe.throw(_("Block {0} not found").format(unit), frappe.ValidationError)
	if row.is_group and row.lft:
		subs = frappe.get_all("Production Unit", filters={"lft": (">=", row.lft), "rgt": ("<=", row.rgt)},
			fields=["name", "cost_center", "area_ha", "is_group"])
	else:
		subs = [frappe._dict(name=row.name, cost_center=row.cost_center, area_ha=row.area_ha, is_group=0)]
	area = flt(row.area_ha) or sum(flt(s.area_ha) for s in subs if not s.is_group)
	return [s.name for s in subs], [s.cost_center for s in subs if s.cost_center], area


def _labour(units, frm, to, can_see_pay):
	rows = frappe.db.sql("""select w.operation, o.operation_name, w.uom, sum(w.qty), count(distinct w.employee), sum(w.pay_value)
		from `tabValue Adder Work` w left join `tabProduction Operation` o on o.name = w.operation
		where w.docstatus = 1 and w.unit in %(u)s and w.work_date between %(f)s and %(t)s
		group by w.operation, o.operation_name, w.uom""", {"u": tuple(units), "f": frm, "t": to})
	ops: dict = {}
	for op, label, uom, qty, _n, pay in rows:
		ops.setdefault(op, {"operation": op, "operation_name": label or op, "parts": [], "pay": 0.0})
		ops[op]["parts"].append((uom, qty))
		ops[op]["pay"] += flt(pay)
	workers = {r[0]: r[1] for r in frappe.db.sql("""select operation, count(distinct employee) from `tabValue Adder Work`
		where docstatus = 1 and unit in %(u)s and work_date between %(f)s and %(t)s group by operation""",
		{"u": tuple(units), "f": frm, "t": to})}
	out = [{"operation": o["operation"], "operation_name": o["operation_name"], "qty_by_uom": merge_uoms(o["parts"]),
		"workers": workers.get(o["operation"], 0), "pay": _pay(round(o["pay"], 2), can_see_pay)} for o in ops.values()]
	return sorted(out, key=lambda r: -(r["pay"] or 0)) if can_see_pay else sorted(out, key=lambda r: r["operation_name"])


def _inputs(ccs, frm, to, area):
	if not ccs:
		return []
	rows = frappe.db.sql("""select d.item_code, i.item_name, i.item_group, d.stock_uom, sum(d.transfer_qty), sum(d.amount)
		from `tabStock Entry Detail` d join `tabStock Entry` se on se.name = d.parent
		left join `tabItem` i on i.name = d.item_code
		where se.docstatus = 1 and se.stock_entry_type != 'Harvesting' and d.cost_center in %(c)s
		and ifnull(d.s_warehouse, '') != '' and ifnull(d.t_warehouse, '') = ''
		and se.posting_date between %(f)s and %(t)s
		group by d.item_code, i.item_name, i.item_group, d.stock_uom order by sum(d.amount) desc""",
		{"c": tuple(ccs), "f": frm, "t": to})
	return [{"item_code": code, "item_name": name or code, "item_group": grp, "qty": round(flt(qty), 3), "uom": uom,
		"amount": round(flt(amt), 2), "per_ha": round(flt(qty) / area, 3) if area else None,
		"planned_qty": None} for code, name, grp, uom, qty, amt in rows]


def _other(ccs, frm, to):
	from upande_production.production.logic import breakeven  # breakeven imports establishment, which imports this
	if not ccs:
		return []
	capital = breakeven._capital_accounts()
	extra, args = "", {"c": tuple(ccs), "f": frm, "t": to}
	if capital:
		extra = "and gle.account not in %(cap)s"
		args["cap"] = tuple(capital)
	rows = frappe.db.sql(f"""select gle.account, sum(gle.debit - gle.credit)
		from `tabGL Entry` gle join `tabAccount` a on a.name = gle.account
		where gle.is_cancelled = 0 and a.root_type = 'Expense' and gle.cost_center in %(c)s
		and gle.voucher_type != 'Stock Entry' and gle.posting_date between %(f)s and %(t)s {extra}
		group by gle.account order by sum(gle.debit - gle.credit) desc""", args)
	return [{"account": acc, "amount": round(flt(amt), 2)} for acc, amt in rows if flt(amt)]


def breakdown(unit: str, from_date, to_date, can_see_pay: bool) -> dict:
	frm, to = analytics._range(from_date, to_date)
	units, ccs, area = _scope(unit)
	labour = _labour(units, frm, to, can_see_pay)
	inputs = _inputs(ccs, frm, to, area)
	other = _other(ccs, frm, to)
	lab_total = round(sum(r["pay"] or 0 for r in labour), 2) if can_see_pay else None
	inp_total = round(sum(r["amount"] for r in inputs), 2)
	oth_total = round(sum(r["amount"] for r in other), 2)
	total = round((lab_total or 0) + inp_total + oth_total, 2)
	fy = fiscal_year_range()
	actual = 0.0
	if fy:
		from upande_production.production.logic import breakeven
		for cc in ccs:
			actual += sum(v for d, v in breakeven._gl_events(cc, set()) if fy[1] <= getdate(d) <= fy[2])
	return {"unit": unit, "area_ha": area, "labour": labour, "inputs": inputs, "other": other,
		"totals": {"labour": lab_total, "inputs": inp_total, "other": oth_total,
			"total": _pay(total, can_see_pay), "per_ha": _pay(round(total / area, 2) if area else 0, can_see_pay)},
		"budget": {"erp_budget": round(sum(erp_budget(cc) for cc in ccs), 2), "actual_this_fy": round(actual, 2)}}
