import frappe


def execute():
	"""Work submitted before approvals existed counts as approved."""
	frappe.db.sql(
		"""update `tabValue Adder Work` set approval_status = 'Approved',
		submitted_by = ifnull(submitted_by, owner), reviewed_by = ifnull(reviewed_by, owner),
		reviewed_at = ifnull(reviewed_at, modified) where docstatus = 1 and ifnull(approval_status, '') != 'Approved'"""
	)
	frappe.db.sql(
		"update `tabValue Adder Work` set submitted_by = owner where ifnull(submitted_by, '') = ''"
	)
