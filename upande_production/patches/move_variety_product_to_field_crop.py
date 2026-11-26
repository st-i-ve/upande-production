import frappe

DT, SUB = "Production Field Crop", "Production Sub Crop"


def plan(varieties, crop_products, sub_products):
	"""(changes, conflicts) for moving each variety's product onto its sub-crop (when it has one) or its field crop.

	`varieties` is [{"name", "field_crop", "sub_crop", "product"}]; `crop_products` and `sub_products` map a crop /
	sub-crop name to the product it already has. A target without a product takes the variety's; a target that has a
	different product keeps it and the clash is reported. Changes are [(doctype, name, product)], each target once."""
	changes, conflicts, claimed = [], [], {}
	for v in varieties:
		product = v.get("product")
		if not product:
			continue
		sub = v.get("sub_crop")
		target = (SUB, sub, sub_products) if sub else (DT, v.get("field_crop"), crop_products) if v.get("field_crop") else None
		if not target:
			continue
		doctype, name, existing = target
		have = existing.get(name) or claimed.get((doctype, name))
		if not have:
			claimed[(doctype, name)] = product
			changes.append((doctype, name, product))
		elif have != product:
			conflicts.append({"variety": v["name"], "doctype": doctype, "target": name, "variety_product": product, "kept": have})
	return changes, conflicts


def execute():
	"""Production Variety.product goes away: the product of a variety is its sub-crop's, else its field crop's.
	Copies each variety's product into the field crop (sub-crop when set) that has none; never overwrites a different
	product (logged instead). Runs before the model sync drops the field; a no-op once the column is gone."""
	if not frappe.db.has_column("Production Variety", "product"):
		return
	varieties = frappe.get_all("Production Variety", filters={"product": ("is", "set")},
		fields=["name", "field_crop", "sub_crop", "product"], limit_page_length=0)
	crop_products = dict(frappe.get_all(DT, fields=["name", "product"], as_list=True, limit_page_length=0))
	sub_products = dict(frappe.get_all(SUB, fields=["name", "product"], as_list=True, limit_page_length=0)) \
		if frappe.db.table_exists(SUB) else {}
	changes, conflicts = plan(varieties, crop_products, sub_products)
	log = frappe.logger("patches")
	for doctype, name, product in changes:
		frappe.db.set_value(doctype, name, "product", product, update_modified=False)
		log.info(f"move_variety_product_to_field_crop: {doctype} {name} product set to {product}")
		print(f"move_variety_product_to_field_crop: {doctype} {name} product = {product}")
	for c in conflicts:
		log.warning(f"move_variety_product_to_field_crop: {c['variety']} has product {c['variety_product']} but "
			f"{c['doctype']} {c['target']} keeps {c['kept']}")
		print(f"move_variety_product_to_field_crop: CONFLICT {c['variety']} product {c['variety_product']}, "
			f"{c['doctype']} {c['target']} keeps {c['kept']}")
	skipped = [v["name"] for v in varieties if not v.get("field_crop") and not v.get("sub_crop")]
	if skipped:
		print(f"move_variety_product_to_field_crop: no crop to take the product of: {', '.join(skipped)}")
	print(f"move_variety_product_to_field_crop: {len(changes)} set, {len(conflicts)} conflicts, {len(skipped)} without a crop")
