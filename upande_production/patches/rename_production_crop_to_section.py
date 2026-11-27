import frappe

OLD, NEW = "Production Crop", "Production Section"

# Places that store a doctype name as a plain value, which rename_doc does not know about (it follows
# Link fields, Dynamic Links, Custom Fields and Property Setters, and the child rows' parenttype).
# (doctype, field) pairs; all are skipped when the table is not there.
VALUE_FIELDS = (
	("Workspace Link", "link_to"),
	("Workspace Sidebar Item", "link_to"),
	("Desktop Icon", "link_to"),
	("DocPerm", "parent"),
	("Custom DocPerm", "parent"),
	("User Permission", "allow"),
	("Comment", "reference_doctype"),
	("Version", "ref_doctype"),
	("File", "attached_to_doctype"),
	("Number Card", "document_type"),
	("Dashboard Chart", "document_type"),
	("Dynamic Link", "link_doctype"),
)


def copy_rows(old=OLD, new=NEW) -> int:
	"""Copy the rows of `old` (children included) into `new`, skipping names already in `new`. Returns rows copied."""
	if not frappe.db.table_exists(old):
		return 0
	copied = 0
	for name in frappe.get_all(old, pluck="name", limit_page_length=0):
		if frappe.db.exists(new, name):
			continue
		doc = frappe.copy_doc(frappe.get_doc(old, name))
		doc.doctype = new
		doc.name = name
		doc.flags.ignore_mandatory = True
		doc.flags.ignore_links = True
		doc.flags.name_set = True
		doc.insert(ignore_permissions=True)
		copied += 1
	return copied


def fix_stored_names(old=OLD, new=NEW) -> None:
	for doctype, field in VALUE_FIELDS:
		if not frappe.db.table_exists(doctype) or not frappe.db.has_column(doctype, field):
			continue
		table = frappe.qb.DocType(doctype)
		frappe.qb.update(table).set(table[field], new).where(table[field] == old).run()


def execute():
	"""Production Crop became Production Section (it is a farm section such as Phases or Pivots, not a crop; the
	crops are Production Field Crop). Renames the doctype in place before the JSON sync, keeping every record,
	Link field (the fieldnames stay) and child row, then fixes the stored doctype names rename_doc leaves.
	A no-op where Production Crop does not exist or the work is done.
	When the new doctype already exists (something synced it first) the old one would be deleted as an orphan
	with its rows, so its rows are copied across first."""
	if frappe.db.get_value("DocType", OLD, "module") == "Production":
		if not frappe.db.exists("DocType", NEW):
			frappe.rename_doc("DocType", OLD, NEW, force=True, show_alert=False)
		else:
			print(f"rename_production_crop_to_section: copied {copy_rows()} rows of {OLD} into {NEW}")
	fix_stored_names()
	frappe.db.commit()
