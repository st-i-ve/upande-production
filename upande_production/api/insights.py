"""Extra read-only series for the Costs page sparklines (envelope pattern as api/production.py)."""

import frappe

from upande_production.api.envelope import run
from upande_production.api.production import _can_see_pay, _need
from upande_production.production.logic import analytics
from upande_production.production.logic.weeks import iso_of


@frappe.whitelist(methods=["POST"])
@run
def cost_trend(crop, from_date=None, to_date=None):
	"""Weekly labour, inputs, harvest value and quantity for the crop over the range (oldest first).

	Labour is None for a viewer without pay access.
	"""
	_need("Production Unit")
	frm, to = analytics._range(from_date, to_date)
	frm = analytics._monday(frm)
	units = analytics.crop_units(crop)
	names = [u.name for u in units if not u.is_group]
	ccs = [u.cost_center for u in units if u.cost_center and not u.is_group]
	weeks = {}

	def put(ws, key, v):
		ws = analytics.getdate(ws)
		w = weeks.setdefault(ws, {"labour": 0.0, "inputs": 0.0, "revenue": 0.0, "harvest_qty": 0.0})
		w[key] += float(v or 0)

	if names:
		for ws, v in frappe.db.sql(
			"""select date_sub(work_date, interval weekday(work_date) day), sum(pay_value)
			from `tabValue Adder Work` where docstatus=1 and unit in %(u)s
			and work_date between %(f)s and %(t)s group by 1""",
			{"u": tuple(names), "f": frm, "t": to},
		):
			put(ws, "labour", v)
		for ws, q, v in frappe.db.sql(
			"""select date_sub(harvest_date, interval weekday(harvest_date) day), sum(qty), sum(value)
			from `tabProduction Harvest` where unit in %(u)s
			and harvest_date between %(f)s and %(t)s group by 1""",
			{"u": tuple(names), "f": frm, "t": to},
		):
			put(ws, "harvest_qty", q)
			put(ws, "revenue", v)
	if ccs:
		for ws, v in frappe.db.sql(
			"""select date_sub(gle.posting_date, interval weekday(gle.posting_date) day), sum(gle.debit - gle.credit)
			from `tabGL Entry` gle join `tabAccount` a on a.name = gle.account
			where gle.is_cancelled = 0 and a.root_type = 'Expense' and gle.cost_center in %(c)s
			and gle.posting_date between %(f)s and %(t)s group by 1""",
			{"c": tuple(ccs), "f": frm, "t": to},
		):
			put(ws, "inputs", v)

	can_pay = _can_see_pay()
	out = []
	for ws in sorted(weeks):
		w = weeks[ws]
		iso_y, iso_w = iso_of(ws)
		out.append({
			"week_start": str(ws), "iso_year": iso_y, "iso_week": iso_w,
			"labour": round(w["labour"], 2) if can_pay else None,
			"inputs": round(w["inputs"], 2), "revenue": round(w["revenue"], 2),
			"harvest_qty": w["harvest_qty"],
		})
	return {"weeks": out}
