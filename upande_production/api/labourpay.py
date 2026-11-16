"""Desk API for built-in labour pay: Labour & Pay settings, rate periods, attendance and pay runs.
Same envelope as api.production: data or {"error": msg}. Pay figures need a pay role; changes need a manager."""

import json

import frappe
from frappe import _

from upande_production.api.envelope import as_dict, run
from upande_production.production.logic import attendance, labour, payrun, rates
from upande_production.production.logic.settings import can_see_pay, is_manager, is_supervisor


def _need_manager():
	if not is_manager():
		frappe.throw(_("Only a Production Manager can do this."), frappe.PermissionError)


def _need_pay():
	if not can_see_pay():
		frappe.throw(_("You do not have permission to see pay."), frappe.PermissionError)


# -- settings ----------------------------------------------------------------


def _mode() -> dict:
	return {"mode": labour.setting("labour_mode"), "wm_installed": labour.wm_installed(), "wm_active": labour.wm_active()}


def _settings() -> dict:
	out = labour.labour_settings()
	if not can_see_pay():
		out.pop("daily_wage")
	return {**out, "options": {k: list(v) for k, v in labour.OPTIONS.items()}, **_mode()}


@frappe.whitelist(methods=["POST"])
@run
def labour_mode_status():
	return _mode()


@frappe.whitelist(methods=["POST"])
@run
def get_labour_settings():
	return _settings()


@frappe.whitelist(methods=["POST"])
@run
def save_labour_settings(values):
	"""Only the Labour & Pay fields change; keys not sent stay as they are."""
	_need_manager()
	values = as_dict(values) or {}
	unknown = set(values) - set(labour.DEFAULTS)
	if unknown:
		frappe.throw(_("Unknown setting: {0}").format(", ".join(sorted(unknown))), frappe.ValidationError)
	for key, val in values.items():
		if key in labour.OPTIONS and val not in labour.OPTIONS[key]:
			frappe.throw(_("{0} is not a valid {1}.").format(val, key), frappe.ValidationError)
	doc = frappe.get_doc("Production Settings")
	doc.update(values)
	doc.save()
	return _settings()


# -- rate periods ------------------------------------------------------------

_RATE_FIELDS = ["name", "operation", "operation_name", "valid_from", "valid_to", "rate", "daily_target", "uom", "note"]


@frappe.whitelist(methods=["POST"])
@run
def list_rates(operation=None):
	_need_pay()
	filters = {"operation": operation} if operation else {}
	return {"rates": frappe.get_all("Field Operation Rate", filters=filters, fields=_RATE_FIELDS,
		order_by="operation, valid_from desc")}


@frappe.whitelist(methods=["POST"])
@run
def save_rate(operation=None, valid_from=None, valid_to=None, rate=None, daily_target=None, note=None, name=None):
	_need_manager()
	doc = frappe.get_doc("Field Operation Rate", name) if name else frappe.new_doc("Field Operation Rate")
	if not name:
		doc.operation = operation
	elif operation and operation != doc.operation:
		frappe.throw(_("A rate period cannot move to another operation."), frappe.ValidationError)
	doc.valid_from = valid_from or doc.valid_from
	doc.valid_to = valid_to or None
	doc.rate = rate if rate not in (None, "") else None
	doc.daily_target = daily_target if daily_target not in (None, "") else None
	doc.note = note
	doc.save()
	return {k: doc.get(k) for k in _RATE_FIELDS}


@frappe.whitelist(methods=["POST"])
@run
def delete_rate(name):
	_need_manager()
	frappe.delete_doc("Field Operation Rate", name)
	return {"deleted": name}


# -- attendance --------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
@run
def attendance_day(date, farm=None):
	"""Every mark on the day (optionally one farm's): [{employee, employee_name, status, farm, note}]."""
	frappe.has_permission("Casual Labour Attendance", "read", throw=True)
	filters = {"date": date, **({"farm": farm} if farm else {})}
	rows = frappe.get_all("Casual Labour Attendance", filters=filters,
		fields=["name", "employee", "employee_name", "status", "farm", "note"], order_by="employee_name")
	return {"date": date, "rows": rows}


@frappe.whitelist(methods=["POST"])
@run
def mark_attendance(employees, date, status="Present", farm=None, note=None):
	if not is_supervisor():
		frappe.throw(_("You do not have permission to mark attendance."), frappe.PermissionError)
	names = attendance.mark(as_dict(employees) or [], date, status, farm, note)
	return {"marked": len(names), "names": names}


# -- pay runs ----------------------------------------------------------------


def _detail(doc) -> dict:
	lines = [{"employee": ln.employee, "employee_name": ln.employee_name, "days": ln.days, "entries": ln.entries,
		"qty": ln.qty, "amount": ln.amount, "work": json.loads(ln.work_names or "[]")} for ln in doc.lines]
	head = {k: doc.get(k) for k in ("name", "company", "farm", "from_date", "to_date", "status", "docstatus",
		"payment_reference", "paid_on", "total_people", "total_amount")}
	return {**head, "lines": lines}


@frappe.whitelist(methods=["POST"])
@run
def list_pay_runs(status=None, limit=50):
	_need_pay()
	frappe.has_permission("Casual Labour Pay Run", "read", throw=True)
	filters = {"status": status} if status else {}
	return {"runs": frappe.get_all("Casual Labour Pay Run", filters=filters, order_by="from_date desc, creation desc",
		limit=int(limit or 50), fields=["name", "company", "farm", "from_date", "to_date", "status", "docstatus",
			"total_people", "total_amount", "payment_reference", "paid_on"]),
		"default_period": dict(zip(("from_date", "to_date"), payrun.default_period())),
		"pay_day": labour.setting("pay_day")}


@frappe.whitelist(methods=["POST"])
@run
def new_pay_run(from_date=None, to_date=None, farm=None):
	"""A draft run for the dates (default: the current pay period) filled with the work waiting to be paid."""
	_need_manager()
	start, end = payrun.default_period(from_date or None)  # the period holding from_date, else today
	doc = frappe.new_doc("Casual Labour Pay Run")
	doc.update({"from_date": from_date or start, "to_date": to_date or end, "farm": farm or None})
	payrun.validate_run(doc)  # sets the company and checks the dates
	payrun.fill(doc)
	doc.insert()
	return _detail(doc)


@frappe.whitelist(methods=["POST"])
@run
def refresh_pay_run(name):
	"""Re-pull the eligible work into a draft run."""
	_need_manager()
	doc = frappe.get_doc("Casual Labour Pay Run", name)
	if doc.docstatus != 0:
		frappe.throw(_("Only a draft pay run can be refreshed."), frappe.ValidationError)
	payrun.fill(doc)
	doc.save()
	return _detail(doc)


@frappe.whitelist(methods=["POST"])
@run
def pay_run_detail(name):
	_need_pay()
	frappe.has_permission("Casual Labour Pay Run", "read", throw=True)
	return _detail(frappe.get_doc("Casual Labour Pay Run", name))


@frappe.whitelist(methods=["POST"])
@run
def approve_pay_run(name):
	_need_manager()
	doc = frappe.get_doc("Casual Labour Pay Run", name)
	doc.submit()
	return _detail(doc)


@frappe.whitelist(methods=["POST"])
@run
def mark_pay_run_paid(name, reference=None, paid_on=None):
	_need_manager()
	return _detail(payrun.mark_paid(name, reference, paid_on))


@frappe.whitelist(methods=["POST"])
@run
def cancel_pay_run(name):
	_need_manager()
	doc = frappe.get_doc("Casual Labour Pay Run", name)
	if doc.docstatus == 0:
		frappe.delete_doc("Casual Labour Pay Run", name)
		return {"name": name, "status": "Deleted"}
	doc.cancel()
	return _detail(doc)


@frappe.whitelist(methods=["POST"])
@run
def pay_run_csv(name):
	_need_pay()
	frappe.has_permission("Casual Labour Pay Run", "read", throw=True)
	return {"filename": f"{name}.csv", "csv": payrun.export_csv(name)}
