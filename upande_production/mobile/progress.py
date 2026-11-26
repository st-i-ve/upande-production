"""Phone endpoints for task progress logs (notes, quantity, photos/files on a plan task, any number a day).

Same conventions as mobile/api.py: JSON body in, `frappe.response["data"]` out, a refusal is a 200 carrying
`{"error": ...}`, success carries `"status": "success"`. Files are uploaded first through Frappe's
`/api/method/upload_file` (is_private=1, no doctype); the URLs it returns go in `files`.
"""
import frappe

from upande_production.mobile import access
from upande_production.mobile.api import _denied, _fail, _payload, _require, _run, _s
from upande_production.production.logic import progress

CAPS = ("plan_tick_off", "plan_manage", "plan_approve")


def _guarded(name, go):
	def inner():
		try:
			return go()
		except frappe.PermissionError as e:
			frappe.db.rollback()
			return {"error": frappe.utils.strip_html(str(e)) or "You do not have permission to do this."}

	_run(name, inner)


def _allowed(caps=CAPS) -> bool:
	if any(access.has_capability(c) for c in caps):
		return True
	_fail("You do not have permission to do this.")
	return False


@frappe.whitelist()
def productionLogProgress():
	if not _allowed() or _denied(("Task Progress Log", "create")):
		return
	data = _payload()
	err = _require(data, "plan", "task")
	if err:
		return _fail(err)

	def go():
		log = progress.log_progress(_s(data, "plan"), _s(data, "task"), notes=_s(data, "notes") or None,
			qty=data.get("qty"), log_date=_s(data, "log_date") or None, files=data.get("files"))
		frappe.db.commit()
		return {"status": "success", "log": log, "message": "Progress logged."}

	_guarded("productionLogProgress", go)


@frappe.whitelist()
def productionListProgress():
	if not _allowed(CAPS + ("plan_view",)) or _denied(("Task Progress Log", "read")):
		return
	data = _payload()
	err = _require(data, "plan", "task")
	if err:
		return _fail(err)

	def go():
		return {"status": "success", "logs": progress.list_progress(_s(data, "plan"), _s(data, "task"))}

	_guarded("productionListProgress", go)
