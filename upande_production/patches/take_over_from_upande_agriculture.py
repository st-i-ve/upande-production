"""Take ownership of the field-execution doctypes that upande_agriculture used to ship.

On a site that ran upande_agriculture (live Margin Par) the rows already exist, with module
"Upande Agriculture". Flip them to this app's "Crop Production" module before the JSON sync so
migrate adopts the existing tables and every record survives. Crop Type and Agriculture
Settings may instead carry "Upande Propagation" (propagation shipped its own copies).

No-op on a fresh site: nothing matches, nothing is touched.
"""

import frappe

NEW_MODULE = "Crop Production"
OLD_MODULES = ("Upande Agriculture", "Upande Propagation")
OLD_APP, NEW_APP = "upande_agriculture", "upande_production"

DOCTYPES = [
	"Greenhouse", "Greenhouse Bed", "Greenhouse Bed Range", "Bed Range", "Greenhouse Variety",
	"Greenhouse Replanting Log", "Greenhouse Uprooting Log", "Replanting Log", "Uprooting Log",
	"Employee Greenhouse", "Item Greenhouses",
	"Crop Cycle", "Crop Cycle Bed", "Crop Cycle Uproot", "Crop Cycle Variety",
	"Crop Protocol", "Crop Protocol Flush", "Crop Protocol Grade Mix", "Crop Protocol Growth Stage",
	"Crop Protocol Length Distribution",
	"Cut Stage", "Bucket Reuse Anomaly", "Scan Location Mapping", "Scan Location Mapping Items",
	"Production Plan Form", "Production Plan Task", "Production Plan Variety",
	"Irrigation Plan Task", "Crop Protection Plan Task",
	"Crop Type", "Agriculture Settings",
]
# Rows of these doctypes that were exported with the roses workspaces.
WORKSPACES = ["Agriculture", "Roses Production"]
SIDEBARS = ["Roses Production"]


def _flip(doctype: str, names: list[str], with_app: bool = False):
	if not names or not frappe.db.has_table(doctype):
		return
	values = {"module": NEW_MODULE}
	if with_app and frappe.db.has_column(doctype, "app"):
		values["app"] = NEW_APP
	for name in names:
		if frappe.db.exists(doctype, name) and frappe.db.get_value(doctype, name, "module") in OLD_MODULES:
			frappe.db.set_value(doctype, name, values, update_modified=False)


def execute():
	_flip("DocType", DOCTYPES)
	_flip("Workspace", WORKSPACES, with_app=True)
	_flip("Workspace Sidebar", SIDEBARS, with_app=True)
	# Reports and Pages attached to the ported doctypes (none today, kept for completeness).
	if frappe.db.has_table("Report"):
		for name in frappe.get_all("Report", filters={"ref_doctype": ("in", DOCTYPES),
		                                              "module": ("in", OLD_MODULES)}, pluck="name"):
			frappe.db.set_value("Report", name, "module", NEW_MODULE, update_modified=False)
	frappe.db.commit()
