"""Awaiting tasks: an assistant manager's plan rows wait for a manager to forward them to the supervisors."""

import frappe
from frappe import _
from frappe.utils import now_datetime

from upande_production.production.logic import settings, teams

REAWAIT_FIELDS = ("unit", "cycle", "operation", "planned_qty", "rate", "uom")


def visible_filter() -> dict:
	"""Filter for task queries: supervisors do not see awaiting tasks while the step is on."""
	if settings.assistant_step_on() and not settings.is_manager() and not settings.is_assistant_manager():
		return {"awaiting_approval": 0}
	return {}


def mask_awaiting(rows):
	"""With the step off nothing awaits: whatever the rows say, report awaiting_approval 0 (desk and phone badges follow)."""
	if not settings.assistant_step_on():
		for r in rows:
			if "awaiting_approval" in r:
				r["awaiting_approval"] = 0
	return rows


def refuse_if_awaiting(row, status=None):
	"""A manager may still close an awaiting task off by marking it Skipped."""
	if status == "Skipped" and settings.is_manager():
		return
	if settings.assistant_step_on() and row.get("awaiting_approval"):
		frappe.throw(_("This task is waiting for a manager's approval."), frappe.ValidationError)


def forward(plan: str, tasks: list | None = None, confirm_other_team=0) -> dict:
	"""Managers forward all awaiting tasks of a plan (or the named ones): clear the flag, stamp who and when."""
	if not settings.is_manager():
		frappe.throw(_("Only a manager can forward tasks."), frappe.PermissionError)
	doc = frappe.get_doc("Production Work Plan", plan)
	doc.flags.approval_fields_ok = True
	wanted = set(tasks) if tasks else None
	out, hit = [], []
	for r in doc.tasks:
		if r.awaiting_approval and (wanted is None or r.name in wanted):
			hit.append(r)
	teams.require_confirm([r.assigned_by for r in hit], confirm_other_team)
	other = [r.name for r in hit if teams.other_team_manager(r.assigned_by)]
	for r in hit:
		r.awaiting_approval = 0
		r.forwarded_by = frappe.session.user
		r.forwarded_on = now_datetime()
		out.append(r.name)
	if out:
		doc.flags.wm_force_sync = set(out)  # a row that already has a planner would look unchanged otherwise
		doc.save()  # the plan save runs the Work Management plan-row sync for the newly released rows
	return {"forwarded": out, "other_team": other}


def annotate_teams(rows):
	"""Mark each task row (dicts) with the manager whose team it belongs to and whether that is someone else."""
	for r in rows:
		r["team_manager"] = teams.team_manager(r.get("assigned_by"))
		r["other_team"] = bool(teams.other_team_manager(r.get("assigned_by")))
	return rows


def awaiting_tasks(crop=None, all_teams=0) -> dict:
	"""Awaiting tasks a manager can forward: their team's and the ones with no team (all_teams: every one)."""
	if not settings.is_manager():
		frappe.throw(_("Only a manager can forward tasks."), frappe.PermissionError)
	filters = {"awaiting_approval": 1, "parenttype": "Production Work Plan"}
	rows = frappe.get_all("Work Plan Task", filters=filters, order_by="due_date asc, idx asc",
		fields=["name", "parent as plan", "unit", "operation", "operation_name", "planned_qty", "uom", "due_date",
			"assigned_by"])
	plans = {p.name: p for p in frappe.get_all("Production Work Plan",
		filters={"name": ("in", list({r.plan for r in rows}) or [""])}, fields=["name", "crop", "plan_year", "plan_week"])}
	narrow = teams.scoped(all_teams=frappe.utils.cint(all_teams))
	out = []
	for r in rows:
		p = plans.get(r.plan)
		if not p or (crop and p.crop != crop) or not settings.crop_allowed(p.crop):
			continue
		if narrow and not teams.is_mine(r.assigned_by):
			continue
		out.append({**r, "crop": p.crop, "plan_year": p.plan_year, "plan_week": p.plan_week})
	annotate_teams(out)
	return {"tasks": out, "count": len(out)}
