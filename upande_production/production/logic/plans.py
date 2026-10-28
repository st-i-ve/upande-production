import frappe
from frappe import _
from frappe.utils import add_days, getdate

from upande_production.production.logic.weeks import iso_week_bounds


def get_or_create_plan(crop, farm, year, week):
	filters = {"crop": crop, "plan_year": int(year), "plan_week": int(week)}
	filters["farm"] = farm if farm else ("in", ["", None])
	name = frappe.db.get_value("Production Plan", filters)
	if name:
		return frappe.get_doc("Production Plan", name)
	doc = frappe.get_doc({
		"doctype": "Production Plan", "crop": crop, "farm": farm or None,
		"plan_year": int(year), "plan_week": int(week),
	})
	doc.insert()
	return doc


def generate_week(plan_name: str) -> int:
	plan = frappe.get_doc("Production Plan", plan_name)
	start, end = iso_week_bounds(plan.plan_year, plan.plan_week)
	existing = {t.protocol_ref for t in plan.tasks if t.protocol_ref}
	count = 0
	cycles = frappe.get_all(
		"Production Crop Cycle",
		filters={"status": ("in", ["Active", "Harvesting"]), "crop": plan.crop, "protocol": ("is", "set")},
		fields=["name", "unit", "start_date", "protocol"],
	)
	for cy in cycles:
		if plan.farm and frappe.db.get_value("Production Unit", cy.unit, "farm") != plan.farm:
			continue
		proto = frappe.get_doc("Production Protocol", cy.protocol)
		for step in proto.steps:
			for k in range(int(step.repeat_count or 1)):
				due = add_days(getdate(cy.start_date), int(step.day_offset or 0) + k * int(step.repeat_every_days or 0))
				if not (start <= getdate(due) <= end):
					continue
				ref = f"{cy.name}:{step.name}:{k}"
				if ref in existing:
					continue
				op = frappe.db.get_value(
					"Production Operation", step.operation, ["work_uom", "default_rate"], as_dict=True
				)
				plan.append("tasks", {
					"unit": cy.unit, "cycle": cy.name, "operation": step.operation,
					"planned_qty": step.planned_qty, "uom": op.work_uom, "rate": op.default_rate,
					"due_date": due, "status": "Open", "protocol_ref": ref, "note": step.note,
				})
				existing.add(ref)
				count += 1
	if count:
		plan.save()
	return count
