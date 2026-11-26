import frappe
from frappe import _
from frappe.model.document import Document


class ProductionSupervisor(Document):
	"""The registry the supervisor dropdowns list. Stored supervisor values elsewhere stay Employee ids."""

	def validate(self):
		status = frappe.db.get_value("Employee", self.employee, "status")
		if self.active and status != "Active":
			frappe.throw(_("{0} is {1}; mark the record inactive.").format(self.employee, status or _("not active")),
				frappe.ValidationError)


def employee_updated(doc, method=None):
	"""An Employee who is no longer Active (Left, Inactive, Suspended) stops being an active supervisor."""
	if doc.status == "Active" or not frappe.db.get_value("Production Supervisor", doc.name, "active"):
		return
	frappe.db.set_value("Production Supervisor", doc.name, "active", 0)
	crops = frappe.get_all("Production Supervisor Crop", filters={"parent": doc.name, "parenttype": "Production Supervisor"}, pluck="crop")
	from upande_production.production.logic import supervisors

	try:
		supervisors.refresh_current_week(crops)
	except Exception:  # re-routing is a courtesy: it must never block an HR Employee save
		frappe.log_error(title="Supervisor re-route after Employee left failed")
