"""Desk API for the production frontend. Every endpoint returns data or {"error": msg}."""

import frappe
from frappe import _

from upande_production.api.envelope import as_dict, run
from upande_production.production.logic import analytics, cycle_chain, plans, rules, stages, work
from upande_production.production.logic.settings import PAY_ROLES, can_see_pay
from upande_production.production.logic.weeks import iso_week_bounds

MANAGE_ROLES = {"Production Manager", "System Manager"}


# -- helpers -----------------------------------------------------------------


def _is_admin():
	return frappe.session.user == "Administrator"


def _can_see_pay():
	return can_see_pay()


def _need(doctype, ptype="read"):
	frappe.has_permission(doctype, ptype, throw=True)


def _pay(v, can_pay):
	return v if can_pay else None


def _farm(farm):
	return farm or None


def _save(doctype, data, protected=()):
	"""Insert, or update when data.name is set. Returns the saved doc."""
	data = dict(as_dict(data) or {})
	for k in ("doctype", "docstatus", "modified", "creation", "owner", *protected):
		data.pop(k, None)
	name = data.pop("name", None)
	if name:
		_need(doctype, "write")
		doc = frappe.get_doc(doctype, name)
		doc.update(data)
		doc.save()
	else:
		_need(doctype, "create")
		if "crop" in frappe.get_meta(doctype).get_valid_columns() and not data.get("crop") and data.get("unit"):
			data["crop"] = frappe.db.get_value("Production Unit", data["unit"], "crop")
		doc = frappe.get_doc({"doctype": doctype, **data})
		doc.insert()
	return doc


def _unit_rows(crop):
	"""Unit rows for list_units, including current cycle/item and has_geojson."""
	rows = frappe.db.sql(
		"""select name, unit_type, parent_production_unit as parent, is_group, area_ha, plant_count,
		cost_center, status, if(ifnull(geojson, '') = '', 0, 1) as has_geojson
		from `tabProduction Unit` where crop = %s order by lft""",
		(crop,),
		as_dict=True,
	)
	cycles = analytics.current_cycles(crop)
	flag_by_cycle = {x["cycle"]: x["flags"] for x in cycle_chain.flag_rows(crop)}
	for r in rows:
		cy = cycles.get(r.name)
		r["current_cycle"] = cy.name if cy else None
		r["item"] = cy.item if cy else None
		r["variety"] = cy.variety if cy else None
		r["current_stage"] = cy.current_stage if cy else None
		r["flags"] = flag_by_cycle.get(cy.name, []) if cy else []
	dm = _dry_matter_by_unit(crop)
	replaced = _plants_replaced(crop)
	for r in rows:
		r["dry_matter"] = dm.get(r.name)
		r["plants_replaced"] = replaced.get(r.name, 0)
	return rows


def _dry_matter_by_unit(crop):
	"""Latest dry matter per unit: generic Dry Matter Test, or Avocado Maturity Test for avocado."""
	from upande_production.api import drymatter

	out = drymatter.latest_by_unit(crop)
	if frappe.db.get_value("Production Crop", crop, "crop_key") == "avocado":
		try:
			from upande_production.api import avocadoapi
			from upande_production.api.avocadomaturity import MIN_DRY_MATTER_PCT

			for blk, p in avocadoapi.dm_projection(avocadoapi._samples()).items():
				out.setdefault(blk, {"pct": p["dry_matter_pct"], "target": MIN_DRY_MATTER_PCT,
					"ready": bool(p["ready"]), "date": p["sample_date"]})
		except Exception:
			frappe.log_error(title="upande_production: avocado dry matter on blocks")
	return out


def _plants_replaced(crop):
	"""Approved Gap filling work (uom Plant) per unit."""
	rows = frappe.db.sql(
		"""select w.unit, sum(w.qty) from `tabValue Adder Work` w
		join `tabProduction Operation` o on o.name = w.operation
		where w.crop = %s and w.docstatus < 2 and w.approval_status = 'Approved' and w.uom = 'Plant'
		and o.operation_name = 'Gap filling' group by w.unit""",
		(crop,),
	)
	return {u: int(q or 0) for u, q in rows}


# -- bootstrap ---------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
@run
def get_bootstrap():
	roles = set(frappe.get_roles())
	admin = _is_admin()
	crops = frappe.get_all(
		"Production Crop",
		filters={"enabled": 1},
		fields=[
			"name", "crop_key", "accent_color", "icon_key", "unit_label", "parent_unit_label",
			"sub_unit_label", "yield_uom", "uses_crop_cycles",
		],
		order_by="sort_order asc, name asc",
	)
	return {
		"crops": crops,
		"farms": frappe.get_all("Farm", pluck="name", order_by="name asc"),
		"can_see_pay": _can_see_pay(),
		"can_plan": admin or bool(PAY_ROLES & roles),
		"can_manage": admin or bool(MANAGE_ROLES & roles),
	}


# -- overview, units, cycles -------------------------------------------------


@frappe.whitelist(methods=["POST"])
@run
def get_overview(crop):
	_need("Production Unit")
	return analytics.overview(crop, _can_see_pay())


@frappe.whitelist(methods=["POST"])
@run
def list_units(crop):
	_need("Production Unit")
	return {"units": _unit_rows(crop)}


@frappe.whitelist(methods=["POST"])
@run
def get_unit(name):
	_need("Production Unit")
	doc = frappe.get_doc("Production Unit", name)
	unit = doc.as_dict()
	unit["parent"] = doc.parent_production_unit
	cycles = frappe.get_all(
		"Production Crop Cycle", filters={"unit": name}, fields=_CYCLE_FIELDS, order_by="start_date desc"
	)
	cur = next((c for c in cycles if c.status in ("Active", "Harvesting")), None)
	unit["current_cycle"] = cur.name if cur else None
	unit["item"] = cur.item if cur else None
	pay = _can_see_pay()
	work_rows = frappe.get_all(
		"Value Adder Work",
		filters={"unit": name, "docstatus": 1},
		fields=["name", "work_date", "employee", "employee_name", "operation", "qty", "uom", "hours", "rate", "pay_value"],
		order_by="work_date desc, creation desc",
		limit=20,
	)
	for w in work_rows:
		w["rate"], w["pay_value"] = _pay(w["rate"], pay), _pay(w["pay_value"], pay)
	return {"unit": unit, "cycles": cycles, "recent_work": work_rows}


_CYCLE_FIELDS = [
	"name", "title", "unit", "item", "cycle_type", "start_date", "expected_harvest_start",
	"expected_harvest_end", "protocol", "status", "area_ha", "previous_cycle", "variety", "current_stage",
	"cycle_no", "expected_flowering_date", "actual_flowering_date", "actual_harvest_start", "actual_harvest_end",
	"due_for_uprooting", "proposed_next_cycle", "protocol_flags",
]


@frappe.whitelist(methods=["POST"])
@run
def list_cycles(crop, unit=None, status=None):
	_need("Production Crop Cycle")
	filters = {"crop": crop}
	if unit:
		filters["unit"] = unit
	if status:
		filters["status"] = status
	cycles = frappe.get_all("Production Crop Cycle", filters=filters, fields=_CYCLE_FIELDS, order_by="start_date desc")
	for c in cycles:
		c["stage_bands"] = _stage_bands(c)
		c["flags"] = [f for f in (c.pop("protocol_flags", None) or "").split("\n") if f]
	return {"cycles": cycles}


@frappe.whitelist(methods=["POST"])
@run
def cycle_flags(crop):
	"""Open cycles that are off protocol: {"rows": [{cycle, unit, variety, flags: [str]}]}."""
	_need("Production Crop Cycle")
	return {"rows": cycle_chain.flag_rows(crop)}


def _stage_bands(c):
	"""The variety's stages with real dates (actuals applied) for the Gantt; [] without a variety."""
	if not c.get("variety"):
		return []
	try:
		return [
			{"stage": b["stage"], "start": str(b["start"]), "end": str(b["end"]), "is_harvest": int(b["is_harvest"]),
				"actual": bool(b["actual"])}
			for b in stages.timeline(c["name"])
		]
	except Exception:
		return []


@frappe.whitelist(methods=["POST"])
@run
def save_cycle(data):
	before = None
	name = as_dict(data).get("name") if as_dict(data) else None
	if name:
		before = frappe.db.get_value("Production Crop Cycle", name, "proposed_next_cycle")
	doc = _save("Production Crop Cycle", data)
	after = doc.get("proposed_next_cycle")
	return {"name": doc.name, "proposed_next_cycle": after if after and after != before else None}


# -- weekly plan -------------------------------------------------------------

_TASK_EDITABLE = ("unit", "cycle", "operation", "planned_qty", "uom", "rate", "due_date", "supervisor", "note")


@frappe.whitelist(methods=["POST"])
@run
def get_plan(crop, farm, year, week):
	_need("Production Work Plan")
	year, week = int(year), int(week)
	start, end = iso_week_bounds(year, week)
	filters = {"crop": crop, "plan_year": year, "plan_week": week}
	filters["farm"] = farm if farm else ("in", ["", None])
	name = frappe.db.get_value("Production Work Plan", filters)
	out = {"plan": name, "week_start": start, "week_end": end, "tasks": []}
	if not name:
		return out
	pay = _can_see_pay()
	tasks = frappe.get_all(
		"Production Plan Task",
		filters={"parent": name, "parenttype": "Production Work Plan"},
		fields=[
			"name", "unit", "cycle", "operation", "operation_name", "planned_qty", "done_qty", "pending_qty", "uom",
			"rate", "due_date", "supervisor", "status", "deviation", "protocol_ref", "note",
			"rule_status", "rule_notes", "override_reason",
		],
		order_by="idx asc",
	)
	by_task = {}
	for w in frappe.get_all(
		"Value Adder Work",
		filters={"plan": name, "docstatus": ("<", 2)},
		fields=["name", "plan_task", "employee", "employee_name", "qty", "hours", "pay_value",
			"approval_status", "review_note"],
		order_by="creation asc",
	):
		w["pay_value"] = _pay(w["pay_value"], pay)
		by_task.setdefault(w.pop("plan_task"), []).append(w)
	sup = [t.supervisor for t in tasks if t.supervisor]
	sup_names = (
		dict(frappe.get_all("Employee", filters={"name": ("in", sup)}, fields=["name", "employee_name"], as_list=True))
		if sup
		else {}
	)
	colors = dict(frappe.get_all("Production Operation", fields=["name", "color"], as_list=True))
	for t in tasks:
		t["color"] = colors.get(t.operation) or None
		t["rate"] = _pay(t["rate"], pay)
		t["deviation"] = t.deviation or None
		t["supervisor_name"] = sup_names.get(t.supervisor)
		t["work"] = by_task.get(t.name, [])
	out["tasks"] = tasks
	return out


def _task_rules(vals, override_reason=None, exclude_task=None) -> dict:
	"""Activity rules for a task being added or moved: Block refuses, Warn needs override_reason."""
	if not (vals.get("operation") and vals.get("unit") and vals.get("due_date")):
		return {}
	breaches = rules.check(cycle=vals.get("cycle") or None, unit=vals["unit"], operation=vals["operation"],
		on_date=vals["due_date"], exclude_task=exclude_task)
	return rules.enforce(breaches, override_reason)


@frappe.whitelist(methods=["POST"])
@run
def save_plan_tasks(crop, farm, year, week, tasks, override_reason=None):
	_need("Production Work Plan", "write")
	tasks = as_dict(tasks) or []
	plan = plans.get_or_create_plan(crop, _farm(farm), int(year), int(week))
	for t in tasks:
		name = t.get("name")
		if t.get("_delete"):
			plan.tasks = [r for r in plan.tasks if r.name != name]
			continue
		vals = {k: t.get(k) for k in _TASK_EDITABLE if k in t}
		if name:
			row = next((r for r in plan.tasks if r.name == name), None)
			if not row:
				frappe.throw(_("Task {0} not found on this plan").format(name), frappe.ValidationError)
			if any(k in vals and vals[k] != row.get(k) for k in ("unit", "operation", "due_date")):
				vals.update(_task_rules({**row.as_dict(), **vals}, override_reason, exclude_task=row.name))
			row.update(vals)
		else:
			if vals.get("operation") and not (vals.get("uom") and vals.get("rate")):
				op = frappe.db.get_value(
					"Production Operation", vals["operation"], ["work_uom", "default_rate"], as_dict=True
				)
				vals.setdefault("uom", op.work_uom)
				if vals.get("rate") in (None, ""):
					vals["rate"] = op.default_rate
			vals.update(_task_rules(vals, override_reason))
			plan.append("tasks", {**vals, "status": "Open"})
	for i, r in enumerate(plan.tasks, 1):
		r.idx = i
	plan.save()
	return {"name": plan.name}


@frappe.whitelist(methods=["POST"])
@run
def generate_plan_week(crop, farm, year, week):
	_need("Production Work Plan", "create")
	plan = plans.get_or_create_plan(crop, _farm(farm), int(year), int(week))
	res = plans.generate_week_detail(plan.name)
	return {"name": plan.name, "created": res["created"], "skipped": res["skipped"]}


@frappe.whitelist(methods=["POST"])
@run
def record_task_work(plan, task, status, entries=None, note="", work_date=None, override_reason=None):
	_need("Production Work Plan", "write")
	entries = as_dict(entries) or []
	if entries:
		_need("Value Adder Work", "create")
	res = work.record_task_work(plan, task, status, entries, note or "", work_date or None,
		override_reason=override_reason or None)
	if not _can_see_pay():
		res["task"]["rate"] = None
	return res


# -- value adders ------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
@run
def list_value_adders():
	_need("Value Adder Work")
	people = frappe.get_all(
		"Employee",
		filters={"designation": "Value Adder", "status": "Active"},
		fields=["name", "employee_name", "image"],
		order_by="employee_name asc",
	)
	return {"people": people}


@frappe.whitelist(methods=["POST"])
@run
def value_adder_summary(crop, from_date=None, to_date=None, group_by="employee"):
	_need("Value Adder Work")
	return analytics.value_adder_summary(crop, from_date, to_date, group_by, _can_see_pay())


# -- costs, deviations, forecast ---------------------------------------------


@frappe.whitelist(methods=["POST"])
@run
def block_costs(crop, from_date=None, to_date=None):
	_need("Production Unit")
	return analytics.block_costs(crop, from_date, to_date, _can_see_pay())


@frappe.whitelist(methods=["POST"])
@run
def deviations(crop, from_date=None, to_date=None):
	_need("Production Work Plan")
	return analytics.deviations(crop, from_date, to_date)


@frappe.whitelist(methods=["POST"])
@run
def forecast_summary(crop, from_date=None, to_date=None):
	_need("Production Forecast")
	return analytics.forecast_summary(crop, from_date, to_date)


# -- records -----------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
@run
def list_samples(crop, unit=None):
	_need("Yield Sample")
	filters = {"crop": crop}
	if unit:
		filters["unit"] = unit
	return {"rows": frappe.get_all("Yield Sample", filters=filters, fields=["*"], order_by="sample_date desc", limit=500)}


@frappe.whitelist(methods=["POST"])
@run
def save_sample(data):
	return {"name": _save("Yield Sample", data, protected=("est_unit_yield",)).name}


@frappe.whitelist(methods=["POST"])
@run
def save_harvest(data):
	return {"name": _save("Production Harvest", data, protected=("value",)).name}


@frappe.whitelist(methods=["POST"])
@run
def list_harvests(crop, from_date=None, to_date=None):
	_need("Production Harvest")
	frm, to = analytics._range(from_date, to_date)
	return {
		"rows": frappe.get_all(
			"Production Harvest",
			filters={"crop": crop, "harvest_date": ("between", [frm, to])},
			fields=["*"],
			order_by="harvest_date desc",
			limit=1000,
		)
	}


@frappe.whitelist(methods=["POST"])
@run
def list_commitments(crop):
	_need("Buyer Commitment")
	return {
		"rows": frappe.get_all(
			"Buyer Commitment", filters={"crop": crop}, fields=["*"], order_by="week_start desc", limit=1000
		)
	}


@frappe.whitelist(methods=["POST"])
@run
def save_commitment(data):
	return {"name": _save("Buyer Commitment", data).name}


@frappe.whitelist(methods=["POST"])
@run
def list_operations(crop):
	_need("Production Operation")
	pay = _can_see_pay()
	rows = frappe.get_all("Production Operation", filters={"crop": crop}, fields=["*"], order_by="operation_name asc")
	for r in rows:
		r["default_rate"] = _pay(r.get("default_rate"), pay)
	return {"rows": rows}


@frappe.whitelist(methods=["POST"])
@run
def save_operation(data):
	return {"name": _save("Production Operation", data).name}


@frappe.whitelist(methods=["POST"])
@run
def list_protocols(crop):
	_need("Production Protocol")
	rows = frappe.get_all("Production Protocol", filters={"crop": crop, "version_status": "Active"}, fields=["*"], order_by="protocol_name asc")
	for r in rows:
		for table, doctype, fields in (
			("key_activities", "Production Protocol Key Activity", ["name", "operation", "week", "repeats", "planned_qty", "description"]),
			("cultural_activities", "Production Protocol Cultural Activity", ["name", "operation", "schedule", "interval_weeks",
				"establishment_period_weeks", "pre_harvest_interval_days", "planned_qty", "description"]),
			("capital_activities", "Production Protocol Capital Activity", ["name", "operation", "description", "budget_per_ha"]),
		):
			r[table] = frappe.get_all(doctype, filters={"parent": r.name, "parenttype": "Production Protocol", "parentfield": table},
				fields=fields, order_by="idx asc")
	return {"rows": rows}
