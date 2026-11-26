"""Approval workflow for supervisor-keyed work (Casual Labour Work).

Supervisor keys work in as a draft (Pending). A manager approves it (submit, so it counts) or sends it
back with a note (Sent Back). The supervisor fixes and resubmits (back to Pending).
"""

import json

import frappe
from frappe import _
from frappe.utils import add_days, cint, now_datetime, today

from upande_production.production.logic import cycle_requests as _cycle_requests, labourers, wm_bridge, work
from upande_production.production.logic.units import retired_sql
from upande_production.production.logic.settings import (
	assistant_step_on, can_see_pay, get_stale_days, is_assistant_manager, is_manager, is_supervisor,
)

STATUSES = ("Pending", "Checked", "Approved", "Sent Back")
DEFAULT_HISTORY_DAYS = 60


def _names(names) -> list[str]:
	if isinstance(names, str):
		try:
			names = json.loads(names)
		except Exception:
			names = [n.strip() for n in names.split(",") if n.strip()]
	names = [n for n in (names or []) if n]
	if not names:
		frappe.throw(_("Select at least one entry."), frappe.ValidationError)
	return list(dict.fromkeys(names))


def _need_manager():
	if not is_manager():
		frappe.throw(_("Only a Production Manager can review work."), frappe.PermissionError)


def _docs(names, status):
	"""The named drafts, each in one of the allowed status (a name or a tuple of them)."""
	allowed = (status,) if isinstance(status, str) else tuple(status)
	docs = []
	for n in names:
		doc = frappe.get_doc("Casual Labour Work", n)
		if doc.docstatus != 0 or doc.approval_status not in allowed:
			frappe.throw(
				_("{0} is {1}, not {2}.").format(
					n, "approved" if doc.docstatus == 1 else doc.approval_status, _(" or ").join(allowed)
				),
				frappe.ValidationError,
			)
		docs.append(doc)
	return docs


def _decided_in_wm(docs):
	"""Work mirrored onto Work Management actuals is approved or returned there, not here."""
	held = {d.name: wm_bridge.wm_row_of(d.name) for d in docs}
	held = {n: a for n, a in held.items() if a}
	if held:
		frappe.throw(
			_("{0} is decided in Work Management (actuals {1}). Approve or return it there.").format(
				", ".join(list(held)[:5]), ", ".join(sorted(set(held.values())))),
			frappe.ValidationError,
		)


def _refresh(docs):
	for plan, task in dict.fromkeys((d.plan, d.plan_task) for d in docs):
		work.refresh_task_done(plan, task)


def _assigner(plan_task):
	return frappe.db.get_value("Work Plan Task", plan_task, "assigned_by") if plan_task else None


def needs_check(doc) -> bool:
	"""The step is on and the entry's task was assigned by an assistant manager (who is still one)."""
	if not assistant_step_on() or not doc.plan_task or doc.get("wm_actuals"):
		return False  # the two-step check is built-in labour only; Work Management has its own chain
	by = _assigner(doc.plan_task)
	return bool(by) and is_assistant_manager(by)


def check(names) -> dict:
	"""The assistant manager who assigned the task vouches for the entries; a manager approves them next."""
	docs = _docs(_names(names), "Pending")
	if not assistant_step_on():
		frappe.throw(_("The assistant manager step is off; work no longer needs a check."), frappe.ValidationError)
	_decided_in_wm(docs)
	for d in docs:
		if not d.plan_task or _assigner(d.plan_task) != frappe.session.user or not is_assistant_manager():
			frappe.throw(_("Only the assistant manager who assigned the task can check {0}.").format(d.name),
				frappe.PermissionError)
	for d in docs:
		d.db_set({"approval_status": "Checked", "checked_by": frappe.session.user,
			"checked_at": now_datetime()})
	_refresh(docs)
	return {"checked": [d.name for d in docs]}


def approve(names, unchecked_ok=0) -> dict:
	_need_manager()
	docs = _docs(_names(names), ("Pending", "Checked"))
	_decided_in_wm(docs)
	if not cint(unchecked_ok):
		open_ = [d.name for d in docs if d.approval_status == "Pending" and needs_check(d)]
		if open_:
			frappe.throw(_("{0} still needs the assistant manager's check. Approve as not checked to override.")
				.format(", ".join(open_[:5])), frappe.ValidationError)
	for d in docs:
		d.submit()  # before_submit stamps Approved/reviewed_by/at; on_submit recounts the task
	return {"approved": [d.name for d in docs]}


def send_back(names, note) -> dict:
	manager = is_manager()
	if not manager and not is_assistant_manager():
		frappe.throw(_("Only a Production Manager can review work."), frappe.PermissionError)
	note = (note or "").strip()
	if not note:
		frappe.throw(_("A note is required when sending work back."), frappe.ValidationError)
	docs = _docs(_names(names), ("Pending", "Checked") if manager else "Pending")
	if not manager:
		mine = [d.name for d in docs if _assigner(d.plan_task) != frappe.session.user]
		if mine:
			frappe.throw(_("You can send back only work on tasks you assigned: {0}.").format(", ".join(mine[:5])),
				frappe.PermissionError)
	_decided_in_wm(docs)
	for d in docs:
		d.approval_status = "Sent Back"
		d.review_note = note
		d.reviewed_by = frappe.session.user
		d.reviewed_at = now_datetime()
		d.save()
	_refresh(docs)
	return {"sent_back": [d.name for d in docs]}


def resubmit(names, entries=None, override_reason=None) -> dict:
	if not is_supervisor():
		frappe.throw(_("You do not have permission to resubmit work."), frappe.PermissionError)
	docs = _docs(_names(names), "Sent Back")
	edits = {}
	if isinstance(entries, str):
		entries = json.loads(entries or "[]")
	for e in entries or []:
		if e.get("name"):
			edits[e["name"]] = e
	unknown = set(edits) - {d.name for d in docs}
	if unknown:
		frappe.throw(_("Cannot edit {0}: not a sent-back entry in this request.").format(", ".join(unknown)),
			frappe.ValidationError)
	for d in docs:
		e = edits.get(d.name) or {}
		if "qty" in e:
			if float(e["qty"] or 0) <= 0:
				frappe.throw(_("Quantity must be greater than zero"), frappe.ValidationError)
			d.qty = float(e["qty"])
		if e.get("employee"):
			d.employee = e["employee"]
		d.approval_status = "Pending"
		d.checked_by = None
		d.checked_at = None
		d.save()
	wm = []
	if wm_bridge.active():
		reason = override_reason or next((d.override_reason for d in docs if d.override_reason), None)
		wm = wm_bridge.repush([d.name for d in docs if d.wm_actuals], override_reason=reason)
	_refresh(docs)
	return {"resubmitted": [d.name for d in docs], "wm": wm or None}


# -- listing -----------------------------------------------------------------


def _age_days(created) -> int:
	return max((now_datetime() - frappe.utils.get_datetime(created)).days, 0)


def _rule_status(rows) -> str:
	flags = {r.rule_status for r in rows}
	return "Block" if "Block" in flags else "Warn" if "Warn" in flags else "OK"


def list_approvals(
	crop=None, status="Pending", from_date=None, to_date=None, unit=None, operation=None, supervisor=None,
	queue=None,
) -> dict:
	if status not in STATUSES:
		frappe.throw(_("Invalid status {0}").format(status), frappe.ValidationError)
	frappe.has_permission("Casual Labour Work", "read", throw=True)
	pay = can_see_pay()
	stale_days = get_stale_days()

	cond, args = ["docstatus < 2", "unit not in %(retired)s"], {"retired": retired_sql()}
	for col, val in (("crop", crop), ("unit", unit), ("operation", operation), ("submitted_by", supervisor)):
		if val:
			cond.append(f"{col} = %({col})s")
			args[col] = val
	if from_date:
		cond.append("work_date >= %(frm)s")
		args["frm"] = from_date
	if to_date:
		cond.append("work_date <= %(to)s")
		args["to"] = to_date
	if not from_date:
		# the Approved history is bounded unless asked for; Pending / Sent Back never are
		cond.append("(approval_status != 'Approved' or work_date >= %(hist)s)")
		args["hist"] = add_days(today(), -DEFAULT_HISTORY_DAYS)
	rows = frappe.db.sql(
		f"""select name, work_date, employee, employee_name, plan, plan_task, unit, crop, operation, qty, uom,
		rate, pay_value, approval_status, rule_status, rule_notes, override_reason, review_note, reviewed_by, reviewed_at, submitted_by, creation,
		wm_actuals, checked_by, checked_at
		from `tabCasual Labour Work` where {' and '.join(cond)} order by creation asc""",
		args, as_dict=True,
	)

	groups = {}
	for r in rows:
		key = f"{r.plan_task or '|'.join((r.unit, r.operation, str(r.work_date)))}::{r.submitted_by}::{r.approval_status}"
		g = groups.setdefault(key, {"key": key, "rows": []})
		g["rows"].append(r)

	counts = {s: 0 for s in STATUSES}
	for g in groups.values():
		counts[g["rows"][0].approval_status] += 1
	stale_count = sum(
		1 for g in groups.values()
		if g["rows"][0].approval_status == "Pending" and _age_days(g["rows"][0].creation) >= stale_days
	)

	tasks = {
		t.name: t for t in frappe.get_all(
			"Work Plan Task",
			filters={"name": ("in", list({r.plan_task for r in rows if r.plan_task}) or [""])},
			fields=["name", "planned_qty", "done_qty", "pending_qty", "note", "status", "supervisor", "assigned_by"],
		)
	}
	plans = {
		p.name: p for p in frappe.get_all(
			"Production Work Plan",
			filters={"name": ("in", list({r.plan for r in rows if r.plan}) or [""])},
			fields=["name", "plan_year", "plan_week"],
		)
	}
	me = frappe.session.user if assistant_step_on() and is_assistant_manager() else None
	assistants = {}

	def _needs(task):
		if not assistant_step_on() or not task or not task.assigned_by:
			return False
		if task.assigned_by not in assistants:
			assistants[task.assigned_by] = is_assistant_manager(task.assigned_by)
		return assistants[task.assigned_by]

	users = {
		u.name: u.full_name for u in frappe.get_all(
			"User", filters={"name": ("in", list({u for r in rows for u in (r.submitted_by, r.checked_by) if u}) or [""])},
			fields=["name", "full_name"],
		)
	}
	unit_names = dict(frappe.get_all("Production Unit", fields=["name", "unit_name"], as_list=True))
	op_names = dict(frappe.get_all("Field Operation", fields=["name", "operation_name"], as_list=True))
	op_colors = dict(frappe.get_all("Field Operation", fields=["name", "color"], as_list=True))

	out = []
	for g in groups.values():
		rs = g["rows"]
		first = rs[0]
		task = tasks.get(first.plan_task)
		mirrored = any(r.wm_actuals for r in rs)
		if queue == "check":
			if first.approval_status != "Pending" or not task or not me or task.assigned_by != me or mirrored:
				continue
		elif queue == "approve":
			if first.approval_status not in ("Pending", "Checked"):
				continue
		elif first.approval_status != status:
			continue
		gstatus = first.approval_status
		age = _age_days(first.creation)
		is_stale = gstatus == "Pending" and age >= stale_days
		plan = plans.get(first.plan)
		review = next((r for r in reversed(rs) if r.review_note or r.reviewed_by), first)
		out.append({
			"key": g["key"],
			"status": gstatus,
			"needs_check": _needs(task) and gstatus == "Pending" and not mirrored,
			"checked_by": first.checked_by,
			"checked_by_name": users.get(first.checked_by) or first.checked_by,
			"checked_at": first.checked_at,
			"crop": first.crop,
			"unit": first.unit,
			"unit_name": unit_names.get(first.unit) or first.unit,
			"operation": first.operation,
			"operation_name": op_names.get(first.operation) or first.operation,
			"color": op_colors.get(first.operation) or None,
			"plan": first.plan,
			"plan_year": plan.plan_year if plan else None,
			"plan_week": plan.plan_week if plan else None,
			"plan_task": first.plan_task,
			"task_planned_qty": task.planned_qty if task else None,
			"task_done_qty": task.done_qty if task else None,
			"task_pending_qty": task.pending_qty if task else None,
			"task_status": task.status if task else None,
			"note": (task.note if task else None),
			"unplanned": 0 if first.plan_task else 1,
			"uom": first.uom,
			"work_date": first.work_date,
			"submitted_by": first.submitted_by,
			"submitted_by_name": users.get(first.submitted_by) or first.submitted_by,
			"created": min(r.creation for r in rs),
			"age_days": age,
			"stale": bool(is_stale),
			"total_qty": sum(r.qty or 0 for r in rs),
			"total_pay": sum(r.pay_value or 0 for r in rs) if pay else None,
			"rule_status": _rule_status(rs),
			"rule_notes": "\n".join(dict.fromkeys(r.rule_notes for r in rs if r.rule_notes)) or None,
			"override_reason": next((r.override_reason for r in rs if r.override_reason), None),
			"review_note": review.review_note,
			"reviewed_by": review.reviewed_by,
			"reviewed_at": review.reviewed_at,
			"names": [r.name for r in rs],
			"wm_actuals": next((r.wm_actuals for r in rs if r.wm_actuals), None),
			"entries": [{
				"name": r.name, "employee": r.employee, "employee_name": r.employee_name, "qty": r.qty,
				"uom": r.uom, "operation": r.operation, "rate": r.rate if pay else None,
				"pay_value": r.pay_value if pay else None, "work_date": r.work_date,
				"approval_status": r.approval_status, "review_note": r.review_note,
				"rule_status": r.rule_status or "OK", "rule_notes": r.rule_notes,
				"override_reason": r.override_reason, "wm_actuals": r.wm_actuals,
			} for r in rs],
		})
	labourers.annotate_work([e for g in out for e in g["entries"]])
	out.sort(key=lambda g: (g["created"],), reverse=(queue is None and status != "Pending"))
	counts["stale"] = stale_count
	if queue:
		counts["queue"] = len(out)  # cards in this queue (Checked included for "approve"), for the tab badge
	return {"groups": out, "counts": counts, "stale_days": stale_days}


def approval_counts() -> dict:
	"""Pending submissions (cards) per crop, for the desk and sidebar badges."""
	frappe.has_permission("Casual Labour Work", "read", throw=True)
	stale_days = get_stale_days()
	rows = frappe.db.sql(
		"""select crop, plan_task, unit, operation, work_date, submitted_by, approval_status, min(creation) as created,
		max(ifnull(wm_actuals, '')) as wm
		from `tabCasual Labour Work` where docstatus = 0 and approval_status in ('Pending', 'Checked')
		and ifnull(crop, '') != '' and unit not in %(retired)s
		group by crop, plan_task, unit, operation, work_date, submitted_by, approval_status""",
		{"retired": retired_sql()}, as_dict=True,
	)
	me = frappe.session.user if assistant_step_on() and is_assistant_manager() else None  # only assistants have a check queue
	assigners = dict(frappe.get_all(
		"Work Plan Task", filters={"name": ("in", list({r.plan_task for r in rows if r.plan_task}) or [""])},
		fields=["name", "assigned_by"], as_list=True,
	))
	step, is_asst, to_check = assistant_step_on(), {}, 0
	seen, per = set(), {}
	for r in rows:
		key = (r.crop, r.plan_task or (r.unit, r.operation, r.work_date), r.submitted_by, r.approval_status)
		if key in seen:
			continue
		seen.add(key)
		by = assigners.get(r.plan_task)
		if r.approval_status == "Pending" and not r.wm:  # Work Management work has no check step
			to_check += 1 if me and by == me else 0
			if step and by:
				if by not in is_asst:
					is_asst[by] = is_assistant_manager(by)
				if is_asst[by]:
					continue  # waits for the assistant manager's check before it is the manager's to approve
		c = per.setdefault(r.crop, {"pending": 0, "stale": 0})
		c["pending"] += 1
		c["stale"] += 1 if _age_days(r.created) >= stale_days else 0
	meta = {
		c.name: c for c in frappe.get_all(
			"Production Crop", fields=["name", "crop_key", "sort_order"], order_by="sort_order asc, name asc"
		)
	}
	from upande_production.production.logic import protocols as _protocols

	proto = _protocols.pending_counts() if frappe.has_permission("Production Protocol", "read") else {}
	for k in proto:
		per.setdefault(k, {"pending": 0, "stale": 0})
	crops = [
		{"crop": k, "crop_key": meta[k].crop_key if k in meta else None, **per[k],
			"protocols_pending": proto.get(k, 0)}
		for k in sorted(per, key=lambda k: list(meta).index(k) if k in meta else 999)
	]
	return {
		"crops": crops,
		"total": sum(c["pending"] for c in crops),
		"to_check": to_check,
		"cycle_changes": _cycle_requests.pending_counts(),
		"protocols_pending": sum(c["protocols_pending"] for c in crops),
		"stale": sum(c["stale"] for c in crops),
		"stale_days": stale_days,
	}
