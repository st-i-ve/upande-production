"""Clear block: a block is uprooted or cleared and will be replanted. Every running cycle on it closes (no successor is
proposed), planned cycles are removed or closed, open plan tasks from the date are skipped and the block goes Fallow.
Straight DB writes, as when a block is retired, so no cycle hook proposes a next cycle."""

import frappe
from frappe import _
from frappe.utils import cstr, getdate, now_datetime, today

CYCLE_DT = "Production Crop Cycle"
REQUEST_DT = "Production Cycle Change Request"
TASK_DT = "Work Plan Task"
RUNNING = ("Active", "Harvesting")
REASONS = ("Uprooted", "Crop failed", "Replanting", "Other")
OPEN_TASKS = ("Open", "In Progress")


def _cycles(unit, statuses):
	return frappe.get_all(CYCLE_DT, filters={"unit": unit, "status": ("in", statuses)},
		fields=["name", "start_date", "status", "creation"], order_by="start_date asc, creation asc")


def _recorded(cycle) -> bool:
	from upande_production.production.doctype.production_crop_cycle.production_crop_cycle import recorded_in

	return bool(recorded_in(cycle))


def check_unit(unit):
	"""The block's status and cycles; raises when it cannot be cleared."""
	row = frappe.db.get_value("Production Unit", unit, ["name", "status", "is_group"], as_dict=True)
	if not row:
		frappe.throw(_("Block {0} not found").format(unit), frappe.ValidationError)
	if row.status == "Retired":
		frappe.throw(_("{0} is retired and cannot be cleared.").format(unit), frappe.ValidationError)
	running, planned = _cycles(unit, RUNNING), _cycles(unit, ("Planned",))
	if row.is_group or not (running or planned):
		frappe.throw(_("Nothing to clear on {0}.").format(unit), frappe.ValidationError)
	return running, planned


def validate(unit, on_date, reason, note=None):
	"""Check the inputs; returns (date, running cycles, planned cycles)."""
	running, planned = check_unit(unit)
	if not on_date:
		frappe.throw(_("Give the date the block was cleared."), frappe.ValidationError)
	d = getdate(on_date)
	if d > getdate(today()):
		frappe.throw(_("The date is in the future."), frappe.ValidationError)
	if reason not in REASONS:
		frappe.throw(_("Choose a reason: {0}.").format(", ".join(REASONS)), frappe.ValidationError)
	if reason == "Other" and not cstr(note).strip():
		frappe.throw(_("Write a note when the reason is Other."), frappe.ValidationError)
	if running:
		earliest = min(getdate(c.start_date) for c in running)
		if d < earliest:
			frappe.throw(_("The date is before the earliest running cycle started ({0}).").format(earliest), frappe.ValidationError)
	return d, running, planned


def _tasks(unit, on):
	return frappe.get_all(TASK_DT, filters={"unit": unit, "status": ("in", OPEN_TASKS), "due_date": (">=", on)},
		fields=["name", "note"])


def preview(unit, on_date=None) -> dict:
	"""What clearing the block would close, delete and skip (nothing is written). Tasks count from `on_date` (default today)."""
	running, planned = check_unit(unit)
	n_deleted = sum(1 for c in planned if not _recorded(c.name))
	on = getdate(on_date or today())
	return {"unit": unit, "running": len(running), "planned_deleted": n_deleted, "planned_closed": len(planned) - n_deleted,
		"tasks_skipped": len(_tasks(unit, on)), "on_date": str(on),
		"earliest_start": str(min(getdate(c.start_date) for c in running)) if running else None,
		"cycles": [c.name for c in running], "planned": [c.name for c in planned]}


def clear_block(unit, on_date, reason, note=None, except_request=None) -> dict:
	"""Clear the block as of `on_date` (one transaction). Returns the counts."""
	d, running, planned = validate(unit, on_date, reason, note)
	note = cstr(note).strip() or None
	cycles = [c.name for c in running] + [c.name for c in planned]
	rejected = _reject_pending(cycles, except_request)
	close = {"status": "Closed", "current_stage": None, "protocol_flags": "", "flag_count": 0, "closed_on": d,
		"close_reason": reason, "close_note": note}
	for c in running:
		vals = dict(close)
		if not frappe.db.get_value(CYCLE_DT, c.name, "actual_harvest_end"):
			vals["actual_harvest_end"] = d
		frappe.db.set_value(CYCLE_DT, c.name, vals, update_modified=False)
	n_deleted = n_closed = 0
	for c in planned:
		if _recorded(c.name):
			frappe.db.set_value(CYCLE_DT, c.name, close, update_modified=False)
			n_closed += 1
		else:
			frappe.delete_doc(CYCLE_DT, c.name, ignore_permissions=True)
			n_deleted += 1
	skipped = 0
	for t in _tasks(unit, d):
		text = f"Block cleared {d}: {reason}"
		frappe.db.set_value(TASK_DT, t.name, {"status": "Skipped", "note": f"{t.note}\n{text}" if t.note else text}, update_modified=False)
		skipped += 1
	frappe.db.set_value("Production Unit", unit, {"status": "Fallow", "cleared_on": d}, update_modified=False)
	return {"unit": unit, "on_date": str(d), "running_closed": len(running), "planned_deleted": n_deleted,
		"planned_closed": n_closed, "tasks_skipped": skipped, "requests_rejected": rejected}


def _reject_pending(cycles, except_request=None) -> int:
	filters = {"cycle": ("in", cycles or [""]), "status": "Pending"}
	if except_request:
		filters["name"] = ("!=", except_request)
	names = frappe.get_all(REQUEST_DT, filters=filters, pluck="name")
	for n in names:
		frappe.db.set_value(REQUEST_DT, n, {"status": "Rejected", "review_note": "Block cleared",
			"reviewed_by": frappe.session.user, "reviewed_at": now_datetime()})
	return len(names)
