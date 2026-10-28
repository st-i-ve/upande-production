# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

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
		tol = get_tolerance_days()
		for t in self.tasks:
			t.deviation = task_deviation(
				t.status, t.due_date, t.completed_at, t.planned_qty, t.done_qty, tol
			)
