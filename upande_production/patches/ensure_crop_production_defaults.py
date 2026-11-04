"""Idempotent set-up the ported field-execution code relies on (post model sync).

Folds the useful, non-historic parts of upande_agriculture's v1_0 patches into one:
  - Crop Type records the Crop Protocol link expects (Rose, Spray Rose, Summer Flower, Other)
  - Bed.status / Bed.plant_count mirror fields (Bed belongs to another app, so they are Custom
    Fields), including the "Partially Uprooted" option. Skipped on sites without Bed.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

CROP_TYPES = ("Rose", "Spray Rose", "Summer Flower", "Other")
STATUS_OPTIONS = "Empty\nPlanted\nProducing\nHarvesting\nTransplanted\nPartially Uprooted\nUprooted"


def execute():
	for name in CROP_TYPES:
		if not frappe.db.exists("Crop Type", name):
			frappe.get_doc({"doctype": "Crop Type", "crop_type_name": name}).insert(ignore_permissions=True)

	if not frappe.db.exists("DocType", "Bed"):
		return
	meta = frappe.get_meta("Bed")
	fields = []
	if not meta.has_field("status"):
		fields.append({
			"fieldname": "status", "fieldtype": "Select", "label": "Status", "options": STATUS_OPTIONS,
			"insert_after": "variety", "in_list_view": 1, "in_standard_filter": 1, "read_only": 1,
			"description": "Mirrored from the Greenhouse bed ledger on every save there.",
		})
	elif "Partially Uprooted" not in (frappe.db.get_value("Custom Field", "Bed-status", "options") or ""):
		if frappe.db.exists("Custom Field", "Bed-status"):
			frappe.db.set_value("Custom Field", "Bed-status", "options", STATUS_OPTIONS)
	if not meta.has_field("plant_count"):
		fields.append({
			"fieldname": "plant_count", "fieldtype": "Int", "label": "Plant Count",
			"insert_after": "status", "in_list_view": 1, "read_only": 1, "non_negative": 1,
			"description": "Mirrored from the Greenhouse bed ledger on every save there.",
		})
	if fields:
		create_custom_fields({"Bed": fields})
	frappe.clear_cache(doctype="Bed")
