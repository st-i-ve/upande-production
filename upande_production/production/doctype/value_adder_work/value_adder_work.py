# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

from upande_production.production.logic.pay import pay_value
from upande_production.production.logic.settings import get_company
from upande_production.production.logic.work import refresh_task_done
from upande_production.production.logic.units import ensure_unit_cost_center


class ValueAdderWork(Document):
	def validate(self):
		if not self.rate:
			self.rate = frappe.db.get_value("Production Operation", self.operation, "default_rate") or 0
		self.pay_value = pay_value(self.qty, self.rate)
		self.crop = frappe.db.get_value("Production Unit", self.unit, "crop")
		if not self.cost_center:
			self.cost_center = ensure_unit_cost_center(self.unit)
		self.company = self.company or get_company()
		self.unplanned = 0 if self.plan_task else 1
		if self.is_new() and not self.submitted_by:
			self.submitted_by = frappe.session.user
		if self.docstatus == 0:
			if self.approval_status == "Approved":
				frappe.throw(_("Work is approved only by submitting it."), frappe.ValidationError)
			self.approval_status = self.approval_status or "Pending"

	def before_submit(self):
		# Submission is the approval: Approved <=> docstatus 1.
		self.approval_status = "Approved"
		self.reviewed_by = frappe.session.user
		self.reviewed_at = now_datetime()

	def on_submit(self):
		refresh_task_done(self.plan, self.plan_task)

	def on_cancel(self):
		refresh_task_done(self.plan, self.plan_task)

	def after_delete(self):
		refresh_task_done(self.plan, self.plan_task)
