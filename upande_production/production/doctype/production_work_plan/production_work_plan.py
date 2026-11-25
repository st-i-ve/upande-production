# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from upande_production.production.logic import supervisors
from upande_production.production.logic.deviation import task_deviation
from upande_production.production.logic.settings import get_company, get_tolerance_days
from upande_production.production.logic.weeks import iso_week_bounds


class ProductionWorkPlan(Document):
	def validate(self):
		self.week_start, self.week_end = iso_week_bounds(self.plan_year, self.plan_week)
		self.company = self.company or get_company()
		dup = frappe.db.sql(
			"""select name from `tabProduction Work Plan` where crop=%s and ifnull(farm,'')=%s
			and plan_year=%s and plan_week=%s and name != %s limit 1""",
			(self.crop, self.farm or "", self.plan_year, self.plan_week, self.name or ""),
		)
		if dup:
			frappe.throw(
				_("A plan already exists for this crop, farm and week: {0}").format(dup[0][0]),
				frappe.DuplicateEntryError,
			)
		self._guard_task_changes()
		supervisors.fill_plan_tasks(self)
		tol = get_tolerance_days()
		for t in self.tasks:
			t.deviation = task_deviation(
				t.status, t.due_date, t.completed_at, t.planned_qty, t.done_qty, tol
			) or ("Late" if t.postpone_count else "")  # a postponed task stays Late

	def _guard_task_changes(self):
		"""Removing a task or changing its date needs the reschedule permission, however the plan is saved."""
		before = self.get_doc_before_save()
		if self.is_new() or not before:
			return
		from frappe.utils import getdate

		from upande_production.production.logic import settings, task_schedule

		now = {r.name: r for r in self.tasks if r.name}
		removed = [r for r in before.tasks if r.name not in now]
		redated = [r for r in before.tasks if r.name in now
			and (getdate(r.due_date) if r.due_date else None)
			!= (getdate(now[r.name].due_date) if now[r.name].due_date else None)]
		if (removed or redated) and not settings.can_reschedule():
			frappe.throw(_("You are not permitted to change or delete planned tasks."), frappe.PermissionError)
		for r in removed:
			if task_schedule.has_work(r.name):
				frappe.throw(_("Work is recorded against this task; mark it Skipped instead."), frappe.ValidationError)
