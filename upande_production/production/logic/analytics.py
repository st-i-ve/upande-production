"""Aggregation queries behind the desk API. Each takes plain values and returns plain dicts.

Money that is pay-related is returned as None when `can_see_pay` is false.
"""

from datetime import timedelta

import frappe
from frappe.utils import add_days, getdate, today

from upande_production.production.logic import rules
from upande_production.production.logic.cycles import crop_uses_cycles
from upande_production.production.logic.weeks import iso_of


def _range(from_date, to_date):
	to = getdate(to_date) if to_date else getdate(today())
	frm = getdate(from_date) if from_date else getdate(f"{to.year}-01-01")
	return frm, to


def _monday(d):
	d = getdate(d)
	return d - timedelta(days=d.weekday())


def _pay(v, can_see_pay):
	return v if can_see_pay else None


# -- units -------------------------------------------------------------------


def crop_units(crop):
	return frappe.get_all(
		"Production Unit",
		filters={"crop": crop},
		fields=[
			"name", "unit_type", "parent_production_unit as parent", "is_group", "area_ha",
			"plant_count", "cost_center", "status", "lft", "rgt",
		],
		order_by="lft asc",
	)


def _rollup(units, direct):
	"""Sum `direct` (unit -> value) over each unit's subtree using lft/rgt."""
	out = {}
	for u in units:
		lo, hi = u.lft or 0, u.rgt or 0
		total = 0
		for v in units:
			if (v.lft or 0) >= lo and (v.rgt or 0) <= hi:
				total += direct.get(v.name, 0) or 0
		out[u.name] = total
	return out


def current_cycles(crop):
	"""unit -> latest Active/Harvesting cycle row. Empty for crops without cycles."""
	if not crop_uses_cycles(crop):
		return {}
	rows = frappe.get_all(
		"Production Crop Cycle",
		filters={"crop": crop, "status": ("in", ["Active", "Harvesting"])},
		fields=["name", "unit", "item", "start_date", "variety", "current_stage"],
		order_by="start_date asc",
	)
	return {r.unit: r for r in rows}


def _labour_by_unit(names, frm, to):
	if not names:
		return {}
	rows = frappe.db.sql(
		"""select unit, sum(pay_value) from `tabValue Adder Work`
		where docstatus=1 and unit in %(u)s and work_date between %(f)s and %(t)s group by unit""",
		{"u": tuple(names), "f": frm, "t": to},
	)
	return {r[0]: float(r[1] or 0) for r in rows}


def _harvest_by_unit(names, frm, to):
	if not names:
		return {}, {}
	rows = frappe.db.sql(
		"""select unit, sum(qty), sum(value) from `tabProduction Harvest`
		where unit in %(u)s and harvest_date between %(f)s and %(t)s group by unit""",
		{"u": tuple(names), "f": frm, "t": to},
	)
	return {r[0]: float(r[1] or 0) for r in rows}, {r[0]: float(r[2] or 0) for r in rows}


def _inputs_by_cc(ccs, frm, to):
	ccs = [c for c in ccs if c]
	if not ccs:
		return {}
	rows = frappe.db.sql(
		"""select gle.cost_center, sum(gle.debit - gle.credit)
		from `tabGL Entry` gle join `tabAccount` a on a.name = gle.account
		where gle.is_cancelled = 0 and a.root_type = 'Expense'
		and gle.cost_center in %(c)s and gle.posting_date between %(f)s and %(t)s
		group by gle.cost_center""",
		{"c": tuple(ccs), "f": frm, "t": to},
	)
	return {r[0]: float(r[1] or 0) for r in rows}


# -- overview ----------------------------------------------------------------


def _week_tasks(crop, year, week):
	plans = frappe.get_all(
		"Production Work Plan", filters={"crop": crop, "plan_year": year, "plan_week": week}, pluck="name"
	)
	if not plans:
		return []
	return frappe.get_all(
		"Production Plan Task",
		filters={"parenttype": "Production Work Plan", "parent": ("in", plans)},
		fields=["unit", "status", "deviation"],
	)


def overview(crop, can_see_pay):
	t = getdate(today())
	iso_y, iso_w = iso_of(t)
	units = crop_units(crop)
	names = [u.name for u in units]
	cycles = current_cycles(crop)
	tasks = _week_tasks(crop, iso_y, iso_w)

	season_from = getdate(f"{t.year}-01-01")
	month_from = getdate(f"{t.year}-{t.month:02d}-01")
	labour_season = _rollup(units, _labour_by_unit(names, season_from, t))
	harvest_qty, _val = _harvest_by_unit(names, season_from, t)
	harvest_roll = _rollup(units, harvest_qty)
	labour_mtd = sum(_labour_by_unit(names, month_from, t).values())

	open_by_unit = {}
	for k in tasks:
		if k.status in ("Open", "In Progress"):
			open_by_unit[k.unit] = open_by_unit.get(k.unit, 0) + 1
	open_roll = _rollup(units, open_by_unit)

	w_start = _monday(t)
	w_end = w_start + timedelta(days=27)
	forecast_next4 = frappe.db.sql(
		"""select sum(w.expected_qty) from `tabProduction Forecast Week` w
		join `tabProduction Forecast` f on f.name = w.parent
		where f.crop = %s and w.week_start between %s and %s""",
		(crop, w_start, w_end),
	)[0][0]
	committed_next4 = frappe.db.sql(
		"""select sum(committed_qty) from `tabBuyer Commitment`
		where crop = %s and status != 'Cancelled' and week_start between %s and %s""",
		(crop, w_start, w_end),
	)[0][0]

	total = len(tasks)
	done = sum(1 for k in tasks if k.status == "Done")
	# Deviations look back over the last 4 ISO weeks, this one included.
	dev_from = w_start - timedelta(days=21)
	n_deviations = len(deviations(crop, dev_from, t)["rows"])
	return {
		"tiles": {
			"active_cycles": len(cycles),
			"tasks_total": total,
			"tasks_done": done,
			"done_pct": round(done / total * 100, 1) if total else 0,
			"deviations": n_deviations,
			"labour_cost_mtd": _pay(round(labour_mtd, 2), can_see_pay),
			"forecast_next4": float(forecast_next4 or 0),
			"committed_next4": float(committed_next4 or 0),
			"harvest_qty_season": sum(harvest_qty.values()),
		},
		"blocks": [
			{
				"unit": u.name,
				"unit_type": u.unit_type,
				"parent": u.parent,
				"area_ha": u.area_ha or 0,
				"cycle": cycles[u.name].name if u.name in cycles else None,
				"item": cycles[u.name].item if u.name in cycles else None,
				"tasks_open": open_roll.get(u.name, 0),
				"labour_cost_season": _pay(round(labour_season.get(u.name, 0), 2), can_see_pay),
				"harvest_qty_season": harvest_roll.get(u.name, 0),
			}
			for u in units
		],
	}


# -- block costs -------------------------------------------------------------


def block_costs(crop, from_date, to_date, can_see_pay):
	frm, to = _range(from_date, to_date)
	units = crop_units(crop)
	names = [u.name for u in units]
	labour = _rollup(units, _labour_by_unit(names, frm, to))
	gl = _inputs_by_cc([u.cost_center for u in units], frm, to)
	inputs = _rollup(units, {u.name: gl.get(u.cost_center, 0) for u in units})
	hq, hv = _harvest_by_unit(names, frm, to)
	hq, hv = _rollup(units, hq), _rollup(units, hv)
	rows = []
	for u in units:
		lab, inp, rev = labour.get(u.name, 0), inputs.get(u.name, 0), hv.get(u.name, 0)
		total = lab + inp
		area = u.area_ha or 0
		rows.append({
			"unit": u.name, "unit_type": u.unit_type, "parent": u.parent, "is_group": u.is_group,
			"area_ha": area,
			"labour": _pay(round(lab, 2), can_see_pay),
			"inputs": round(inp, 2),
			"total_cost": _pay(round(total, 2), can_see_pay),
			"cost_per_ha": _pay(round(total / area, 2) if area else 0, can_see_pay),
			"harvest_qty": hq.get(u.name, 0),
			"revenue": round(rev, 2),
			"margin": _pay(round(rev - total, 2), can_see_pay),
		})
	return {"rows": rows}


# -- value adders ------------------------------------------------------------


def merge_uoms(parts):
	"""[(uom, qty), ...] -> [{"uom", "qty"}] summed per UOM, biggest first.

	Work quantities are never added across units of measure (6 Hectare + 309 Tree is
	not 315 of anything), so every figure is carried per UOM."""
	acc = {}
	for uom, qty in parts:
		acc[uom or ""] = acc.get(uom or "", 0.0) + float(qty or 0)
	return [{"uom": u, "qty": round(v, 4)} for u, v in sorted(acc.items(), key=lambda kv: (-kv[1], kv[0]))]


def value_adder_summary(crop, from_date, to_date, group_by, can_see_pay):
	frm, to = _range(from_date, to_date)
	if group_by not in ("employee", "day", "unit"):
		frappe.throw("group_by must be employee, day or unit", frappe.ValidationError)
	key = {"employee": "employee", "day": "work_date", "unit": "unit"}[group_by]
	label = "max(employee_name)" if group_by == "employee" else key
	data = frappe.db.sql(
		f"""select {key}, {label}, uom, sum(qty), sum(hours), sum(pay_value), count(*)
		from `tabValue Adder Work`
		where docstatus = 1 and crop = %s and work_date between %s and %s
		group by {key}, uom order by {key}""",
		(crop, frm, to),
	)
	grouped = {}
	for k, lab, uom, qty, hours, pay, n in data:
		g = grouped.setdefault(str(k), {"label": None, "uoms": [], "hours": 0.0, "pay": 0.0, "entries": 0})
		g["label"] = g["label"] or str(lab or k)
		g["uoms"].append((uom, qty))
		g["hours"] += float(hours or 0)
		g["pay"] += float(pay or 0)
		g["entries"] += n
	rows = [
		{
			"key": k, "label": g["label"], "qty_by_uom": merge_uoms(g["uoms"]),
			"hours": g["hours"], "pay_value": _pay(round(g["pay"], 2), can_see_pay), "entries": g["entries"],
		}
		for k, g in grouped.items()
	]
	total = round(sum(float(r[5] or 0) for r in data), 2)
	return {
		"rows": rows,
		"total_pay": _pay(total, can_see_pay),
		"total_qty_by_uom": merge_uoms((r[2], r[3]) for r in data),
	}


# -- deviations --------------------------------------------------------------


def deviations(crop, from_date, to_date):
	frm, to = _range(from_date, to_date)
	rows = []

	plans = frappe.get_all("Production Work Plan", filters={"crop": crop}, pluck="name")
	if plans:
		tasks = frappe.get_all(
			"Production Plan Task",
			filters={
				"parenttype": "Production Work Plan", "parent": ("in", plans),
				"deviation": ("in", ["Late", "Partial", "Skipped"]),
				"due_date": ("between", [frm, to]),
			},
			fields=[
				"parent", "unit", "operation_name", "due_date", "deviation", "planned_qty",
				"done_qty", "uom", "completed_at",
			],
			order_by="due_date asc",
		)
		for k in tasks:
			if k.deviation == "Late":
				detail = f"Completed {getdate(k.completed_at)} against due {k.due_date}" if k.completed_at else "Completed late"
			elif k.deviation == "Partial":
				detail = f"{k.done_qty or 0:g} of {k.planned_qty or 0:g} {k.uom or ''}".strip() + " done"
			else:
				detail = "Skipped"
			rows.append({
				"kind": k.deviation, "unit": k.unit, "operation_name": k.operation_name,
				"due_date": k.due_date, "plan": k.parent, "detail": detail,
			})

	# Deviations are plan tasks that ran late/partial/skipped plus protocol steps never planned.
	# Unplanned work (one Value Adder Work row each) is extra output, not a deviation, so it is
	# never counted here; Overview tile, recent list and the deviations endpoint all share this.
	op_names = dict(frappe.get_all("Production Operation", filters={"crop": crop}, fields=["name", "operation_name"], as_list=True))
	rows.extend(_missed(crop, frm, to, op_names))
	rows.sort(key=lambda r: (str(r["due_date"]), r["kind"]))
	return {"rows": rows}


def _missed(crop, frm, to, op_names):
	last = min(to, getdate(add_days(today(), -1)))
	if frm > last:
		return []
	cycles = frappe.get_all(
		"Production Crop Cycle",
		filters={"crop": crop, "status": ("in", ["Active", "Harvesting"]), "protocol": ("is", "set")},
		fields=["name", "unit", "start_date", "protocol"],
	)
	if not cycles:
		return []
	refs = set(
		frappe.get_all(
			"Production Plan Task",
			filters={"parenttype": "Production Work Plan", "cycle": ("in", [c.name for c in cycles]), "protocol_ref": ("is", "set")},
			pluck="protocol_ref",
		)
	)
	protocols, out = {}, []
	for cy in cycles:
		proto = protocols.get(cy.protocol) or protocols.setdefault(
			cy.protocol, frappe.get_doc("Production Protocol", cy.protocol)
		)
		for step in proto.steps:
			for k in range(int(step.repeat_count or 1)):
				due = getdate(add_days(getdate(cy.start_date), int(step.day_offset or 0) + k * int(step.repeat_every_days or 0)))
				if not (frm <= due <= last) or f"{cy.name}:{step.name}:{k}" in refs:
					continue
				out.append({
					"kind": "Missed", "unit": cy.unit,
					"operation_name": op_names.get(step.operation) or frappe.db.get_value("Production Operation", step.operation, "operation_name"),
					"due_date": due, "plan": None,
					"detail": f"Protocol {cy.protocol} step due {due} was never planned",
				})
	return out


# -- protocol check ----------------------------------------------------------


def _step_status(task, due, today_d):
	"""Status of one protocol step occurrence. `task` is the plan task row or None."""
	if not task:
		return "not_planned"
	if task.status == "Skipped":
		return "skipped"
	if task.status in ("Done", "Partly Done") and float(task.pending_qty or 0) > 0:
		return "pending_approval"
	if task.deviation == "Late":
		return "late"
	if task.deviation == "Partial" or task.status == "Partly Done":
		return "partial"
	if task.status == "Done":
		return "done"
	return "late" if due < today_d else "open"


CHECK_KEYS = ("done", "partial", "late", "skipped", "pending_approval", "open", "not_planned")


def protocol_check(crop, year, week, unit=None):
	"""Protocol steps due in an ISO week for each cycle's pinned (Active or Superseded) protocol, with
	their plan status. Crops without cycles (apiary, aquaculture) return no rows and a reason."""
	from upande_production.production.logic.weeks import iso_week_bounds

	start, end = iso_week_bounds(year, week)
	today_d = getdate(today())
	out = {"crop": crop, "year": int(year), "week": int(week), "week_start": start, "week_end": end,
		"unit": unit or None, "reason": None, "blocks": [],
		"totals": {"steps": 0, **{k: 0 for k in CHECK_KEYS}, "planned_qty_by_uom": [], "done_qty_by_uom": []}}
	if not crop_uses_cycles(crop):
		out["reason"] = "This crop does not run in crop cycles, so it has no protocol steps."
		return out
	filters = {"crop": crop, "status": ("in", ["Active", "Harvesting"]), "protocol": ("is", "set")}
	if unit:
		filters["unit"] = unit
	cycles = frappe.get_all("Production Crop Cycle", filters=filters,
		fields=["name", "unit", "start_date", "protocol"], order_by="unit asc")
	if not cycles:
		out["reason"] = "No active cycle with a protocol" + (" on this block." if unit else " for this crop.")
		return out
	tasks = {
		t.protocol_ref: t for t in frappe.get_all(
			"Production Plan Task",
			filters={"parenttype": "Production Work Plan", "cycle": ("in", [c.name for c in cycles]),
				"protocol_ref": ("is", "set")},
			fields=["name", "parent", "protocol_ref", "status", "deviation", "planned_qty", "done_qty",
				"pending_qty", "uom", "due_date"],
		)
	}
	op_names = dict(frappe.get_all("Production Operation", filters={"crop": crop},
		fields=["name", "operation_name"], as_list=True))
	unit_names = dict(frappe.get_all("Production Unit", filters={"crop": crop},
		fields=["name", "unit_name"], as_list=True))
	planned_parts, done_parts, protocols = [], [], {}
	for cy in cycles:
		proto = protocols.get(cy.protocol) or protocols.setdefault(
			cy.protocol, frappe.get_doc("Production Protocol", cy.protocol))
		if proto.version_status not in ("Active", "Superseded"):
			continue
		steps = []
		for step in proto.steps:
			for k in range(int(step.repeat_count or 1)):
				due = getdate(add_days(getdate(cy.start_date),
					int(step.day_offset or 0) + k * int(step.repeat_every_days or 0)))
				if not (start <= due <= end):
					continue
				t = tasks.get(f"{cy.name}:{step.name}:{k}")
				status = _step_status(t, due, today_d)
				breaches = rules.check(cycle=cy.name, unit=cy.unit, operation=step.operation, on_date=due,
					exclude_task=t.name if t else None)
				uom = t.uom if t else frappe.db.get_value("Production Operation", step.operation, "work_uom")
				planned = float(t.planned_qty or 0) if t else float(step.planned_qty or 0)
				done = float(t.done_qty or 0) if t else 0.0
				steps.append({
					"protocol_ref": f"{cy.name}:{step.name}:{k}", "operation": step.operation,
					"operation_name": op_names.get(step.operation) or step.operation, "due_date": due,
					"status": status, "planned_qty": planned, "done_qty": done,
					"pending_qty": float(t.pending_qty or 0) if t else 0.0, "uom": uom,
					"plan": t.parent if t else None, "task": t.name if t else None,
					"task_status": t.status if t else None, "note": step.note,
					"rule_status": rules.worst(breaches), "breaches": breaches,
				})
				out["totals"][status] += 1
				out["totals"]["steps"] += 1
				planned_parts.append((uom, planned))
				done_parts.append((uom, done))
		steps.sort(key=lambda r: (str(r["due_date"]), r["operation_name"]))
		block = {"unit": cy.unit, "unit_name": unit_names.get(cy.unit) or cy.unit, "cycle": cy.name,
			"protocol": cy.protocol, "protocol_version_status": proto.version_status,
			"steps": steps, "breaches": [
				{**b, "operation": s["operation"], "operation_name": s["operation_name"], "due_date": s["due_date"]}
				for s in steps for b in s["breaches"]],
			"counts": {k: sum(1 for s in steps if s["status"] == k) for k in CHECK_KEYS}}
		out["blocks"].append(block)
	out["totals"]["planned_qty_by_uom"] = merge_uoms(planned_parts)
	out["totals"]["done_qty_by_uom"] = merge_uoms(done_parts)
	if not out["totals"]["steps"]:
		out["reason"] = "No protocol steps fall due in this week."
	return out


# -- forecast ----------------------------------------------------------------


def _pct(actual, forecast):
	return round((actual - forecast) / forecast * 100, 1) if forecast and forecast > 0 else None


def forecast_summary(crop, from_date, to_date):
	frm, to = _range(from_date, to_date)
	frm = _monday(frm)
	uom = frappe.db.get_value("Production Crop", crop, "yield_uom")

	fc = frappe.db.sql(
		"""select w.week_start, f.unit, sum(w.expected_qty)
		from `tabProduction Forecast Week` w join `tabProduction Forecast` f on f.name = w.parent
		where f.crop = %s and w.week_start between %s and %s group by w.week_start, f.unit""",
		(crop, frm, to),
	)
	ac = frappe.db.sql(
		"""select date_sub(harvest_date, interval weekday(harvest_date) day), unit, sum(qty)
		from `tabProduction Harvest` where crop = %s and harvest_date between %s and %s
		group by 1, 2""",
		(crop, frm, to),
	)
	cm = frappe.db.sql(
		"""select week_start, sum(committed_qty) from `tabBuyer Commitment`
		where crop = %s and status != 'Cancelled' and week_start between %s and %s group by week_start""",
		(crop, frm, to),
	)
	this_monday = _monday(today())
	wf, wa, wc, uf, ua = {}, {}, {}, {}, {}
	for ws, unit, q in fc:
		wf[getdate(ws)] = wf.get(getdate(ws), 0) + float(q or 0)
		# Only weeks up to the current one have actuals to compare with.
		if getdate(ws) <= this_monday:
			uf[unit] = uf.get(unit, 0) + float(q or 0)
	for ws, unit, q in ac:
		wa[getdate(ws)] = wa.get(getdate(ws), 0) + float(q or 0)
		ua[unit] = ua.get(unit, 0) + float(q or 0)
	for ws, q in cm:
		wc[getdate(ws)] = float(q or 0)

	weeks = []
	for ws in sorted(set(wf) | set(wa) | set(wc)):
		iso_y, iso_w = iso_of(ws)
		f, a = wf.get(ws, 0), wa.get(ws, 0)
		weeks.append({
			"iso_year": iso_y, "iso_week": iso_w, "week_start": ws, "forecast": f, "actual": a,
			"committed": wc.get(ws, 0), "error_pct": _pct(a, f) if ws <= this_monday else None,
		})
	units = [
		{
			"unit": u, "forecast": uf.get(u, 0), "forecast_to_date": uf.get(u, 0),
			"actual": ua.get(u, 0), "error_pct": _pct(ua.get(u, 0), uf.get(u, 0)),
		}
		for u in sorted(set(uf) | set(ua))
	]
	fc_to_date = sum(uf.values())
	actual_total = sum(wa.values())
	totals = {
		"forecast": sum(wf.values()), "forecast_to_date": fc_to_date, "actual": actual_total,
		"committed": sum(wc.values()), "error_pct": _pct(actual_total, fc_to_date),
	}
	seasons = frappe.db.sql(
		"select year(harvest_date), sum(qty) from `tabProduction Harvest` where crop = %s group by 1 order by 1",
		(crop,),
	)
	return {
		"uom": uom, "weeks": weeks, "units": units, "totals": totals,
		"seasons": [{"year": int(y), "actual": float(q or 0)} for y, q in seasons],
	}
