# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from upande_production.production.logic import labour_guards, payrun, rates
from upande_production.production.logic.pay import pay_value
from upande_production.production.logic.settings import get_company
from upande_production.production.logic.work import refresh_task_done
from upande_production.production.logic.units import ensure_unit_cost_center


class CasualLabourWork(Document):
	def validate(self):
		self.set_rate()
		self.pay_value = pay_value(self.qty, self.rate)
		self.crop = frappe.db.get_value("Production Unit", self.unit, "crop")
		if not self.cost_center:
			self.cost_center = ensure_unit_cost_center(self.unit)
		self.company = self.company or get_company()
		self.unplanned = 0 if self.plan_task else 1
		if self.is_new() and not self.submitted_by:
			self.submitted_by = frappe.session.user
		labour_guards.check(self)
		self.guard_check()
		if self.docstatus == 0:
			if self.approval_status == "Approved":
				frappe.throw(_("Work is approved only by submitting it."), frappe.ValidationError)
			self.approval_status = self.approval_status or "Pending"

	def guard_check(self):
		"""Checked is stamped by approvals.check (a direct write), never by a save: a save cannot move an entry into
		Checked or stamp a check, and editing a checked entry's quantity, worker or day drops the check."""
		if self.docstatus != 0:
			return
		before = self.get_doc_before_save()
		was_checked = bool(before) and before.approval_status == "Checked"
		if self.approval_status == "Checked" and not was_checked:
			frappe.throw(_("Work is checked only by the assistant manager's Check action."), frappe.ValidationError)
		if was_checked and self.approval_status == "Checked":
			if any(self.has_value_changed(f) for f in ("qty", "employee", "work_date")):
				self.approval_status = "Pending"
				self.checked_by = self.checked_at = None
			else:
				self.checked_by, self.checked_at = before.checked_by, before.checked_at
		elif self.approval_status != "Checked":
			self.checked_by = self.checked_at = None

	def set_rate(self):
		"""The rate comes from the operation's rate period for work_date (else its default rate) and
		rate_source says which. A rate keyed by hand that matches neither is kept and marked Manual.
		Work already in a pay run, or no longer a draft, keeps the rate it has (blank: filled once)."""
		if self.pay_run or (self.docstatus != 0 and self.rate):
			return
		rate, source = rates.rate_on(self.operation, self.work_date)
		if not self.rate:
			self.rate, self.rate_source = rate, source
			return
		default = float(frappe.db.get_value("Field Operation", self.operation, "default_rate") or 0)
		moved = self.is_new() or self.has_value_changed("work_date") or self.has_value_changed("operation")
		if moved and float(self.rate) in (default, rate):
			# the plan's copy of the default is not a decision: the period for this date applies
			self.rate, self.rate_source = rate, source
		elif moved or self.has_value_changed("rate"):
			self.rate_source = source if float(self.rate) == rate else _("Manual")
		elif not self.rate_source:
			self.rate_source = _("Manual")

	def before_submit(self):
		# Submission is the approval: Approved <=> docstatus 1.
		self.approval_status = "Approved"
		self.reviewed_by = frappe.session.user
		self.reviewed_at = now_datetime()

	def on_submit(self):
		refresh_task_done(self.plan, self.plan_task)

	def before_cancel(self):
		payrun.block_work_cancel(self)

	def on_cancel(self):
		refresh_task_done(self.plan, self.plan_task)

	def after_delete(self):
		refresh_task_done(self.plan, self.plan_task)
