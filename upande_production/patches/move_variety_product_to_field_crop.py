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


def _variety_rows():
	"""[{name, field_crop, sub_crop, product}] read straight from the table: by now the model sync has dropped `product`
	from the doctype (its column stays), and `sub_crop` / `field_crop` may be missing on a site that never had them."""
	t = frappe.qb.DocType("Production Variety")
	cols = [c for c in ("field_crop", "sub_crop") if frappe.db.has_column("Production Variety", c)]
	q = frappe.qb.from_(t).select(t.name, t.product, *[t[c] for c in cols]).where(t.product.isnotnull() & (t.product != ""))
	rows = q.run(as_dict=True)
	for r in rows:
		for c in ("field_crop", "sub_crop"):
			r.setdefault(c, None)
	return rows


def execute():
	"""Production Variety.product goes away: the product of a variety is its sub-crop's, else its field crop's.
	Copies each variety's product into the field crop (sub-crop when set) that has none; never overwrites a different
	product (logged instead). Runs after the model sync and crop_hierarchy (so varieties are linked to their crop);
	the old column is read directly. A no-op where the column never existed."""
	if not frappe.db.has_column("Production Variety", "product"):
		return
	varieties = _variety_rows()
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
