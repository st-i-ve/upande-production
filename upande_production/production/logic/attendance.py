"""Casual labour attendance: Production's own marks, HRMS Attendance, or both."""

import frappe
from frappe import _
from frappe.utils import getdate

from upande_production.production.logic.labour import setting

WORKED = ("Present", "Half Day")
STATUSES = ("Present", "Half Day", "Absent", "On Leave", "Off")


def validate_row(doc):
	if frappe.db.exists("Casual Labour Attendance",
		{"employee": doc.employee, "date": doc.date, "name": ("!=", doc.name or "")}):
		frappe.throw(_("{0} already has attendance for {1}.").format(doc.employee, doc.date), frappe.ValidationError)
	doc.marked_by = frappe.session.user


def _production_status(employee, date):
	return frappe.db.get_value("Casual Labour Attendance", {"employee": employee, "date": getdate(date)}, "status")


def _hrms_status(employee, date):
	if not frappe.db.exists("DocType", "Attendance"):
		return None
	status = frappe.db.get_value("Attendance", {"employee": employee, "attendance_date": getdate(date), "docstatus": 1}, "status")
	return "Present" if status == "Work From Home" else status


def day_status(employee, date) -> str | None:
	"""Present / Half Day / Absent / On Leave / Off, or None when the source has no mark for the day."""
	source = setting("attendance_source")
	if source == "Production":
		return _production_status(employee, date)
	if source == "HRMS Attendance":
		return _hrms_status(employee, date)
	marks = [s for s in (_production_status(employee, date), _hrms_status(employee, date)) if s]
	return next((s for s in marks if s in WORKED), marks[0] if marks else None)


def mark(employees, date, status="Present", farm=None, note=None) -> list[str]:
	"""Bulk upsert one status per employee for the date; returns the attendance names."""
	if status not in STATUSES:
		frappe.throw(_("Invalid status {0}").format(status), frappe.ValidationError)
	names = []
	for emp in dict.fromkeys(employees or []):
		name = frappe.db.get_value("Casual Labour Attendance", {"employee": emp, "date": getdate(date)})
		doc = frappe.get_doc("Casual Labour Attendance", name) if name else frappe.new_doc("Casual Labour Attendance")
		if not name:
			doc.employee, doc.date = emp, getdate(date)
		doc.status = status
		if farm is not None:
			doc.farm = farm or None
		if note is not None:
			doc.note = note
		doc.save()
		names.append(doc.name)
	return names
