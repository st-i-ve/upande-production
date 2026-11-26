import frappe
from frappe import _
from frappe.model.document import Document


class ProductionSupervisor(Document):
	"""The registry the supervisor dropdowns list. Stored supervisor values elsewhere stay Employee ids."""

	def validate(self):
		if frappe.db.get_value("Employee", self.employee, "status") == "Left":
			frappe.throw(_("{0} has left and cannot be a supervisor.").format(self.employee), frappe.ValidationError)
