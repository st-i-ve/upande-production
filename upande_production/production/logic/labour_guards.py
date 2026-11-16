"""Guards on Casual Labour Work: dates, duplicates, several jobs a day, attendance."""

import frappe
from frappe import _
from frappe.utils import add_days, getdate, today

from upande_production.production.logic import attendance
from upande_production.production.logic.labour import setting

TAG = "Labour: "


def _notes(doc, warnings):
	"""Keep our own warning lines in rule_notes (they replace ours from an earlier save, never the activity
	rules'). rule_status stays the activity rules' own flag."""
	kept = [ln for ln in (doc.rule_notes or "").split("\n") if ln and not ln.startswith(TAG)]
	doc.rule_notes = "\n".join(kept + [TAG + w for w in warnings]) or None


def check(doc):
	"""Raise on a breach, flag a warning; skipped when doc.flags.ignore_labour_guards is set."""
	if doc.flags.get("ignore_labour_guards") or doc.docstatus == 2:
		return
	keys = ("work_date", "employee", "operation", "unit")
	if not doc.is_new() and not any(doc.has_value_changed(k) for k in keys):
		return
	warnings = []
	_dates(doc)
	_duplicate(doc, warnings)
	_other_jobs(doc, warnings)
	_attendance(doc)
	_notes(doc, warnings)
	for w in warnings:
		frappe.msgprint(w, indicator="orange", alert=True)


def _dates(doc):
	d = getdate(doc.work_date)
	if d > getdate(today()):
		frappe.throw(_("Work cannot be dated in the future ({0}).").format(d), frappe.ValidationError)
	days = setting("max_backdate_days")
	if days and d < getdate(add_days(today(), -days)):
		frappe.throw(_("Work older than {0} days cannot be recorded ({1}).").format(days, d), frappe.ValidationError)


def _same_day(doc):
	return {"employee": doc.employee, "work_date": doc.work_date, "docstatus": ("<", 2), "name": ("!=", doc.name or "")}


def _duplicate(doc, warnings):
	rule = setting("duplicate_rule")
	if rule == "Off":
		return
	filters = {**_same_day(doc), "operation": doc.operation, "unit": doc.unit}
	if doc.harvest_batch:  # one row per picker per batch: different batches are different work
		filters["harvest_batch"] = doc.harvest_batch
	other = frappe.db.get_value("Casual Labour Work", filters)
	if not other:
		return
	msg = _("{0} is already recorded for {1} on {2} for this operation and unit ({3}).").format(
		doc.employee, doc.operation, doc.work_date, other)
	if rule == "Block":
		frappe.throw(msg, frappe.ValidationError)
	warnings.append(msg)


def _other_jobs(doc, warnings):
	rule = setting("multiple_jobs_per_day")
	if rule == "Allow":
		return
	rows = frappe.get_all("Casual Labour Work", filters=_same_day(doc), fields=["name", "operation", "unit"])
	rows = [r for r in rows if (r.operation, r.unit) != (doc.operation, doc.unit)]
	if not rows:
		return
	msg = _("{0} is already on another job on {1} ({2}).").format(doc.employee, doc.work_date, rows[0].name)
	if rule == "Block":
		frappe.throw(msg, frappe.ValidationError)
	warnings.append(msg)


def _attendance(doc):
	if not setting("attendance_required"):
		return
	status = attendance.day_status(doc.employee, doc.work_date)
	if status not in attendance.WORKED:
		frappe.throw(_("{0} is not marked present on {1} ({2}).").format(
			doc.employee, doc.work_date, status or _("no attendance")), frappe.ValidationError)
