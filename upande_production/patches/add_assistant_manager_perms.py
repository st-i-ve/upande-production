"""Production Assistant Manager rights on sites whose doctypes carry Custom DocPerm rows.

Frappe ignores a doctype's standard permission rows once it has Custom DocPerm rows (the avocado role setup
creates them), so the new role's standard rows are copied across. Idempotent.
"""

import frappe

ROLE = "Production Assistant Manager"


def execute():
	if not frappe.db.exists("Role", ROLE):
		frappe.get_doc({"doctype": "Role", "role_name": ROLE, "desk_access": 1}).insert(ignore_permissions=True)
	for dt in frappe.get_all("DocPerm", filters={"role": ROLE, "parenttype": "DocType"}, pluck="parent", distinct=True):
		if not frappe.db.exists("Custom DocPerm", {"parent": dt}):
			continue
		for d in frappe.get_all("DocPerm", fields="*", filters={"parent": dt, "role": ROLE}):
			if frappe.db.exists("Custom DocPerm", {"parent": dt, "role": ROLE, "permlevel": d.permlevel, "if_owner": d.if_owner}):
				continue
			row = frappe.new_doc("Custom DocPerm")
			row.update({k: v for k, v in d.items() if k not in ("name", "creation", "modified", "owner", "modified_by", "idx")})
			row.insert(ignore_permissions=True)
