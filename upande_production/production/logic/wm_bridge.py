"""Production drives Work Management ("jigsaw" mode).

When the Work Management app (WM) is installed and Labour mode is Automatic, production stays the screen people
use and WM's records mirror it, so WM's approvals, payroll check, payment runs and Additional Salary run on them:

    plan task      -> Work Management Planner   (wm_planner on the task row)
    first tick-off -> Work Management Assigner  (wm_assigner on the task row; crew added as it turns up)
    ticked-off work-> Work Management Actuals   (wm_actuals on each Casual Labour Work; one row per person-day)
    WM decisions   -> back onto Casual Labour Work: CONFIRMED submits it (Approved), Rejected sends it back,
                      a paid run sets paid / paid_on / payroll_reference.

Every write into WM goes through WM's own screen actions (wm_planner / wm_assigner / wm_actuals), called
in-process with the arguments the screens send. Those actions are where WM keeps its rules (master-plan budget
cap, rate periods, crew clashes, one worker one day one task, attendance gates, amount = quantity x rate with
the wage snap, target cap and completion gate, who may submit), so going around them would mean a second,
drifting copy of each rule. Their refusals come back as {"error": ...} and are raised here as WMError.

WM moves records between approval steps with frappe.db.set_value, which fires no document events, so the way
back is a reconcile (reconcile()) that reads WM's state; it runs before the commit of any request that wrote
to WM's screens, from WM document events (desk workflow, Salary Slip, Additional Salary, payment cancel) and
on a schedule as a safety net.

Nothing here imports work_management at module load: the hooks are harmless when WM is not installed.
"""

import math

import frappe
from frappe import _
from frappe.utils import cint, flt, today

from upande_production.production.logic import labour, rates
from upande_production.production.logic.weeks import iso_of, iso_week_bounds

PLANNER = "Work Management Planner"
ASSIGNER = "Work Management Assigner"
ACTUALS = "Work Management Actuals"
PAYMENT = "Work Management Payment"
CLW = "Casual Labour Work"
TAG = "Work Management: "

# states a planner can still be edited through WM's submit action
PLANNER_EDITABLE = ("Draft", "Rejected", "Pending Approval")
ASSIGNER_PENDING = ("Pending Farm Manager", "Pending HR Head", "Pending GM")
ASSIGNER_LIVE = ("Draft", "Rejected", *ASSIGNER_PENDING, "Assigned")

ENDPOINTS = {
	"planner": "work_management.api.planner.wm_planner",
	"assigner": "work_management.api.assigner.wm_assigner",
	"actuals": "work_management.api.actuals.wm_actuals",
	"payment": "work_management.api.payment.wm_payment",
}
# Requests to these WM endpoints may move records along WM's chain without document events.
WATCHED_COMMANDS = {
	"wm_actuals", ENDPOINTS["actuals"], "wm_payment", ENDPOINTS["payment"], "wm_assigner", ENDPOINTS["assigner"],
}
READ_ONLY_PREFIXES = ("hist_", "act_assigned", "act_detail", "act_my", "act_pending", "act_rejected",
	"act_closed_list", "act_close_pending", "act_close_roles", "pay_my", "pay_roles", "pay_pending", "pay_audit",
	"pay_insights", "pay_worker_history", "pay_worker_detail", "pay_workers", "pay_confirmed", "pay_issues",
	"pay_discrepancies", "pay_absent_conflicts", "chk_list", "chk_detail", "chk_issues", "chk_dup")


class WMError(frappe.ValidationError):
	"""Work Management refused, or is not set up for, what production asked."""


def active() -> bool:
	return labour.wm_active()


def terminal(doctype) -> str:
	"""The state that ends a WM chain (Approved / Assigned / CONFIRMED / Paid)."""
	fallback = {PLANNER: "Approved", ASSIGNER: "Assigned", ACTUALS: "CONFIRMED", PAYMENT: "Paid"}[doctype]
	try:
		from work_management.approvals import CHAIN_ENDS

		return CHAIN_ENDS[doctype]["terminal"][0]
	except Exception:
		return fallback


# -- calling WM's own actions ------------------------------------------------------------------------------


def call(screen, action, **params) -> frappe._dict:
	"""Run one WM screen action in-process, as the screen would send it. WM's actions read frappe.form_dict
	and one of them leaves frappe.flags.ignore_permissions on; both are put back afterwards."""
	fn = frappe.get_attr(ENDPOINTS[screen])
	saved_form, saved_ip = frappe.local.form_dict, frappe.flags.ignore_permissions
	frappe.local.form_dict = frappe._dict(
		{"action": action, **{k: v for k, v in params.items() if v is not None and v != ""}})
	try:
		out = fn() or {}
	finally:
		frappe.local.form_dict = saved_form
		frappe.flags.ignore_permissions = saved_ip
	return frappe._dict(out)


def _refused(out, what) -> None:
	"""Raise WM's own words when an action refused."""
	if out.get("error"):
		raise WMError(TAG + str(out.error))
	if out.get("needs_att_override"):
		who = "; ".join(
			"{0}: {1}".format(c.get("name") or c.get("employee"), ", ".join(c.get("reasons") or []))
			for c in (out.get("att_conflicts") or [])[:8])
		raise WMError(TAG + _("{0} needs an attendance override for {1}. Give a reason to record it anyway.").format(
			what, who))


def stage_role(key):
	try:
		from work_management.api.config import get_config

		return next((r.get("role") for r in get_config()["stage_rows"] if r["key"] == key), None)
	except Exception:
		return None


def may(key) -> bool:
	"""Whether this user may take a WM submit step (its configured role, or System Manager)."""
	roles = frappe.get_roles()
	return "System Manager" in roles or stage_role(key) in roles


# -- mapping ------------------------------------------------------------------------------------------------


def warehouse_for(unit) -> str:
	wh = frappe.db.get_value("Production Unit", unit, "warehouse")
	if not wh:
		raise WMError(TAG + _("Production Unit {0} has no warehouse. Work Management plans against a block "
			"(warehouse): set the unit's warehouse first.").format(unit))
	return wh


def farm_for(plan_farm=None, unit=None) -> str:
	farm = plan_farm or (unit and frappe.db.get_value("Production Unit", unit, "farm"))
	if not farm:
		raise WMError(TAG + _("No farm for {0}: set the plan's or the unit's farm.").format(unit or _("this work")))
	return farm


def farm_projects() -> dict:
	"""{farm: project} from the farms table on Work Management Settings."""
	if not frappe.db.exists("DocType", "WM Farm"):
		return {}
	return {r.farm: r.project for r in frappe.get_all("WM Farm",
		filters={"parenttype": "Work Management Settings"}, fields=["farm", "project"]) if r.farm and r.project}


def project_for(farm) -> str:
	project = farm_projects().get(farm)
	if not project:
		raise WMError(TAG + _("Farm {0} has no project in Work Management Settings (Farms table). Add one so its "
			"activities can be created.").format(farm))
	return project


def task_terms(operation, on_date=None) -> dict:
	"""What a WM Task should carry for this operation: our rate for the date, the period's (else the
	operation's) daily target, and the work UOM."""
	on_date = on_date or today()
	op = frappe.db.get_value("Field Operation", operation, ["work_uom", "daily_target"], as_dict=True) or {}
	rate, _source = rates.rate_on(operation, on_date)
	period = rates.period_on(operation, on_date)
	target = flt(period.daily_target) if period and flt(period.daily_target) else flt(op.get("daily_target"))
	return {"custom_rate": rate, "custom_daily_target": target, "custom_uom": op.get("work_uom")}


def task_for(operation, farm, on_date=None) -> str:
	"""The WM activity (ERPNext Task) for an operation: Field Operation.wm_task, else a Task of that subject
	under the farm's WM project, else a new one. While WM keeps no rate period of its own for the Task, its
	rate fields follow ours (written directly, as WM's own rate sync does, so no rate period is invented)."""
	op = frappe.db.get_value("Field Operation", operation, ["operation_name", "crop", "wm_task"], as_dict=True)
	if not op:
		raise WMError(TAG + _("No such operation {0}.").format(operation))
	terms = task_terms(operation, on_date)
	task = op.wm_task if op.wm_task and frappe.db.exists("Task", op.wm_task) else None
	if not task:
		project = project_for(farm)
		subject = op.operation_name
		task = frappe.db.get_value("Task", {"project": project, "subject": subject})
		if task and frappe.db.exists("Field Operation", {"wm_task": task, "name": ("!=", operation)}):
			# one activity per operation: another crop's operation of the same name already has this one
			subject = f"{op.operation_name} ({op.crop})"
			task = frappe.db.get_value("Task", {"project": project, "subject": subject})
		if not task:
			doc = frappe.get_doc({"doctype": "Task", "subject": subject, "project": project, **terms})
			doc.flags.ignore_permissions = True
			prev = frappe.flags.get("wm_rate_sync")
			frappe.flags.wm_rate_sync = True  # WM's own flag: no rate period starting today for a new Task
			try:
				doc.insert()
			finally:
				frappe.flags.wm_rate_sync = prev
			task = doc.name
		frappe.db.set_value("Field Operation", operation, "wm_task", task, update_modified=False)
	wm_rates = frappe.db.exists("DocType", "Work Task Rate") and frappe.db.exists("Work Task Rate", {"task": task})
	if not wm_rates:
		cur = frappe.db.get_value("Task", task, list(terms), as_dict=True)
		if any(_differs(cur.get(k), v) for k, v in terms.items()):
			frappe.db.set_value("Task", task, terms, update_modified=False)
	return task


def _differs(a, b) -> bool:
	if isinstance(b, (int, float)):
		return abs(flt(a) - flt(b)) > 1e-6
	return (a or None) != (b or None)


# -- plan task -> planner -----------------------------------------------------------------------------------


def _set_row(row, **values):
	"""Write on a Work Plan Task row without saving its plan (we are inside its on_update)."""
	for k, v in values.items():
		row.set(k, v)
	frappe.db.set_value("Work Plan Task", row.name, values, update_modified=False)


def _with_note(notes, note):
	kept = [ln for ln in (notes or "").split("\n") if ln and not ln.startswith(TAG)]
	if note:
		kept.append(note if note.startswith(TAG) else TAG + note)
	return "\n".join(kept) or None


def submit_planner(farm, block, task, qty, start, end, name=None) -> tuple:
	"""WM's planner submit (new, or an edit of a planner it still allows editing). Returns (name, note)."""
	submit_now = may("planner_submit")
	out = call("planner", "submit", farm=farm, block=block, task=task, quantity=qty,
		from_date=str(start), to_date=str(end), plan=name, submit_now=1 if submit_now else None)
	_refused(out, _("The planner"))
	_people_for_due_day(out.name, qty)
	note = None if submit_now else _("planner {0} is a draft: somebody holding {1} must submit it for "
		"approval in Work Management.").format(out.name, stage_role("planner_submit"))
	return out.name, note


def _people_for_due_day(planner, qty):
	"""WM sizes a plan's crew as if its quantity were spread over every day of the week; a production task is
	planned for its due day, so its crew is quantity / daily target. Only ever raised, never lowered, and only
	while the planner is still a request (WM's assignment screen caps the crew at this figure)."""
	p = frappe.db.get_value(PLANNER, planner, ["daily_target", "people_per_day", "workflow_state"], as_dict=True)
	if not p or p.workflow_state not in PLANNER_EDITABLE or flt(p.daily_target) <= 0:
		return
	need = math.ceil(flt(qty) / flt(p.daily_target) - 1e-9)
	if need > cint(p.people_per_day):
		frappe.db.set_value(PLANNER, planner, "people_per_day", need, update_modified=False)


def upsert_planner(plan, row) -> tuple:
	"""Create or update the planner mirroring a plan task. Returns (planner, note)."""
	farm = farm_for(plan.farm, row.unit)
	block = warehouse_for(row.unit)
	start, end = iso_week_bounds(plan.plan_year, plan.plan_week)
	task = task_for(row.operation, farm, start)
	qty = flt(row.planned_qty)
	cur = row.wm_planner and frappe.db.get_value(PLANNER, row.wm_planner,
		["workflow_state", "quantity", "task", "block_section", "farm"], as_dict=True)
	if cur:
		same = flt(cur.quantity) == qty and cur.task == task and cur.block_section == block and cur.farm == farm
		if cur.workflow_state not in PLANNER_EDITABLE:
			if same:
				return row.wm_planner, None
			return row.wm_planner, _("planner {0} is {1} for {2}; this task now asks for {3}. Revise it in "
				"Work Management.").format(row.wm_planner, cur.workflow_state, flt(cur.quantity), qty)
		if same and cur.workflow_state != "Rejected":
			return row.wm_planner, None
	return submit_planner(farm, block, task, qty, start, end, row.wm_planner if cur else None)


def sync_plan_row(plan, row) -> str | None:
	"""Mirror one plan task. WM's refusals become a note on the row, never a failed plan save."""
	if flt(row.planned_qty) <= 0 or not row.unit or not row.operation:
		return None
	sp = "wm_" + frappe.generate_hash(length=8)
	frappe.db.savepoint(sp)
	try:
		name, note = upsert_planner(plan, row)
	except Exception as e:
		frappe.db.rollback(save_point=sp)
		frappe.clear_last_message()
		if not isinstance(e, frappe.ValidationError):
			frappe.log_error(title="upande_production: Work Management planner")
		name, note = row.wm_planner, str(e) or e.__class__.__name__
	_set_row(row, wm_planner=name, rule_notes=_with_note(row.rule_notes, note))
	return note


def drop_planner(plan, name):
	"""A task left the plan: delete its planner while WM still treats it as a request; otherwise say so."""
	state = frappe.db.get_value(PLANNER, name, "workflow_state")
	if not state:
		return
	if state in PLANNER_EDITABLE and not frappe.db.exists(ASSIGNER, {"planner_request": name}):
		frappe.delete_doc(PLANNER, name, ignore_permissions=True, force=True)
		return
	plan.add_comment("Info", _("A task was removed from this plan, but Work Management planner {0} is {1}. Close "
		"or cancel it in Work Management.").format(name, state))


def on_plan_update(doc, method=None):
	"""doc_events: Production Work Plan.on_update. Each task with a planned quantity gets or updates its
	planner; tasks removed from the plan drop theirs. Rows whose quantity, unit and operation did not change
	and already have a planner are left alone, so a tick-off's plan save costs nothing here."""
	if not active() or doc.flags.get("wm_skip"):
		return
	before = doc.get_doc_before_save()
	old = {r.name: r for r in (before.tasks if before else [])}
	for row in doc.tasks:
		prev = old.get(row.name)
		unchanged = prev and all(prev.get(k) == row.get(k) for k in ("unit", "operation")) \
			and flt(prev.planned_qty) == flt(row.planned_qty)
		# unchanged rows are left alone: mirrored ones, and ones WM already refused (the note says why; a
		# tick-off or an edit of the row tries again)
		if unchanged and (row.wm_planner or TAG in (row.rule_notes or "")):
			continue
		sync_plan_row(doc, row)
	current = {r.name for r in doc.tasks}
	for name, prev in old.items():
		if name not in current and prev.wm_planner:
			drop_planner(doc, prev.wm_planner)


def on_plan_trash(doc, method=None):
	if not labour.wm_installed():
		return
	for row in doc.tasks:
		if row.wm_planner:
			drop_planner(doc, row.wm_planner)


# -- tick-off -> assigner + actuals -------------------------------------------------------------------------


def _wait_for(planner):
	state = frappe.db.get_value(PLANNER, planner, "workflow_state")
	if state == "Rejected":
		raise WMError(TAG + _("Planner {0} was rejected in Work Management. Change the task's quantity (or the "
			"planner there) to send it again.").format(planner))
	if state != terminal(PLANNER):
		raise WMError(TAG + _("Waiting for Work Management approval of planner {0} ({1}).").format(planner, state))


def _commit_and_refuse(msg):
	"""A planner raised for this work must outlive the refusal, so it can be approved."""
	frappe.db.commit()
	raise WMError(msg)


def ensure_assignment(planner, employees, override_reason=None) -> str:
	"""The live assignment on this planner, with everybody in `employees` on its crew: WM's a_submit for a new
	or not-yet-approved one, a_add_crew once it is Assigned."""
	employees = list(dict.fromkeys(e for e in employees if e))
	override = 1 if override_reason else None
	asg = frappe.get_all(ASSIGNER, filters={"planner_request": planner, "workflow_state": ("in", ASSIGNER_LIVE)},
		fields=["name", "workflow_state"], order_by="creation desc", limit=1)
	if not asg:
		out = call("assigner", "a_submit", planner=planner, employees=",".join(employees),
			submit_now=1 if may("assigner_submit") else None, att_override=override)
		_refused(out, _("The crew"))
		return out.name
	asg = asg[0]
	roster = frappe.get_all("Work Assignment Employee", filters={"parent": asg.name},
		fields=["employee", "status"], order_by="idx")
	missing = [e for e in employees if e not in {r.employee for r in roster}]
	if not missing:
		return asg.name
	if asg.workflow_state == terminal(ASSIGNER):
		out = call("assigner", "a_add_crew", assignment=asg.name, employees=",".join(missing))
	else:
		crew = [r.employee for r in roster if (r.status or "Active") == "Active"] + missing
		out = call("assigner", "a_submit", planner=planner, assignment=asg.name, employees=",".join(crew),
			submit_now=1 if asg.workflow_state in ("Draft", "Rejected") and may("assigner_submit") else None,
			att_override=override)
	_refused(out, _("Adding to the crew"))
	return asg.name


def before_task_work(plan, row, employees, override_reason=None) -> str:
	"""Before a plan task's tick-off is recorded: its planner must be approved in WM (raised now if it never
	was), and everybody on the tick-off must be on its assignment. Returns the assignment."""
	if not row.wm_planner or not frappe.db.exists(PLANNER, row.wm_planner):
		row.wm_planner = None
		note = sync_plan_row(plan, row)
		if not row.wm_planner:
			raise WMError(note or TAG + _("No planner for this task."))
		_commit_and_refuse(TAG + _("Raised planner {0} for this task. It is waiting for approval in Work "
			"Management; record the work once it is approved.").format(row.wm_planner))
	_wait_for(row.wm_planner)
	asg = ensure_assignment(row.wm_planner, employees, override_reason)
	if row.wm_assigner != asg:
		_set_row(row, wm_assigner=asg)
	return asg


def before_unplanned_work(unit, operation, employees, work_date, qty, override_reason=None) -> str:
	"""Unplanned work rides on a planner for its week, unit and activity: an existing one, else one raised now
	for the quantity entered (which then waits for approval). Returns the assignment."""
	farm = farm_for(None, unit)
	block = warehouse_for(unit)
	start, end = iso_week_bounds(*iso_of(work_date))
	task = task_for(operation, farm, start)
	found = frappe.get_all(PLANNER, filters={"farm": farm, "task": task, "block_section": block,
		"from_date": start, "to_date": end, "workflow_state": ("!=", "Rejected")},
		pluck="name", order_by="creation desc", limit=1)
	if not found:
		name, note = submit_planner(farm, block, task, qty, start, end)
		_commit_and_refuse(TAG + _("Raised planner {0} for this unplanned work. It is waiting for approval in Work "
			"Management; record the work again once it is approved.").format(name)
			+ (" " + note if note else ""))
	_wait_for(found[0])
	return ensure_assignment(found[0], employees, override_reason)


def _payload(names) -> str:
	"""WM's actuals grid: employee~date~qty per person-day (a person-day keyed twice is summed)."""
	cells = {}
	for r in frappe.get_all(CLW, filters={"name": ("in", list(names))}, fields=["employee", "work_date", "qty"]):
		key = (r.employee, str(r.work_date))
		cells[key] = cells.get(key, 0) + flt(r.qty)
	return "|".join(f"{e}~{d}~{q:g}" for (e, d), q in sorted(cells.items()))


def push_actuals(assignment, names=(), submit=False, override_reason=None) -> dict:
	"""Write the assignment's actuals through WM's act_submit: the new rows plus every pending row already on
	its open (Draft / Rejected) actuals, since WM rewrites the whole grid. Stamps wm_actuals on each row."""
	names = set(names or [])
	open_ = frappe.get_all(ACTUALS, filters={"assignment": assignment, "workflow_state": ("in", ["Draft", "Rejected"])},
		fields=["name", "workflow_state", "docstatus"], limit=1)
	if open_:
		names |= set(frappe.get_all(CLW, filters={"wm_actuals": open_[0].name, "docstatus": 0,
			"approval_status": "Pending"}, pluck="name"))
	if not names:
		return {}
	if open_ and open_[0].workflow_state == "Rejected" and open_[0].docstatus == 0:
		# act_submit resumes a Rejected record by saving it as Draft, but WM's generated workflow has no
		# Rejected -> Draft transition, so that save is refused. Re-open it the way WM moves its states.
		frappe.db.set_value(ACTUALS, open_[0].name, "workflow_state", "Draft", update_modified=False)
		frappe.get_doc(ACTUALS, open_[0].name).add_comment("Comment",
			_("Re-opened from Production by {0} to resubmit the returned work.").format(frappe.session.user))
	reason = (override_reason or "").strip() or None
	out = call("actuals", "act_submit", assignment=assignment, rows=_payload(names),
		submit_now=1 if submit else None, att_override=1 if reason else None, qty_reason=reason)
	_refused(out, _("This work"))
	for n in names:
		frappe.db.set_value(CLW, n, "wm_actuals", out.name, update_modified=False)
	notes = [out.get(k) for k in ("submit_blocked", "released_warning", "joined_warning") if out.get(k)]
	state = out.get("workflow_state")
	msg = _("Recorded on Work Management actuals {0} ({1}); it is approved there.").format(out.name, state)
	return {"actuals": out.name, "workflow_state": state, "message": " ".join([msg, *notes])}


def repush(names, submit=True, override_reason=None) -> list:
	"""Sent-back work resubmitted in production goes back onto its WM actuals (and on for approval)."""
	out = []
	by_actuals = {}
	for r in frappe.get_all(CLW, filters={"name": ("in", list(names)), "wm_actuals": ("is", "set")},
			fields=["name", "wm_actuals"]):
		by_actuals.setdefault(r.wm_actuals, []).append(r.name)
	for actuals, rows in by_actuals.items():
		asg = frappe.db.get_value(ACTUALS, actuals, "assignment")
		if asg:
			out.append(push_actuals(asg, rows, submit=submit, override_reason=override_reason))
	return out


def wm_row_of(name) -> str | None:
	"""The WM actuals a work row is decided on, while that record still exists."""
	actuals = frappe.db.get_value(CLW, name, "wm_actuals")
	return actuals if actuals and labour.wm_installed() and frappe.db.exists(ACTUALS, actuals) else None


# -- WM -> production ---------------------------------------------------------------------------------------


def _return_note(actuals) -> str:
	"""WM's reject carries no reason; say who returned it (the Workflow comment WM writes on a rejection)."""
	c = frappe.get_all("Comment", filters={"reference_doctype": ACTUALS, "reference_name": actuals,
		"comment_type": "Workflow", "content": "Rejected"}, fields=["owner"], order_by="creation desc", limit=1)
	who = frappe.utils.get_fullname(c[0].owner) if c else None
	return (_("Returned in Work Management ({0}) by {1}.").format(actuals, who) if who
		else _("Returned in Work Management ({0}).").format(actuals))


def _refresh_tasks(rows):
	from upande_production.production.logic.work import refresh_task_done

	for plan, task in dict.fromkeys((r.plan, r.plan_task) for r in rows if r.plan and r.plan_task):
		refresh_task_done(plan, task)


def _wm_rows(actuals) -> dict:
	return {(r.employee, str(r.work_date)): r for r in frappe.get_all("Work Actuals Employee",
		filters={"parent": actuals, "parenttype": ACTUALS},
		fields=["employee", "work_date", "actual_quantity", "amount", "count_in_payroll", "paid", "payment_ref"])}


def _approve(doc, wm, wrow):
	"""Submit (approve) a draft work row WM confirmed, at what WM will pay for it."""
	if wrow:
		day_qty = flt(frappe.db.sql("""select sum(qty) from `tabCasual Labour Work` where wm_actuals=%s and
			employee=%s and work_date=%s and docstatus<2""", (wm.name, doc.employee, doc.work_date))[0][0]) or flt(doc.qty)
		share = flt(wrow.amount) * flt(doc.qty) / day_qty if day_qty else 0
		rate = round(share / flt(doc.qty), 6) if flt(doc.qty) else 0
		if abs(rate - flt(doc.rate)) > 1e-6:
			doc.rate = rate
			doc.rate_source = _("Work Management {0}").format(wm.name) if cint(wrow.count_in_payroll) else \
				_("Work Management {0}: not paid as task work").format(wm.name)
	doc.flags.ignore_permissions = True
	doc.flags.wm_sync = True
	doc.submit()
	approver = wm.gm_approved_by or wm.hr_approved_by or wm.fm_approved_by
	if approver:
		doc.db_set({"reviewed_by": approver, "review_note": _("Approved in Work Management ({0}).").format(wm.name)},
			update_modified=False)


def sync_actuals(name) -> dict:
	"""Bring every work row on one WM actuals in line with it. Idempotent."""
	rows = frappe.get_all(CLW, filters={"wm_actuals": name, "docstatus": ("<", 2)},
		fields=["name", "docstatus", "approval_status", "employee", "work_date", "plan", "plan_task", "paid",
			"payroll_reference"])
	done = {"approved": [], "sent_back": [], "cancelled": [], "paid": [], "unpaid": [], "unlinked": []}
	if not rows:
		return done
	wm = frappe.db.get_value(ACTUALS, name, ["name", "workflow_state", "docstatus", "fm_approved_by",
		"hr_approved_by", "gm_approved_by"], as_dict=True)
	drafts = [r for r in rows if r.docstatus == 0]
	if not wm:  # deleted in WM: the drafts come back to production, unlinked
		for r in drafts:
			frappe.db.set_value(CLW, r.name, {"wm_actuals": None, "approval_status": "Sent Back",
				"review_note": _("Work Management actuals {0} was deleted.").format(name)}, update_modified=False)
			done["unlinked"].append(r.name)
		_refresh_tasks(drafts)
		return done
	wrows = _wm_rows(name)
	if wm.docstatus == 2:  # a confirmation reversed in WM
		for r in rows:
			doc = frappe.get_doc(CLW, r.name)
			if r.docstatus == 1 and r.paid != "Paid":
				doc.flags.ignore_permissions = True
				doc.cancel()
				doc.add_comment("Info", _("Cancelled: Work Management reversed {0}.").format(name))
				done["cancelled"].append(r.name)
			elif r.docstatus == 0 and r.approval_status == "Pending":
				doc.db_set({"approval_status": "Sent Back", "review_note": _return_note(name)}, update_modified=False)
				done["sent_back"].append(r.name)
		_refresh_tasks(rows)
		return done
	if wm.workflow_state == terminal(ACTUALS):
		for r in drafts:
			if r.approval_status == "Sent Back":
				continue
			_approve(frappe.get_doc(CLW, r.name), wm, wrows.get((r.employee, str(r.work_date))))
			done["approved"].append(r.name)
	elif wm.workflow_state == "Rejected":
		pending = [r for r in drafts if r.approval_status == "Pending"]
		note = _return_note(name) if pending else None
		for r in pending:
			frappe.db.set_value(CLW, r.name, {"approval_status": "Sent Back", "review_note": note,
				"reviewed_by": frappe.session.user, "reviewed_at": frappe.utils.now_datetime()}, update_modified=False)
			done["sent_back"].append(r.name)
		_refresh_tasks(pending)
	_sync_paid(name, wrows, done)
	return done


def _sync_paid(name, wrows, done):
	for r in frappe.get_all(CLW, filters={"wm_actuals": name, "docstatus": 1},
			fields=["name", "employee", "work_date", "paid", "payroll_reference"]):
		w = wrows.get((r.employee, str(r.work_date)))
		if w and cint(w.paid) and w.payment_ref:
			if r.paid != "Paid" or r.payroll_reference != w.payment_ref:
				pay = frappe.db.get_value(PAYMENT, w.payment_ref, ["accounts_approval_date", "payroll_date"],
					as_dict=True) or {}
				frappe.db.set_value(CLW, r.name, {"paid": "Paid", "payroll_reference": w.payment_ref,
					"paid_on": pay.get("accounts_approval_date") or pay.get("payroll_date") or today()},
					update_modified=False)
				done["paid"].append(r.name)
		elif r.paid == "Paid" and r.payroll_reference and frappe.db.exists(PAYMENT, r.payroll_reference):
			# paid by a WM run that payroll has since withdrawn (slip or Additional Salary cancelled)
			frappe.db.set_value(CLW, r.name, {"paid": "Unpaid", "paid_on": None, "payroll_reference": None},
				update_modified=False)
			done["unpaid"].append(r.name)


def open_actuals() -> list:
	"""WM actuals that still have production rows waiting on them (a decision, or pay)."""
	return [r[0] for r in frappe.db.sql("""select distinct wm_actuals from `tabCasual Labour Work`
		where ifnull(wm_actuals, '') != '' and docstatus < 2 and not (docstatus = 1 and paid = 'Paid')""")]


def reconcile(names=None, payments=None) -> dict:
	"""Sync the named WM actuals (default: every one production still waits on) and those whose rows a WM
	payment touched."""
	if not labour.wm_installed() or not frappe.db.exists("DocType", ACTUALS):
		return {}
	todo = set(names) if names is not None else set(open_actuals())
	for pay in payments or ():
		todo |= set(frappe.get_all(CLW, filters={"payroll_reference": pay, "wm_actuals": ("is", "set")},
			pluck="wm_actuals"))
		todo |= set(frappe.get_all("Work Actuals Employee", filters={"payment_ref": pay}, pluck="parent"))
	out = {}
	for name in sorted(todo):
		try:
			out[name] = sync_actuals(name)
		except Exception:
			frappe.log_error(title=f"upande_production: Work Management sync {name}")
	return out


# -- triggers -----------------------------------------------------------------------------------------------


def _queue() -> dict:
	q = frappe.flags.get("wm_bridge_queue")
	if q is None:
		q = frappe.flags.wm_bridge_queue = {"all": False, "names": set(), "payments": set()}
	return q


def defer(names=(), payments=(), everything=False):
	"""Reconcile just before this transaction commits, once, after every handler (WM's included) has run."""
	q = _queue()
	q["all"] = q["all"] or everything
	q["names"].update(n for n in names if n)
	q["payments"].update(p for p in payments if p)
	if flush not in frappe.db.before_commit._functions:
		frappe.db.before_commit.add(flush)


def flush():
	q = frappe.flags.get("wm_bridge_queue")
	frappe.flags.wm_bridge_queue = None
	if not q:
		return
	try:
		if q["all"]:
			reconcile(None, q["payments"])
			if q["names"]:
				reconcile(q["names"])
		else:
			reconcile(q["names"], q["payments"])
	except Exception:
		frappe.log_error(title="upande_production: Work Management sync")


def on_wm_actuals(doc, method=None):
	"""doc_events on Work Management Actuals (desk workflow, imports, our own pushes)."""
	if method == "on_trash":
		frappe.db.set_value(CLW, {"wm_actuals": doc.name, "docstatus": 0},
			{"wm_actuals": None, "approval_status": "Sent Back",
				"review_note": _("Work Management actuals {0} was deleted.").format(doc.name)}, update_modified=False)
		return
	defer([doc.name])


def on_wm_payment(doc, method=None):
	defer(payments=[doc.name])


def _slip_payments(doc) -> list:
	names = list({r.additional_salary for r in (doc.get("earnings") or []) + (doc.get("deductions") or [])
		if r.get("additional_salary")})
	if not names:
		return []
	return frappe.get_all("Additional Salary", filters={"name": ("in", names), "ref_doctype": PAYMENT},
		pluck="ref_docname")


def on_salary_slip(doc, method=None):
	"""Salary Slip submit/cancel: WM marks its runs Paid (or back) in its own handler, which runs after this
	one, so the sync waits for the commit."""
	if not labour.wm_installed():
		return
	payments = _slip_payments(doc)
	if payments:
		defer(payments=payments)


def on_additional_salary_cancel(doc, method=None):
	if labour.wm_installed() and doc.get("ref_doctype") == PAYMENT and doc.get("ref_docname"):
		defer(payments=[doc.ref_docname])


def watch_request():
	"""before_request: a write to WM's actuals / assigner / payment screens may move records along WM's
	chain with no document event, so reconcile before that request commits."""
	try:
		req = getattr(frappe.local, "request", None)
		if not req or req.method != "POST":
			return
		cmd = frappe.form_dict.get("cmd") or (req.path or "").rsplit("method/", 1)[-1]
		if cmd not in WATCHED_COMMANDS or not labour.wm_installed():
			return
		action = str(frappe.form_dict.get("action") or "")
		if not action or action.startswith(READ_ONLY_PREFIXES):
			return
		defer([frappe.form_dict.get("name")] if frappe.form_dict.get("name") else [], everything=True)
	except Exception:
		frappe.log_error(title="upande_production: Work Management request watch")


def scheduled_reconcile():
	if labour.wm_installed():
		reconcile()
		frappe.db.commit()


# -- status ---------------------------------------------------------------------------------------------------


def status() -> dict:
	"""What still needs mapping before production can drive WM."""
	units = frappe.get_all("Production Unit", filters={"is_group": 0, "status": ("!=", "Retired")},
		fields=["name", "unit_name", "farm", "warehouse"])
	projects = farm_projects() if labour.wm_installed() else {}
	farms = sorted({u.farm for u in units if u.farm})
	return {
		"wm_installed": labour.wm_installed(),
		"wm_active": active(),
		"farms_mapped": [{"farm": f, "project": p} for f, p in sorted(projects.items())],
		"farms_unmapped": [f for f in farms if f not in projects],
		"units_without_warehouse": [{"unit": u.name, "unit_name": u.unit_name, "farm": u.farm}
			for u in units if not u.warehouse],
		"operations_without_task": frappe.get_all("Field Operation", filters={"wm_task": ("is", "not set")},
			fields=["name", "operation_name", "crop"], order_by="operation_name"),
	}
