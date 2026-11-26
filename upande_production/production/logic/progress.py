"""Task progress logs: a note, a quantity and photos/files a supervisor adds to a plan task, any number of times a day.

A log never creates labour or pay records and never changes done_qty / pending_qty (only approved crew work does).
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, now_datetime, today

from upande_production.production.logic import settings, task_approval

DOCTYPE = "Task Progress Log"
FIELDS = ["name", "plan", "task", "unit", "operation", "crop", "log_date", "logged_at", "logged_by", "qty", "uom", "notes"]
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".bmp")


def _task_row(plan, task, logging=False):
	"""The task row, once the user may see it: crop allowed. Logging refuses an awaiting task like recording work
	does; reading refuses it only for users who may not see awaiting tasks."""
	frappe.has_permission("Production Work Plan", "read", doc=plan, throw=True)
	doc = frappe.get_doc("Production Work Plan", plan)
	row = next((t for t in doc.tasks if t.name == task), None)
	if not row:
		frappe.throw(_("Task not found on plan {0}").format(plan), frappe.ValidationError)
	if not settings.crop_allowed(doc.crop):
		frappe.throw(_("You are not permitted to see this crop."), frappe.PermissionError)
	if logging:
		task_approval.refuse_if_awaiting(row)
	elif row.get("awaiting_approval") and task_approval.visible_filter():
		frappe.throw(_("This task is waiting for a manager's approval."), frappe.ValidationError)
	return doc, row


def _find_file(url):
	"""The File doc this user may attach for `url`. Uploads of the same content share a URL across several File
	docs, so pick the caller's own private, unattached one."""
	filters = {"file_url": url, "is_folder": 0, "is_private": 1, "attached_to_doctype": ("is", "not set")}
	if frappe.session.user != "Administrator":
		filters["owner"] = frappe.session.user
	found = frappe.get_all("File", filters=filters, fields=["name", "file_name"], order_by="creation asc", limit=1)
	if not found:
		frappe.throw(_("File {0} cannot be attached here. Upload it again as a private file.").format(url),
			frappe.ValidationError)
	return found[0]


def _attach(f, url, log_name):
	frappe.db.set_value("File", f.name, {"attached_to_doctype": DOCTYPE, "attached_to_name": log_name,
		"attached_to_field": "attachments"}, update_modified=False)
	return {"file_url": url, "file_name": f.file_name, "is_image": 1 if (f.file_name or url).lower().endswith(IMAGE_EXT) else 0}


def _as_dict(doc) -> dict:
	out = {k: doc.get(k) for k in FIELDS}
	out["logged_by_name"] = frappe.db.get_value("User", doc.logged_by, "full_name") if doc.logged_by else None
	out["attachments"] = [{k: a.get(k) for k in ("file_url", "file_name", "is_image")} for a in doc.get("attachments") or []]
	return out


def _files(files) -> list:
	if isinstance(files, str):
		files = frappe.parse_json(files) if files.strip().startswith("[") else [files]
	return [f for f in (files or []) if f]


def log_progress(plan, task, notes=None, qty=None, log_date=None, files=None) -> dict:
	frappe.has_permission(DOCTYPE, "create", throw=True)
	notes = (notes or "").strip()
	files = _files(files)
	qty = None if qty in (None, "") else flt(qty)
	if qty is not None and qty < 0:
		frappe.throw(_("Quantity cannot be negative."), frappe.ValidationError)
	if not (notes or qty or files):
		frappe.throw(_("Add a note, a quantity or a file to log progress."), frappe.ValidationError)
	log_date = getdate(log_date or today())
	if log_date > getdate(today()):
		frappe.throw(_("The log date cannot be in the future."), frappe.ValidationError)
	plan_doc, row = _task_row(plan, task, logging=True)
	# check every file before anything is written, so a bad one leaves no log behind
	found = [(url, _find_file(url)) for url in dict.fromkeys(files)]
	doc = frappe.get_doc({
		"doctype": DOCTYPE, "plan": plan, "task": task, "unit": row.unit, "operation": row.operation,
		"crop": plan_doc.crop, "log_date": log_date, "logged_at": now_datetime(), "logged_by": frappe.session.user,
		"qty": qty or 0, "uom": row.uom if qty else None, "notes": notes,
	})
	doc.insert()
	for url, f in found:
		doc.append("attachments", _attach(f, url, doc.name))
	if files:
		doc.flags.ignore_permissions = True
		doc.save()
	return _as_dict(doc)


def list_progress(plan, task) -> list[dict]:
	"""Logs of one task, newest first."""
	frappe.has_permission(DOCTYPE, "read", throw=True)
	_task_row(plan, task)
	names = frappe.get_all(DOCTYPE, filters={"plan": plan, "task": task}, pluck="name",
		order_by="log_date desc, logged_at desc, creation desc")
	return [_as_dict(frappe.get_doc(DOCTYPE, n)) for n in names]


def latest_by_task(plan) -> dict:
	"""{task row name: date of its latest log} for a plan."""
	return {r.task: r.last for r in frappe.db.sql(
		"select task, max(log_date) as last from `tabTask Progress Log` where plan = %s group by task", plan, as_dict=True)}


def has_progress(task) -> bool:
	"""True when any progress log is recorded against the task row."""
	return bool(frappe.db.exists(DOCTYPE, {"task": task}))


def refuse_if_logged(task) -> None:
	if has_progress(task):
		frappe.throw(_("Progress is logged on this task; mark it Skipped instead."), frappe.ValidationError)


def move_logs(task, from_plan, to_plan, to_task) -> None:
	"""A task row that moved to another plan takes its progress logs with it."""
	frappe.db.set_value(DOCTYPE, {"plan": from_plan, "task": task}, {"plan": to_plan, "task": to_task},
		update_modified=False)
