"""Cultural activity rows and plan tasks written before the field existed: times per week = 1."""

import frappe


def execute():
	for dt in ("Production Protocol Cultural Activity", "Work Plan Task"):
		frappe.reload_doctype(dt)
		frappe.db.sql(f"update `tab{dt}` set times_per_week = 1 where times_per_week is null or times_per_week < 1")
