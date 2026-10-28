"""Break-even per block and per crop per farm: cumulative money in against money recovered.

Costs: opening balance (setup + running to date), establishment costs, approved labour pay, and GL
expense on the block's cost centre (excluding capital accounts, which establishment costs already
carry, and the stock entries harvesting posts). Value: opening value recovered and Production Harvest value.
With an opening balance, system events only count after its as_of_date (no double count).
"""

import calendar
import math
from datetime import date

import frappe
from frappe import _
from frappe.utils import add_months, flt, getdate, today

from upande_production.production.logic import analytics, establishment
from upande_production.production.logic.harvest import valuation_rate


def _month_end(d):
	d = getdate(d)
	return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def _add_months(d, n):
	idx = d.year * 12 + (d.month - 1) + n
	y, m = divmod(idx, 12)
	return date(y, m + 1, 1)


def series(cost_events, value_events):
	"""Pure. Events [(date, amount)] -> cumulative month-end points and the break-even date."""
	c, v = {}, {}
	for src, dst in ((cost_events, c), (value_events, v)):
		for d, amt in src:
			k = _month_end(d)
			dst[k] = dst.get(k, 0) + float(amt or 0)
	if not c and not v:
		return {"points": [], "invested": 0, "recovered": 0, "balance": 0, "pct_recovered": 0, "break_even_date": None}
	first = min(list(c) + list(v))
	last = max(list(c) + list(v) + [_month_end(today())])
	points, cost, value, be = [], 0.0, 0.0, None
	m = first
	while m <= last:
		cost += c.get(m, 0)
		value += v.get(m, 0)
		points.append({"date": m, "cost": round(cost, 2), "value": round(value, 2)})
		if be is None and cost > 0 and value >= cost:
			be = m
		m = _month_end(_add_months(m, 1))
	return {
		"points": points, "invested": round(cost, 2), "recovered": round(value, 2),
		"balance": round(value - cost, 2),
		"pct_recovered": round(value / cost * 100, 1) if cost > 0 else 0,
		"break_even_date": be,
	}


def project(balance, monthly_net, start=None):
	"""Month-end when a negative balance is cleared at a steady monthly net, else None."""
	if balance is None or balance >= 0 or not monthly_net or monthly_net <= 0:
		return None
	months = math.ceil(-balance / monthly_net)
	return _month_end(_add_months(_month_end(start or today()).replace(day=1), months))


# -- sources -----------------------------------------------------------------


def _capital_accounts():
	accounts = [r.account for r in frappe.get_all("Production Capital Account", filters={"parent": "Production Settings"},
		fields=["account"]) if r.account]
	out = set(accounts)
	for a in accounts:
		lr = frappe.db.get_value("Account", a, ["lft", "rgt", "is_group"], as_dict=True)
		if lr and lr.is_group:
			out.update(frappe.get_all("Account", filters={"lft": (">", lr.lft), "rgt": ("<", lr.rgt)}, pluck="name"))
	return out


def _labour_events(unit):
	rows = frappe.db.sql(
		"""select work_date, sum(pay_value) from `tabValue Adder Work` where docstatus = 1 and unit = %s
		group by work_date""", (unit,))
	return [(r[0], float(r[1] or 0)) for r in rows]


def _gl_events(cost_center, capital):
	if not cost_center:
		return []
	extra, args = "", {"cc": cost_center}
	if capital:
		extra = "and gle.account not in %(cap)s"
		args["cap"] = tuple(capital)
	rows = frappe.db.sql(
		f"""select gle.posting_date, sum(gle.debit - gle.credit)
		from `tabGL Entry` gle join `tabAccount` a on a.name = gle.account
		left join `tabStock Entry` se on gle.voucher_type = 'Stock Entry' and se.name = gle.voucher_no
		where gle.is_cancelled = 0 and a.root_type = 'Expense' and gle.cost_center = %(cc)s
		and (se.name is null or se.stock_entry_type != 'Harvesting') {extra}
		group by gle.posting_date""", args)
	return [(r[0], float(r[1] or 0)) for r in rows]


def _harvest_events(unit, crop):
	rows = frappe.get_all("Production Harvest", filters={"unit": unit},
		fields=["harvest_date", "qty", "value", "item"])
	out = []
	for r in rows:
		v = flt(r.value)
		if not v and r.item:
			v = flt(r.qty) * valuation_rate(r.item, crop)
		out.append((r.harvest_date, v))
	return out


def _unit_price(unit, crop):
	p = frappe.db.get_value("Production Harvest", {"unit": unit, "price_per_uom": (">", 0)}, "price_per_uom",
		order_by="harvest_date desc")
	if flt(p) > 0:
		return flt(p)
	cyc = analytics.current_cycles(crop).get(unit)
	return valuation_rate(cyc.item, crop) if cyc and cyc.item else 0


def _events(unit, crop, capital):
	"""(cost_events, value_events) for one block."""
	cost_ev, value_ev, _rc, _rv = _events_split(unit, crop, capital)
	return cost_ev, value_ev


def _events_split(unit, crop, capital):
	"""(cost_events, value_events, running_cost_events, running_value_events). The running pair holds
	only recurring flows (labour, GL running costs, harvest values): no opening-balance lump, no
	establishment costs. Projections read it."""
	ob = frappe.db.get_value("Block Opening Balance", unit,
		["as_of_date", "setup_cost", "running_costs_to_date", "value_recovered_to_date"], as_dict=True)
	est = [(getdate(d), float(a or 0)) for _u, d, _op, a in establishment.cost_rows([unit])]
	cc = frappe.db.get_value("Production Unit", unit, "cost_center")
	running = [(getdate(d), a) for d, a in _labour_events(unit) + _gl_events(cc, capital)]
	cost = est + running
	value = [(getdate(d), a) for d, a in _harvest_events(unit, crop)]
	cost_ev, value_ev = [], []
	if ob:
		as_of = getdate(ob.as_of_date)
		cost_ev.append((as_of, flt(ob.setup_cost) + flt(ob.running_costs_to_date)))
		value_ev.append((as_of, flt(ob.value_recovered_to_date)))
		cost_ev += [e for e in cost if e[0] > as_of]
		value_ev += [e for e in value if e[0] > as_of]
		run_cost = [e for e in running if e[0] > as_of]
		run_value = [e for e in value if e[0] > as_of]
	else:
		start = min((d for d, _a in est), default=None)
		if start:
			cost_ev = [e for e in cost if e[0] >= start]
		value_ev = value if start else []
		run_cost = [e for e in running if e[0] >= start] if start else []
		run_value = value_ev
	return cost_ev, value_ev, run_cost, run_value


def _forecast_for(unit, cycle=None):
	"""The one Production Forecast that counts for a unit: the current cycle's latest, else the unit's
	latest (forecasts are re-made per cycle or season and overlap, so they must not be summed)."""
	if cycle:
		name = frappe.db.get_value("Production Forecast", {"unit": unit, "cycle": cycle.name}, "name",
			order_by="modified desc, creation desc")
		if name:
			return name
	return frappe.db.get_value("Production Forecast", {"unit": unit}, "name", order_by="modified desc, creation desc")


def _forecast_value(units, crop):
	"""Expected value over the next 12 months from Production Forecast, or None without one."""
	t = getdate(today())
	end = _add_months(t.replace(day=1), 12)
	total = 0.0
	cycles = analytics.current_cycles(crop)
	for unit in units:
		fname = _forecast_for(unit, cycles.get(unit))
		if not fname:
			continue
		qty = frappe.db.sql(
			"""select sum(expected_qty) from `tabProduction Forecast Week`
			where parent = %s and week_start >= %s and week_start < %s""", (fname, t, end))[0][0]
		if qty:
			total += float(qty) * _unit_price(unit, crop)
	return total or None


def _projection(units, crop, run_cost, run_value, balance):
	"""(projected_date, years, basis). Forecast first, else the trailing 12 months. Takes running
	events only (no opening-balance lump or establishment costs)."""
	if balance >= 0:
		return None, None, None
	t = getdate(today())
	since = add_months(t, -12)
	trail_cost = sum(a for d, a in run_cost if since < d <= t) / 12
	trail_value = sum(a for d, a in run_value if since < d <= t) / 12
	fc = _forecast_value(units, crop)
	for basis, net in (("forecast", (fc / 12 - trail_cost) if fc else None), ("trailing_12m", trail_value - trail_cost)):
		if net is None:
			continue
		d = project(balance, net)
		if d:
			months = (d.year - t.year) * 12 + d.month - t.month
			return d, round(months / 12, 1), basis
	return None, None, None


def block(unit, can_see_pay, crop=None):
	if not can_see_pay:
		frappe.throw(_("Break-even includes pay; ask a manager."), frappe.PermissionError)
	crop = crop or frappe.db.get_value("Production Unit", unit, "crop")
	cost_ev, value_ev, run_cost, run_value = _events_split(unit, crop, _capital_accounts())
	s = series(cost_ev, value_ev)
	d, years, _basis = _projection([unit], crop, run_cost, run_value, s["balance"])
	return {"unit": unit, **s, "projected_date": d, "years_to_break_even": years}


def crop(crop, farm, can_see_pay):
	if not can_see_pay:
		frappe.throw(_("Break-even includes pay; ask a manager."), frappe.PermissionError)
	units = [u for u in analytics.crop_units(crop) if not u.is_group]
	if farm:
		ok = set(frappe.get_all("Production Unit", filters={"crop": crop, "farm": farm}, pluck="name"))
		units = [u for u in units if u.name in ok]
	capital = _capital_accounts()
	blocks, all_cost, all_value, all_rc, all_rv = [], [], [], [], []
	for u in units:
		cost_ev, value_ev, run_cost, run_value = _events_split(u.name, crop, capital)
		all_cost += cost_ev
		all_value += value_ev
		all_rc += run_cost
		all_rv += run_value
		s = series(cost_ev, value_ev)
		d, years, _basis = _projection([u.name], crop, run_cost, run_value, s["balance"])
		blocks.append({"unit": u.name, "invested": s["invested"], "recovered": s["recovered"], "balance": s["balance"],
			"pct_recovered": s["pct_recovered"], "break_even_date": s["break_even_date"],
			"projected_date": d, "years_to_break_even": years})
	s = series(all_cost, all_value)
	d, _years, basis = _projection([u.name for u in units], crop, all_rc, all_rv, s["balance"])
	return {"blocks": blocks, "farm": {**s, "projected_date": d, "projection_basis": basis}}
