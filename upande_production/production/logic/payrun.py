"""Casual labour pay runs: pull approved, unpaid work for a period, approve (submit) it, mark it paid."""

import csv
import io
import json
import re

import frappe
from frappe import _
from frappe.utils import add_days, add_months, flt, get_first_day, get_last_day, getdate, today

from upande_production.production.logic.labour import WEEKDAYS, setting


def name_series() -> str:
	prefix = re.sub(r"[^A-Za-z0-9_-]", "", str(setting("pay_reference_prefix") or "")) or "PAY"
	return f"{prefix}-.YYYY.-.#####"


def default_period(date=None) -> tuple:
	"""(from_date, to_date) of the pay period containing `date`, from Settings pay_period / pay_week_starts_on."""
	d = getdate(date or today())
	period = setting("pay_period")
	if period == "Monthly":
		return get_first_day(d), get_last_day(d)
	start = add_days(d, -((d.weekday() - WEEKDAYS.index(setting("pay_week_starts_on"))) % 7))
	if period == "Fortnightly" and getdate(start).isocalendar()[1] % 2:
		start = add_days(start, -7)  # fortnights begin on even ISO weeks, so every run lines up
	return getdate(start), getdate(add_days(start, 13 if period == "Fortnightly" else 6))


def eligible_work(run) -> list:
	"""Approved (submitted), unpaid work in the run's dates, in no pay run (and on the run's farm, if one is set)."""
	filters = {
		"docstatus": 1, "pay_run": ("is", "not set"), "paid": ("!=", "Paid"),
		"work_date": ("between", [getdate(run.from_date), getdate(run.to_date)]),
	}
	if run.farm:  # a work row's farm is its unit's farm
		filters["unit"] = ("in", frappe.get_all("Production Unit", filters={"farm": run.farm}, pluck="name") or [""])
	rows = frappe.get_all("Casual Labour Work", filters=filters,
		fields=["name", "employee", "employee_name", "work_date", "qty", "pay_value", "company"], order_by="work_date, name")
	return [r for r in rows if not r.company or not run.company or r.company == run.company]


def fill(run):
	"""Replace the run's lines with the eligible work grouped by employee."""
	groups = {}
	for r in eligible_work(run):
		g = groups.setdefault(r.employee, {"employee": r.employee, "employee_name": r.employee_name,
			"dates": set(), "entries": 0, "qty": 0.0, "amount": 0.0, "names": []})
		g["dates"].add(str(r.work_date))
		g["entries"] += 1
		g["qty"] += flt(r.qty)
		g["amount"] += flt(r.pay_value)
		g["names"].append(r.name)
	run.set("lines", [])
	for g in sorted(groups.values(), key=lambda x: (x["employee_name"] or x["employee"])):
		run.append("lines", {"employee": g["employee"], "employee_name": g["employee_name"], "days": len(g["dates"]),
			"entries": g["entries"], "qty": g["qty"], "amount": round(g["amount"], 2), "work_names": json.dumps(g["names"])})
	_totals(run)
	return run


def _totals(run):
	run.total_people = len(run.lines)
	run.total_amount = round(sum(flt(r.amount) for r in run.lines), 2)


def _names(run) -> list[str]:
	return [n for ln in run.lines for n in json.loads(ln.work_names or "[]")]


def validate_run(run):
	if getdate(run.to_date) < getdate(run.from_date):
		frappe.throw(_("To Date cannot be before From Date."), frappe.ValidationError)
	run.company = run.company or frappe.defaults.get_global_default("company")
	if run.docstatus == 0:
		run.status = "Draft"
	_totals(run)
	if run.docstatus == 1:
		if not run.lines:
			frappe.throw(_("There is no work in this pay run."), frappe.ValidationError)
		for n in _names(run):
			row = frappe.db.get_value("Casual Labour Work", n, ["docstatus", "pay_run", "paid"], as_dict=True)
			if not row or row.docstatus != 1 or row.pay_run or row.paid == "Paid":
				frappe.throw(_("{0} is no longer available for this pay run. Get the work again.").format(n),
					frappe.ValidationError)


def approve(run):
	"""on_submit: the run is Approved and its work is locked to it."""
	for n in _names(run):
		frappe.db.set_value("Casual Labour Work", n, "pay_run", run.name, update_modified=False)
	run.db_set("status", "Approved")


def mark_paid(run, reference, paid_on=None):
	if isinstance(run, str):
		run = frappe.get_doc("Casual Labour Pay Run", run)
	if run.docstatus != 1 or run.status != "Approved":
		frappe.throw(_("Only an approved pay run can be marked paid."), frappe.ValidationError)
	paid_on = getdate(paid_on or today())
	reference = (reference or "").strip() or run.name
	for n in _names(run):
		frappe.db.set_value("Casual Labour Work", n,
			{"paid": "Paid", "paid_on": paid_on, "payroll_reference": reference}, update_modified=False)
	run.db_set({"status": "Paid", "paid_on": paid_on, "payment_reference": reference})
	return run


def before_cancel(run):
	if run.status == "Paid":
		frappe.throw(_("A paid pay run cannot be cancelled."), frappe.ValidationError)


def release(run):
	"""on_cancel: free the work for another run."""
	for n in _names(run):
		if frappe.db.get_value("Casual Labour Work", n, "pay_run") == run.name:
			frappe.db.set_value("Casual Labour Work", n, "pay_run", None, update_modified=False)
	run.db_set("status", "Cancelled")


def block_work_cancel(work):
	"""A Casual Labour Work in an Approved or Paid pay run cannot be cancelled."""
	if work.pay_run and frappe.db.get_value("Casual Labour Pay Run", work.pay_run, "status") in ("Approved", "Paid"):
		frappe.throw(_("{0} is in pay run {1}; cancel the pay run first.").format(work.name, work.pay_run),
			frappe.ValidationError)


def export_csv(run) -> str:
	if isinstance(run, str):
		run = frappe.get_doc("Casual Labour Pay Run", run)
	out = io.StringIO()
	w = csv.writer(out, lineterminator="\n")
	w.writerow(["employee", "name", "days", "entries", "qty", "amount"])
	for ln in run.lines:
		w.writerow([ln.employee, ln.employee_name, ln.days, ln.entries, ln.qty, ln.amount])
	return out.getvalue()
