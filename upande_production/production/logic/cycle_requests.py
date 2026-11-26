"""Cycle change requests: a supervisor or assistant manager asks for a change to a cycle's setup (or its
deletion) and a manager approves, sends back or rejects. Managers edit and delete directly.

Unapproved values are never live on the cycle: a request holds only the fields that changed (`payload`, applied
through `cycle_setup.update_cycle` on approval) and what they were (`changes`, for display and the stale check).
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime

from upande_production.production.logic import cycle_setup
from upande_production.production.logic.settings import is_manager

CYCLE_DT = "Production Crop Cycle"
DT = "Production Cycle Change Request"

PROTECTED = ("unit", "crop", "field_crop", "sub_crop", "variety", "item", "protocol", "start_date", "planting_date",
	"area_ha", "plant_count", "expected_harvest_start", "expected_harvest_end")
# what `update_cycle` takes; `reason` in the data belongs to the request, not the cycle
EDITABLE = PROTECTED + ("status", "notes")
DATES = ("start_date", "planting_date", "expected_harvest_start", "expected_harvest_end")
CLOSING = ("Closed", "Cancelled")
GUARD_FLAGS = ("cycle_change_request", "in_demo_seed", "in_migrate", "in_install", "in_patch")


def norm(field, value):
	"""A value in a comparable form: dates as dates, numbers as numbers, empty as None."""
	if value in (None, ""):
		return None
	if field in DATES:
		return getdate(value)
	if field == "area_ha":
		return flt(value)
	if field == "plant_count":
		return cint(value)
	return value


def _plain(value):
	return str(value) if hasattr(value, "isoformat") else value


def diff(doc, data) -> dict:
	"""{field: {"old", "new"}} for the fields in `data` whose value differs from the cycle's."""
	out = {}
	for key, new in (data or {}).items():
		if key not in EDITABLE:
			continue
		try:
			old_n, new_n = norm(key, doc.get(key)), norm(key, new)
		except Exception:
			frappe.throw(_("One of the dates is not a date."), frappe.ValidationError)
		if old_n != new_n:
			out[key] = {"old": _plain(old_n), "new": _plain(new_n)}
	return out


def touches_protected(changes, data=None) -> bool:
	"""True when the changes touch a protected field; status only when it becomes Closed or Cancelled."""
	if any(k in PROTECTED for k in changes):
		return True
	return (changes.get("status") or {}).get("new") in CLOSING


def guard(doc) -> None:
	"""Validate hook of the cycle: setup changes by non-managers go through a request (no back door)."""
	if doc.is_new() or is_manager() or any(frappe.flags.get(f) for f in GUARD_FLAGS):
		return
	before = doc.get_doc_before_save()
	if not before:
		return
	# area_ha is fetched from the block on every save, so a save cannot change it (update_cycle restores the typed value
	# itself); comparing it would trip every save of a cycle whose area differs from its block's
	changed = {k: {"new": doc.get(k)} for k in EDITABLE if k != "area_ha" and norm(k, before.get(k)) != norm(k, doc.get(k))}
	if touches_protected(changed):
		frappe.throw(_("Changes to a cycle's setup need a manager's approval; use Edit cycle to send a request."),
			frappe.PermissionError)


def _recorded_text(cycle):
	from upande_production.production.doctype.production_crop_cycle.production_crop_cycle import recorded_in

	return ", ".join(sorted(set(recorded_in(cycle))))


def _refuse_if_recorded(cycle):
	rec = _recorded_text(cycle)
	if rec:
		frappe.throw(_("This cycle has records against it ({0}), so it cannot be deleted.").format(rec), frappe.ValidationError)


def _reason(reason):
	reason = (reason or "").strip()
	if not reason:
		frappe.throw(_("Give a reason for the change."), frappe.ValidationError)
	return reason


def pending_for(cycle):
	return frappe.db.get_value(DT, {"cycle": cycle, "status": "Pending"}, ["name", "requested_by", "action", "changes"], as_dict=True)


def _one_open(cycle, ignore=None):
	if frappe.db.exists(DT, {"cycle": cycle, "status": "Pending", "name": ("!=", ignore or "")}):
		frappe.throw(_("A change to this cycle is already waiting for approval."), frappe.ValidationError)


def _new(cycle, action, reason, changes=None, payload=None):
	doc = frappe.get_doc({"doctype": DT, "cycle": cycle, "action": action, "reason": reason, "status": "Pending",
		"changes": changes or {}, "payload": payload or {}, "requested_by": frappe.session.user})
	doc.insert()
	return {"request": doc.name, "pending": True}


def request_edit(name, data, reason) -> dict:
	reason = _reason(reason)
	doc = frappe.get_doc(CYCLE_DT, name)
	changes = diff(doc, data)
	if not changes:
		frappe.throw(_("Nothing has changed."), frappe.ValidationError)
	_one_open(name)
	return _new(name, "Edit", reason, changes, {k: v["new"] for k, v in changes.items()})


def request_delete(name, reason) -> dict:
	reason = _reason(reason)
	_refuse_if_recorded(name)
	_one_open(name)
	return _new(name, "Delete", reason)


def _delete(cycle):
	frappe.delete_doc(CYCLE_DT, cycle)  # change requests link the cycle (hooks: ignore_links_on_delete); nothing else records against it


def delete_cycle(name, reason=None) -> dict:
	_refuse_if_recorded(name)
	if is_manager():
		_delete(name)
		return {"deleted": name}
	return request_delete(name, reason)


def _load(name, statuses):
	r = frappe.get_doc(DT, name)
	if r.status not in statuses:
		frappe.throw(_("This request is not {0}.").format(" / ".join(s.lower() for s in statuses)), frappe.ValidationError)
	return r


def _need_manager():
	if not is_manager():
		frappe.throw(_("Only a manager can decide a cycle change."), frappe.PermissionError)


def _stamp(r, status, note=None):
	r.status, r.reviewed_by, r.reviewed_at = status, frappe.session.user, now_datetime()
	if note is not None:
		r.review_note = note
	r.save()


def approve(name, apply_anyway=0) -> dict:
	_need_manager()
	r = _load(name, ("Pending",))
	if not frappe.db.exists(CYCLE_DT, r.cycle):
		frappe.throw(_("The cycle no longer exists."), frappe.ValidationError)
	if r.action == "Delete":
		_refuse_if_recorded(r.cycle)
		_stamp(r, "Approved")
		_delete(r.cycle)
		return {"request": name, "deleted": r.cycle}
	cycle = frappe.get_doc(CYCLE_DT, r.cycle)
	changes = frappe.parse_json(r.changes) or {}
	stale = [k for k, c in changes.items() if norm(k, cycle.get(k)) != norm(k, c.get("old"))]
	if stale and not cint(apply_anyway):
		frappe.throw(_("{0} changed since this request was made. Apply anyway to overwrite.").format(", ".join(stale)),
			frappe.ValidationError)
	frappe.flags.cycle_change_request = name
	try:
		res = cycle_setup.update_cycle(r.cycle, frappe.parse_json(r.payload) or {})
	finally:
		frappe.flags.cycle_change_request = None
	r.stale = 1 if stale else 0
	_stamp(r, "Approved")
	return {**res, "request": name}


def _decide(name, status, note):
	_need_manager()
	note = (note or "").strip()
	if not note:
		frappe.throw(_("Write a note for the requester."), frappe.ValidationError)
	_stamp(_load(name, ("Pending",)), status, note)
	return {"request": name, "status": status}


def send_back(name, note) -> dict:
	return _decide(name, "Sent Back", note)


def reject(name, note) -> dict:
	return _decide(name, "Rejected", note)


def _mine(name, statuses):
	r = _load(name, statuses)
	if r.requested_by != frappe.session.user:
		frappe.throw(_("Only the person who sent this request can change it."), frappe.PermissionError)
	return r


def resubmit(name, data, reason=None) -> dict:
	r = _mine(name, ("Sent Back",))
	if reason is not None:
		r.reason = _reason(reason)
	if r.action == "Edit":
		if not frappe.db.exists(CYCLE_DT, r.cycle):
			frappe.throw(_("The cycle no longer exists."), frappe.ValidationError)
		changes = diff(frappe.get_doc(CYCLE_DT, r.cycle), data)
		if not changes:
			frappe.throw(_("Nothing has changed."), frappe.ValidationError)
		r.changes, r.payload = changes, {k: v["new"] for k, v in changes.items()}
	_one_open(r.cycle, ignore=name)
	r.status, r.stale = "Pending", 0
	r.save()
	return {"request": name, "pending": True}


def withdraw(name) -> dict:
	r = _mine(name, ("Pending", "Sent Back"))
	_stamp(r, "Rejected", "Withdrawn")
	return {"request": name, "status": "Rejected"}


def list_requests(status=None, crop=None) -> list:
	"""Managers see every request, everyone else their own."""
	filters = {}
	if status:
		filters["status"] = status
	if not is_manager():
		filters["requested_by"] = frappe.session.user
	if crop:
		filters["cycle"] = ("in", frappe.get_all(CYCLE_DT, filters={"crop": crop}, pluck="name") or [""])
	rows = frappe.get_all(DT, filters=filters, order_by="creation desc", fields=[
		"name", "cycle", "action", "status", "reason", "changes", "requested_by", "reviewed_by", "reviewed_at",
		"review_note", "stale", "creation"])
	for r in rows:
		r["changes"] = frappe.parse_json(r["changes"]) or {}
		c = frappe.db.get_value(CYCLE_DT, r["cycle"], ["crop", "unit", "title"], as_dict=True) or {}
		r.update({"crop": c.get("crop"), "unit": c.get("unit"), "cycle_title": c.get("title")})
	return rows


def pending_counts() -> int:
	return frappe.db.count(DT, {"status": "Pending"}) if is_manager() else 0
