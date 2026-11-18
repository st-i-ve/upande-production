import frappe
from frappe.tests import IntegrationTestCase


class TestEmployeeLinksIgnoreUserPermissions(IntegrationTestCase):
	"""HRMS gives every user an Employee user permission on their own record (applied to all doctypes). On
	production records an Employee link names a labourer, an operator or a supervisor, not the viewer, so it must
	not filter them: a manager tied to their own Employee still sees everybody's labour, crates and runs."""

	def test_every_production_employee_link_ignores_user_permissions(self):
		missing = []
		for dt in frappe.get_all("DocType", filters={"module": ("in", ["Production"])}, pluck="name"):
			for f in frappe.get_meta(dt).fields:
				if f.fieldtype == "Link" and f.options == "Employee" and not f.ignore_user_permissions:
					missing.append(f"{dt}.{f.fieldname}")
		self.assertEqual(missing, [])
