import frappe

from upande_production.production.logic.crop_groups import CROP_GROUPS, STANDARD_GROUPS, ensure_groups, group_of  # noqa: F401

CROP = "Production Field Crop"
# every record type that carries field_crop and names its section in `crop`
LINKED = ("Production Variety", "Production Protocol", "Production Crop Cycle", "Production Harvest", "Harvest Batch",
	"Yield Sample", "Crop Forecast", "Buyer Commitment", "Harvest Grading Log")


def _avocado_crop(section):
	"""Make the crop for a single-crop section (Avocado) and put it on that section's records that lack one."""
	name = frappe.db.get_value("Production Crop", section, "crop_name") or section
	products = (frappe.get_all("Production Variety", filters={"crop": section, "product": ("is", "set")}, pluck="product", distinct=True)
		if frappe.db.has_column("Production Variety", "product") else [])
	if not frappe.db.exists(CROP, name):
		frappe.get_doc({"doctype": CROP, "crop_name": name, "crop_group": group_of(name) or "Fruit Crops",
			"product": products[0] if len(products) == 1 else None,
			"harvest_uom": "Kg", "enabled": 1}).insert(ignore_permissions=True)
	linked = 0
	for dt in LINKED:
		for row in frappe.get_all(dt, filters={"crop": section, "field_crop": ("is", "not set")}, pluck="name", limit_page_length=0):
			frappe.db.set_value(dt, row, "field_crop", name, update_modified=False)
			linked += 1
	return name, linked


def execute():
	"""The six standard crop groups, a group for every existing crop, and Avocado as a crop of its own.
	Idempotent: only empty values are filled and nothing is deleted."""
	for dt in ("Production Crop Group", "Production Sub Crop", CROP, *LINKED):
		frappe.reload_doc("production", "doctype", frappe.scrub(dt))
	made = ensure_groups()
	grouped, unknown = 0, []
	for c in frappe.get_all(CROP, fields=["name", "crop_group"]):
		if c.crop_group:
			continue
		group = group_of(c.name)
		if group:
			frappe.db.set_value(CROP, c.name, "crop_group", group, update_modified=False)
			grouped += 1
		else:
			unknown.append(c.name)
	avocado = {}
	for section in frappe.get_all("Production Crop", filters={"crop_key": "avocado"}, pluck="name"):
		name, linked = _avocado_crop(section)
		avocado[name] = linked
	msg = f"crop_hierarchy: groups made {made}, crops grouped {grouped}, avocado {avocado}"
	if unknown:
		msg += f"; crops without a group (set by hand): {unknown}"
	frappe.logger().info(msg)
	print(msg)
