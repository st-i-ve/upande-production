"""Approval workflow for supervisor-keyed work (Value Adder Work).

Supervisor keys work in as a draft (Pending). A manager approves it (submit, so it counts) or sends it
back with a note (Sent Back). The supervisor fixes and resubmits (back to Pending).
"""

import json

import frappe
from frappe import _
from frappe.utils import add_days, cint, now_datetime, today

from upande_production.production.logic import work
from upande_production.production.logic.units import retired_sql
from upande_production.production.logic.settings import (
	can_see_pay, get_stale_days, is_manager, is_supervisor,
)

STATUSES = ("Pending", "Approved", "Sent Back")
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
	docs = []
	for n in names:
		doc = frappe.get_doc("Value Adder Work", n)
		if doc.docstatus != 0 or doc.approval_status != status:
			frappe.throw(
				_("{0} is {1}, not {2}.").format(
					n, "approved" if doc.docstatus == 1 else doc.approval_status, status
				),
				frappe.ValidationError,
			)
		docs.append(doc)
	return docs


def _refresh(docs):
	for plan, task in dict.fromkeys((d.plan, d.plan_task) for d in docs):
		work.refresh_task_done(plan, task)


def approve(names) -> dict:
	_need_manager()
	docs = _docs(_names(names), "Pending")
	for d in docs:
		d.submit()  # before_submit stamps Approved/reviewed_by/at; on_submit recounts the task
	return {"approved": [d.name for d in docs]}


def send_back(names, note) -> dict:
	_need_manager()
	note = (note or "").strip()
	if not note:
		frappe.throw(_("A note is required when sending work back."), frappe.ValidationError)
	docs = _docs(_names(names), "Pending")
	for d in docs:
		d.approval_status = "Sent Back"
		d.review_note = note
		d.reviewed_by = frappe.session.user
		d.reviewed_at = now_datetime()
		d.save()
	_refresh(docs)
	return {"sent_back": [d.name for d in docs]}


def resubmit(names, entries=None) -> dict:
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
		if "hours" in e:
			d.hours = e["hours"]
		if e.get("employee"):
			d.employee = e["employee"]
		d.approval_status = "Pending"
		d.save()
	_refresh(docs)
	return {"resubmitted": [d.name for d in docs]}


# -- listing -----------------------------------------------------------------


def _age_days(created) -> int:
	return max((now_datetime() - frappe.utils.get_datetime(created)).days, 0)


def _rule_status(rows) -> str:
	flags = {r.rule_status for r in rows}
	return "Block" if "Block" in flags else "Warn" if "Warn" in flags else "OK"


def list_approvals(
	crop=None, status="Pending", from_date=None, to_date=None, unit=None, operation=None, supervisor=None
) -> dict:
	if status not in STATUSES:
		frappe.throw(_("Invalid status {0}").format(status), frappe.ValidationError)
	frappe.has_permission("Value Adder Work", "read", throw=True)
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
		hours, rate, pay_value, approval_status, rule_status, rule_notes, override_reason, review_note, reviewed_by, reviewed_at, submitted_by, creation
		from `tabValue Adder Work` where {' and '.join(cond)} order by creation asc""",
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
			"Production Plan Task",
			filters={"name": ("in", list({r.plan_task for r in rows if r.plan_task}) or [""])},
			fields=["name", "planned_qty", "done_qty", "pending_qty", "note", "status", "supervisor"],
		)
	}
	plans = {
		p.name: p for p in frappe.get_all(
			"Production Work Plan",
			filters={"name": ("in", list({r.plan for r in rows if r.plan}) or [""])},
			fields=["name", "plan_year", "plan_week"],
		)
	}
	users = {
		u.name: u.full_name for u in frappe.get_all(
			"User", filters={"name": ("in", list({r.submitted_by for r in rows if r.submitted_by}) or [""])},
			fields=["name", "full_name"],
		)
	}
	unit_names = dict(frappe.get_all("Production Unit", fields=["name", "unit_name"], as_list=True))
	op_names = dict(frappe.get_all("Production Operation", fields=["name", "operation_name"], as_list=True))
	op_colors = dict(frappe.get_all("Production Operation", fields=["name", "color"], as_list=True))

	out = []
	for g in groups.values():
		rs = g["rows"]
		first = rs[0]
		if first.approval_status != status:
			continue
		age = _age_days(first.creation)
		is_stale = status == "Pending" and age >= stale_days
		task = tasks.get(first.plan_task)
		plan = plans.get(first.plan)
		review = next((r for r in reversed(rs) if r.review_note or r.reviewed_by), first)
		out.append({
			"key": g["key"],
			"status": status,
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
			"entries": [{
				"name": r.name, "employee": r.employee, "employee_name": r.employee_name, "qty": r.qty,
				"uom": r.uom, "hours": r.hours, "rate": r.rate if pay else None,
				"pay_value": r.pay_value if pay else None, "work_date": r.work_date,
				"approval_status": r.approval_status, "review_note": r.review_note,
				"rule_status": r.rule_status or "OK", "rule_notes": r.rule_notes,
				"override_reason": r.override_reason,
			} for r in rs],
		})
	out.sort(key=lambda g: (g["created"],), reverse=status != "Pending")
	counts["stale"] = stale_count
	return {"groups": out, "counts": counts, "stale_days": stale_days}


def approval_counts() -> dict:
	"""Pending submissions (cards) per crop, for the desk and sidebar badges."""
	frappe.has_permission("Value Adder Work", "read", throw=True)
	stale_days = get_stale_days()
	rows = frappe.db.sql(
		"""select crop, plan_task, unit, operation, work_date, submitted_by, min(creation) as created
		from `tabValue Adder Work` where docstatus = 0 and approval_status = 'Pending' and ifnull(crop, '') != ''
		and unit not in %(retired)s
		group by crop, plan_task, unit, operation, work_date, submitted_by""",
		{"retired": retired_sql()}, as_dict=True,
	)
	seen, per = set(), {}
	for r in rows:
		key = (r.crop, r.plan_task or (r.unit, r.operation, r.work_date), r.submitted_by)
		if key in seen:
			continue
		seen.add(key)
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
		"protocols_pending": sum(c["protocols_pending"] for c in crops),
		"stale": sum(c["stale"] for c in crops),
		"stale_days": stale_days,
	}
