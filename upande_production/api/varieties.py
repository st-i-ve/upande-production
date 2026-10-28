"""Desk API for varieties (with their growth stages), activity rules, cycle stage actuals and the
protocol check. Same envelope as api.production: data or {"error": msg}."""

import frappe
from frappe import _
from frappe.utils import cint, getdate

from upande_production.api.envelope import as_dict, run
from upande_production.api.production import _need, _save
from upande_production.production.logic import analytics, stages

TEMPLATE_FIELDS = [
	"lifespan_years", "harvest_pattern", "harvest_interval_weeks", "plants_per_m2", "dry_matter_target_pct",
	"is_flowering", "weeks_to_first_flowering", "weeks_flowering_to_harvest", "weeks_to_reflower_after_harvest",
	"weeks_to_first_harvest", "harvest_window_weeks",
]
VARIETY_FIELDS = [
	"name", "variety_name", "crop", "product", "item", "enabled", "stage_anchor", "default_protocol",
	"days_to_first_harvest", "harvest_window_days", "expected_yield_per_ha", "expected_yield_per_plant",
	"plants_per_ha", "notes", *TEMPLATE_FIELDS,
]
RULE_FIELDS = [
	"name", "crop", "variety", "stage", "operation", "operation_category", "rule_type", "days",
	"other_operation", "other_category", "enforcement", "reason", "enabled",
]
STAGE_FIELDS = ["stage", "start_day", "length_days", "is_harvest", "description"]


@frappe.whitelist(methods=["POST"])
@run
def list_varieties(crop):
	"""{varieties: [{..., stages: [{stage, start_day, length_days, is_harvest, description}]}]} of the crop."""
	_need("Production Variety")
	rows = frappe.get_all("Production Variety", filters={"crop": crop}, fields=VARIETY_FIELDS,
		order_by="variety_name asc")
	for r in rows:
		r["stages"] = frappe.get_all("Production Variety Stage", filters={"parent": r.name, "parenttype": "Production Variety"},
			fields=STAGE_FIELDS, order_by="idx asc")
	return {"varieties": rows}


@frappe.whitelist(methods=["POST"])
@run
def save_variety(data):
	"""Insert, or update when data.name is set. `data.stages` replaces the stage rows."""
	data = dict(as_dict(data) or {})
	if "stages" in data:
		data["stages"] = [{k: s.get(k) for k in STAGE_FIELDS if k in s} for s in (data["stages"] or [])]
	for r in data.get("stages") or []:
		if not (r.get("stage") or "").strip():
			frappe.throw(_("Every stage needs a name."), frappe.ValidationError)
		if cint(r.get("length_days")) <= 0:
			frappe.throw(_("Stage {0} needs a length in days.").format(r["stage"]), frappe.ValidationError)
	return {"name": _save("Production Variety", data, protected=("variety_name",) if data.get("name") else ()).name}


@frappe.whitelist(methods=["POST"])
@run
def list_rules(crop):
	_need("Production Activity Rule")
	return {"rules": frappe.get_all("Production Activity Rule", filters={"crop": crop}, fields=RULE_FIELDS,
		order_by="rule_type asc, creation asc")}


@frappe.whitelist(methods=["POST"])
@run
def save_rule(data):
	return {"name": _save("Production Activity Rule", data).name}


@frappe.whitelist(methods=["POST"])
@run
def set_rule_enabled(name, enabled):
	"""Disable (or re-enable) a rule. Rules are never deleted: past work still points at them."""
	_need("Production Activity Rule", "write")
	frappe.db.set_value("Production Activity Rule", name, "enabled", 1 if cint(enabled) else 0)
	return {"name": name, "enabled": 1 if cint(enabled) else 0}


@frappe.whitelist(methods=["POST"])
@run
def set_stage_actual(cycle, stage, actual_date=None, note=None):
	"""Record the date `stage` really began on a cycle (empty date clears it). Later stages shift by the
	same delta. Returns the cycle's refreshed stage and bands."""
	_need("Production Crop Cycle", "write")
	doc = frappe.get_doc("Production Crop Cycle", cycle)
	if not doc.variety or stage not in [s["stage"] for s in stages.stages_for(doc.variety)]:
		frappe.throw(_("{0} is not a stage of this cycle's variety.").format(stage), frappe.ValidationError)
	rows = [r for r in doc.stage_actuals if r.stage == stage]
	if actual_date:
		getdate(actual_date)
		if rows:
			rows[0].actual_date, rows[0].note = actual_date, note or rows[0].note
		else:
			doc.append("stage_actuals", {"stage": stage, "actual_date": actual_date, "note": note})
	else:
		doc.stage_actuals = [r for r in doc.stage_actuals if r.stage != stage]
	doc.save()
	cur = stages.refresh_current_stage(doc)
	return {"name": doc.name, "current_stage": cur, "stage_bands": [
		{"stage": b["stage"], "start": str(b["start"]), "end": str(b["end"]), "is_harvest": int(b["is_harvest"]),
			"actual": bool(b["actual"])} for b in stages.timeline(doc.name)]}


@frappe.whitelist(methods=["POST"])
@run
def get_cycle_stages(cycle):
	"""A cycle's stage timeline with actuals: {variety, current_stage, stages: [{stage, start, end, is_harvest,
	actual, actual_date, note}]}."""
	_need("Production Crop Cycle")
	doc = frappe.get_doc("Production Crop Cycle", cycle)
	notes = {r.stage: r for r in doc.stage_actuals}
	out = []
	for b in stages.timeline(doc.name):
		a = notes.get(b["stage"])
		out.append({"stage": b["stage"], "start": str(b["start"]), "end": str(b["end"]),
			"is_harvest": int(b["is_harvest"]), "actual": bool(b["actual"]),
			"actual_date": str(a.actual_date) if a and a.actual_date else None, "note": a.note if a else None})
	return {"variety": doc.variety, "current_stage": doc.current_stage, "stages": out}


@frappe.whitelist(methods=["POST"])
@run
def protocol_check(crop, year, week, unit=None):
	"""Protocol steps due in the week per block with their plan status, rule status and breaches."""
	_need("Production Work Plan")
	return analytics.protocol_check(crop, int(year), int(week), unit or None)
