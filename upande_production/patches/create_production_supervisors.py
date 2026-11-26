"""A Production Supervisor record for every Employee already used as a supervisor (block assignments, plan
tasks, casual labourers). Idempotent; existing records are left alone."""

import frappe

SOURCES = (
	("Production Supervisor Assignment", "supervisor"),
	("Work Plan Task", "supervisor"),
	("Casual Labourer", "supervisor"),
)


def execute():
	frappe.reload_doc("production", "doctype", "production_supervisor_crop")
	frappe.reload_doc("production", "doctype", "production_supervisor")
	used = set()
	for doctype, field in SOURCES:
		used.update(frappe.get_all(doctype, filters={field: ("is", "set")}, pluck=field, distinct=True))
	for emp in sorted(used):
		if frappe.db.exists("Production Supervisor", emp) or not frappe.db.exists("Employee", emp):
			continue
		frappe.get_doc({"doctype": "Production Supervisor", "employee": emp, "active": 1}).insert(ignore_permissions=True)
