import frappe
from frappe import _
from frappe.utils import add_days, getdate

from upande_production.production.logic import rules
from upande_production.production.logic.cycles import crop_uses_cycles
from upande_production.production.logic import schedule
from upande_production.production.logic.units import unit_filter
from upande_production.production.logic.weeks import iso_week_bounds


def get_or_create_plan(crop, farm, year, week):
	filters = {"crop": crop, "plan_year": int(year), "plan_week": int(week)}
	filters["farm"] = farm if farm else ("in", ["", None])
	name = frappe.db.get_value("Production Work Plan", filters)
	if name:
		return frappe.get_doc("Production Work Plan", name)
	doc = frappe.get_doc({
		"doctype": "Production Work Plan", "crop": crop, "farm": farm or None,
		"plan_year": int(year), "plan_week": int(week),
	})
	doc.insert()
	return doc


def generate_week(plan_name: str) -> int:
	return generate_week_detail(plan_name)["created"]


def generate_week_detail(plan_name: str) -> dict:
	"""Generate the week's tasks from protocols. Steps an activity rule blocks are skipped and listed in
	`skipped` (and noted on the plan); steps that only warn are planned with rule_status Warn."""
	plan = frappe.get_doc("Production Work Plan", plan_name)
	start, end = iso_week_bounds(plan.plan_year, plan.plan_week)
	existing = {t.protocol_ref for t in plan.tasks if t.protocol_ref}
	count = 0
	skipped = []
	if not crop_uses_cycles(plan.crop):
		return {"created": 0, "skipped": skipped}
	cycles = frappe.get_all(
		"Production Crop Cycle",
		filters=unit_filter({"status": ("in", ["Active", "Harvesting"]), "crop": plan.crop, "protocol": ("is", "set")}),
		fields=["name", "unit", "start_date", "protocol", "variety", "cycle_no", "expected_harvest_start"],
	)
	with rules.call_cache():
		for cy in cycles:
			count = _generate_cycle(plan, cy, start, end, existing, skipped, count)
	if count:
		plan.save()
	_note_skipped(plan, skipped)
	return {"created": count, "skipped": skipped}


def _generate_cycle(plan, cy, start, end, existing, skipped, count) -> int:
	if plan.farm and frappe.db.get_value("Production Unit", cy.unit, "farm") != plan.farm:
		return count
	# Cycles keep the version they were pinned to (Active or since Superseded); drafts never plan.
	if frappe.db.get_value("Production Protocol", cy.protocol, "version_status") not in ("Active", "Superseded"):
		return count
	proto = frappe.get_doc("Production Protocol", cy.protocol)
	legacy = schedule.legacy_tasks(plan.tasks, cy.name, proto)
	for item in schedule.due_for_cycle(cy, proto, start, end):
		ref, due, operation = item["ref"], item["due_date"], item["operation"]
		if ref in existing or schedule.legacy_match(legacy, operation, due):
			continue
		op = frappe.db.get_value("Field Activity", operation, ["work_uom", "default_rate"], as_dict=True)
		breaches = rules.check(cycle=cy.name, unit=cy.unit, operation=operation, on_date=due)
		flag = rules.worst(breaches)
		if flag == "Block":
			skipped.append({
				"protocol_ref": ref, "unit": cy.unit, "cycle": cy.name, "operation": operation,
				"due_date": getdate(due), "message": " ".join(b["message"] for b in breaches),
			})
			continue
		plan.append("tasks", {
			"unit": cy.unit, "cycle": cy.name, "operation": operation,
			"planned_qty": item["planned_qty"], "uom": op.work_uom, "rate": op.default_rate,
			"due_date": due, "status": "Open", "protocol_ref": ref, "note": item["note"],
			"rule_status": flag, "rule_notes": "\n".join(b["message"] for b in breaches) or None,
		})
		existing.add(ref)
		count += 1
	return count


def _note_skipped(plan, skipped):
	"""Leave a comment on the plan for each step an activity rule kept out (once per step and message)."""
	for s in skipped:
		text = _("Not planned: {0} on {1} ({2}). {3}").format(
			frappe.db.get_value("Field Activity", s["operation"], "operation_name") or s["operation"],
			s["due_date"], s["unit"], s["message"])
		if not frappe.db.exists("Comment", {"reference_doctype": "Production Work Plan", "reference_name": plan.name,
			"comment_type": "Info", "content": text}):
			plan.add_comment("Info", text)
