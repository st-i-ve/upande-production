"""Production Variety.default_protocol is gone: a protocol points at its variety, never the reverse. Before
Frappe drops the column, any protocol a variety pointed at that has no variety of its own is stamped with that
variety, so nothing is lost. Idempotent; logs what it changed."""

import frappe


def execute():
	if not frappe.db.has_column("Production Variety", "default_protocol"):
		return
	rows = frappe.db.sql(
		"select name, default_protocol from `tabProduction Variety` where ifnull(default_protocol, '') != ''",
		as_dict=True)
	for r in rows:
		if not frappe.db.exists("Production Protocol", r.default_protocol):
			continue
		if frappe.db.get_value("Production Protocol", r.default_protocol, "variety"):
			continue
		frappe.db.set_value("Production Protocol", r.default_protocol, "variety", r.name, update_modified=False)
		print(f"clear_variety_default_protocol: protocol {r.default_protocol} now belongs to variety {r.name}")
