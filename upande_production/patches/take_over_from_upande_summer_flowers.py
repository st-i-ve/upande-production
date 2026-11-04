"""Take ownership of the field-side doctypes that upande_summer_flowers used to ship.

On Margin Par the rows already exist, either from that app or as custom DocTypes (custom = 1) mirrored from
live with real data, module "Summer Flowers". Flip them to this app's "Crop Production" module and clear
`custom` before the JSON sync, so migrate adopts the existing tables and every record survives. NEVER
delete or recreate one of these: that drops the table. The same for the reports, and for the custom fields
and property setters on the doctypes production owns (Crop Cycle, Crop Protocol, Bed, Block, Farm, Item), which
this app now ships under crop_production/custom.

No-op on a fresh site and on Mutara: nothing is in module "Summer Flowers".
"""

import frappe

OLD_MODULE, NEW_MODULE = "Summer Flowers", "Crop Production"

DOCTYPES = [
	"Planting Calendar", "Planting Calendar Bed", "Planting Calendar Flush",
	"Field Activity", "Crop Field Activity",
	"Crop Protocol Version", "Crop Protocol Way", "Crop Protocol Way Stage",
	"Summer Flower Protocol", "Summer Flower Protocol Flush", "Summer Flower Protocol Grade",
	"Summer Flower Protocol Lift", "Summer Flower Second Way",
	"Crop Cycle Weekly Target", "Bed Work Order", "Bed Work Progress",
	"Block Change Request", "Block Change Result", "Block Change Source", "Block Area Revision", "Block Bed",
	"Summer Flower Growth Stage", "Summer Flower Settings", "Summer Flower Approver Role",
]
REPORTS = ["Crop Protocol Yield", "Summer Flower Planting Slippage"]
CUSTOMISED = ["Crop Cycle", "Crop Protocol", "Bed", "Block", "Farm", "Item"]


def execute():
	if not frappe.db.has_table("DocType"):
		return
	for name in DOCTYPES:
		# only a Field Activity that really is summer_flowers' own: never touch another module's
		if frappe.db.get_value("DocType", name, "module") == OLD_MODULE:
			frappe.db.set_value("DocType", name, {"module": NEW_MODULE, "custom": 0}, update_modified=False)
	for name in REPORTS:
		if frappe.db.exists("Report", name) and frappe.db.get_value("Report", name, "module") == OLD_MODULE:
			frappe.db.set_value("Report", name, "module", NEW_MODULE, update_modified=False)
	for dt in CUSTOMISED:
		for doctype, field in (("Custom Field", "dt"), ("Property Setter", "doc_type")):
			frappe.db.sql(
				f"update `tab{doctype}` set module=%s where `{field}`=%s and module=%s",
				(NEW_MODULE, dt, OLD_MODULE),
			)
	frappe.db.commit()
