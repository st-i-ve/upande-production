import frappe

OLD, NEW = "Field Crop", "Production Field Crop"
COPIED = ("crop_name", "product", "harvest_uom", "color", "enabled")


def copy_rows(old=OLD, new=NEW) -> int:
	"""Copy the rows of `old` into `new` (same name, crop_name, product, harvest_uom, color, enabled; the group
	comes from the standard map when the name is known), skipping names already in `new`. Returns rows copied."""
	from upande_production.patches import crop_hierarchy

	if not frappe.db.table_exists(old):
		return 0
	copied = 0
	for r in frappe.get_all(old, fields=["name", *COPIED], limit_page_length=0):
		if frappe.db.exists(new, r.name):
			continue
		doc = frappe.get_doc({"doctype": new, "crop_name": r.crop_name or r.name, **{k: r.get(k) for k in COPIED[1:]},
			"crop_group": crop_hierarchy.group_of(r.crop_name or r.name)})
		doc.flags.ignore_mandatory = True  # the group of an unknown crop is set by hand
		doc.flags.ignore_links = True
		doc.insert(ignore_permissions=True)
		copied += 1
	return copied


def execute():
	"""Field Crop became Production Field Crop (it was never deployed to a live site, so this only moves the
	records of a bench that already migrated it). Runs before the JSON sync, which then finds the renamed
	doctype instead of making a second, empty one. A no-op where Field Crop does not exist.
	When the new doctype already exists (something synced it first) the old one would be deleted as an orphan
	with its rows, so its rows are copied across first."""
	if frappe.db.get_value("DocType", OLD, "module") == "Production":
		if not frappe.db.exists("DocType", NEW):
			frappe.rename_doc("DocType", OLD, NEW, force=True, show_alert=False)
		else:
			print(f"rename_field_crop_doctype: copied {copy_rows()} rows of {OLD} into {NEW}")
	frappe.db.commit()
