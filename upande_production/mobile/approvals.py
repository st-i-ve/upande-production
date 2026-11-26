"""Phone endpoints for the approval chain: assistant managers check, managers approve and forward.

Same conventions as mobile/api.py: JSON body in, `frappe.response["data"]` out, a refusal is a 200 carrying
`{"error": ...}`, success carries `"status": "success"`.
"""
import frappe

from upande_production.mobile.api import _denied, _fail, _need, _payload, _require, _run, _s, _strip_pay
from upande_production.production.logic import approvals, task_approval

QUEUE_CAP = {"check": "plan_check", "approve": "plan_approve"}


def _guarded(name, go):
	"""_run, with an authorisation refusal from the logic layer reported plainly (not logged as a fault)."""
	def inner():
		try:
			return go()
		except frappe.PermissionError as e:
			frappe.db.rollback()
			return {"error": frappe.utils.strip_html(str(e)) or "You do not have permission to do this."}

	_run(name, inner)


def _names(data):
	names = data.get("names")
	return names if isinstance(names, (list, str)) else None


@frappe.whitelist()
def productionListApprovals():
	"""Work waiting for the user: queue "check" (assistant manager) or "approve" (manager), one crop."""
	data = _payload()
	queue = _s(data, "queue")
	if queue not in QUEUE_CAP:
		return _fail('Queue must be "check" or "approve".')
	if _need(QUEUE_CAP[queue]) or _denied(("Casual Labour Work", "read")):
		return

	def go():
		res = approvals.list_approvals(
			crop=_s(data, "crop") or None, queue=queue, status="Pending",
			from_date=_s(data, "from_date") or None, to_date=_s(data, "to_date") or None,
			unit=_s(data, "unit") or None, operation=_s(data, "operation") or None,
		)
		for g in res["groups"]:
			_strip_pay(g, "total_pay")
			_strip_pay(g["entries"], "rate", "pay_value")
		return {"status": "success", "groups": res["groups"], "counts": res["counts"], "stale_days": res["stale_days"]}

	_guarded("productionListApprovals", go)


@frappe.whitelist()
def productionCheckWork():
	if _need("plan_check") or _denied(("Casual Labour Work", "write")):
		return
	data = _payload()
	err = _require(data, "names")
	if err:
		return _fail(err)

	def go():
		res = approvals.check(_names(data))
		frappe.db.commit()
		return {"status": "success", "checked": res["checked"], "approval_status": "Checked",
			"message": f"{len(res['checked'])} work record(s) checked."}

	_guarded("productionCheckWork", go)


@frappe.whitelist()
def productionApproveWork():
	if _need("plan_approve") or _denied(("Casual Labour Work", "submit")):
		return
	data = _payload()
	err = _require(data, "names")
	if err:
		return _fail(err)

	def go():
		res = approvals.approve(_names(data), unchecked_ok=data.get("unchecked_ok") or 0)
		frappe.db.commit()
		return {"status": "success", "approved": res["approved"], "approval_status": "Approved",
			"message": f"{len(res['approved'])} work record(s) approved."}

	_guarded("productionApproveWork", go)


@frappe.whitelist()
def productionSendBackWork():
	if not (_has("plan_check") or _has("plan_approve")):
		return _fail("You do not have permission to do this.")
	if _denied(("Casual Labour Work", "write")):
		return
	data = _payload()
	err = _require(data, "names", "note")
	if err:
		return _fail(err)

	def go():
		res = approvals.send_back(_names(data), _s(data, "note"))
		frappe.db.commit()
		return {"status": "success", "sent_back": res["sent_back"], "approval_status": "Sent Back",
			"message": f"{len(res['sent_back'])} work record(s) sent back."}

	_guarded("productionSendBackWork", go)


def _has(cap) -> bool:
	from upande_production.mobile import access

	return access.has_capability(cap)


@frappe.whitelist()
def productionForwardTasks():
	"""Release an assistant manager's awaiting tasks (all of the plan's, or the named ones) to the supervisors."""
	if _need("plan_approve") or _denied(("Production Work Plan", "write")):
		return
	data = _payload()
	err = _require(data, "plan")
	if err:
		return _fail(err)

	def go():
		res = task_approval.forward(_s(data, "plan"), data.get("tasks") or None)
		frappe.db.commit()
		return {"status": "success", "forwarded": res["forwarded"],
			"message": f"{len(res['forwarded'])} task(s) forwarded to the supervisors."}

	_guarded("productionForwardTasks", go)


@frappe.whitelist()
def productionApprovalCounts():
	"""Badge numbers: to_check (assistant manager's queue) and to_approve (manager's queue)."""
	if _denied(("Casual Labour Work", "read")):
		return

	def go():
		c = approvals.approval_counts()
		return {"status": "success", "to_check": c["to_check"], "to_approve": c["total"]}

	_guarded("productionApprovalCounts", go)
