"""Rate periods of a field operation: what a unit of work paid on a given date."""

import frappe
from frappe import _
from frappe.utils import getdate

from upande_production.production.logic.labour import setting


def validate_period(doc):
	if doc.valid_to and getdate(doc.valid_to) < getdate(doc.valid_from):
		frappe.throw(_("Valid To cannot be before Valid From."), frappe.ValidationError)
	if doc.rate is not None and float(doc.rate or 0) < 0:
		frappe.throw(_("Rate cannot be negative."), frappe.ValidationError)
	for r in frappe.get_all(
		"Field Operation Rate", filters={"operation": doc.operation, "name": ("!=", doc.name or "")},
		fields=["name", "valid_from", "valid_to"],
	):
		# two periods overlap unless one ends before the other starts (a blank end is open)
		ends_before = r.valid_to and getdate(r.valid_to) < getdate(doc.valid_from)
		starts_after = doc.valid_to and getdate(r.valid_from) > getdate(doc.valid_to)
		if not (ends_before or starts_after):
			frappe.throw(_("This period overlaps {0} for the same operation.").format(r.name),
				frappe.ValidationError)


def period_on(operation, work_date):
	"""The rate period (dict) covering work_date, or None."""
	rows = frappe.get_all(
		"Field Operation Rate",
		filters={"operation": operation, "valid_from": ("<=", getdate(work_date))},
		or_filters=[["valid_to", "is", "not set"], ["valid_to", ">=", getdate(work_date)]],
		fields=["name", "rate", "daily_target", "valid_from", "valid_to"], order_by="valid_from desc", limit=1,
	)
	return rows[0] if rows else None


def rate_on(operation, work_date) -> tuple[float, str]:
	"""(rate, source label): the period's rate; else the period's daily target against the daily wage;
	else the operation's default rate."""
	period = period_on(operation, work_date)
	if period:
		if float(period.rate or 0):
			return float(period.rate), _("Rate period {0}").format(period.name)
		wage = float(setting("daily_wage") or 0)
		if float(period.daily_target or 0) and wage:
			return round(wage / float(period.daily_target), 6), _("Daily wage / target ({0})").format(period.name)
	return float(frappe.db.get_value("Field Operation", operation, "default_rate") or 0), _("Operation default")
