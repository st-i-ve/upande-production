"""Casual labour rework: hours are gone (pay is per unit of work), work gets a paid status, and the
roster is seeded from the employees designated "Casual Labourer".

* Any legacy hours > 0 is kept as an Info comment on the work record before the column is dropped.
* Idempotent: a second run finds no column, no new employees and no role rows to add.
"""

import frappe

DT = "Casual Labour Work"


def execute():
	frappe.reload_doc("production", "doctype", "casual_labourer_target")
	frappe.reload_doc("production", "doctype", "casual_labourer")
	frappe.reload_doc("production", "doctype", "casual_labour_work")
	frappe.reload_doc("production", "doctype", "field_operation")
	frappe.reload_doc("production", "doctype", "work_plan_task")

	noted = dropped = 0
	if frappe.db.has_column(DT, "hours"):
		rows = frappe.db.sql(f"select name, hours from `tab{DT}` where ifnull(hours, 0) > 0", as_dict=True)
		for r in rows:
			if frappe.db.exists("Comment", {"reference_doctype": DT, "reference_name": r.name,
					"comment_type": "Info", "content": ("like", "Hours recorded before hourly tracking was removed%")}):
				continue
			frappe.get_doc({
				"doctype": "Comment", "comment_type": "Info", "reference_doctype": DT, "reference_name": r.name,
				"content": f"Hours recorded before hourly tracking was removed: {r.hours:g}",
			}).insert(ignore_permissions=True)
			noted += 1
		frappe.db.sql_ddl(f"alter table `tab{DT}` drop column `hours`")
		dropped = 1
	if frappe.db.has_column(DT, "paid"):
		frappe.db.sql(f"update `tab{DT}` set paid = 'Unpaid' where ifnull(paid, '') = ''")

	seeded = 0
	for emp in frappe.get_all("Employee", filters={"designation": "Casual Labourer"}, pluck="name"):
		if not frappe.db.exists("Casual Labourer", emp):
			frappe.get_doc({"doctype": "Casual Labourer", "employee": emp,
				"active": 1 if frappe.db.get_value("Employee", emp, "status") == "Active" else 0}).insert(ignore_permissions=True)
			seeded += 1

	if frappe.db.exists("Role", "Avocado Production Manager"):
		from upande_production.production.logic.avocado_role import ensure_permissions
		ensure_permissions()
	frappe.db.commit()
	print(f"casual_labour_targets_and_paid: hours noted on {noted} record(s), column dropped: {bool(dropped)}, roster seeded with {seeded}")
