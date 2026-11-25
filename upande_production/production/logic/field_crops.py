"""Field Crops: the named crops inside a farm section (Cabbage, Maize, Onion ... inside Fruits & Vegetables).

A section (Production Crop) that has Field Crops keeps its pivots, blocks, operations, labour and one weekly
plan; every variety, protocol, cycle and harvest under it says which Field Crop it is, and harvests are
counted in that crop's own unit (Pieces for cabbage, Kg for the rest). Totals are therefore always kept per
Field Crop and per unit, never added across units.
"""

import frappe
from frappe import _
from frappe.utils import flt

DT = "Production Field Crop"
DEFAULT_UOM = "Kg"


def has_field_crops(section) -> bool:
	"""True when the section has MORE THAN ONE crop (Fruits & Vegetables). A single-crop section (Avocado) keeps its
	pages as they are; its crop is filled in silently (see only_crop). Task 2 refines this."""
	return bool(section) and len(crops_of(section)) > 1


def only_crop(section):
	"""The crop of a section that has exactly one, else None."""
	crops = crops_of(section)
	return crops[0] if len(crops) == 1 else None


def crops_of(section) -> list:
	"""The distinct enabled crops of a section's varieties."""
	if not section:
		return []
	names = frappe.get_all("Production Variety", filters={"crop": section, "field_crop": ("is", "set")}, pluck="field_crop", distinct=True)
	return frappe.get_all(DT, filters={"name": ("in", names), "enabled": 1}, pluck="name") if names else []


def list_for(section, enabled_only=False) -> list:
	names = frappe.get_all("Production Variety", filters={"crop": section, "field_crop": ("is", "set")}, pluck="field_crop", distinct=True)
	filters = {"name": ("in", names or [""])}
	if enabled_only:
		filters["enabled"] = 1
	return frappe.get_all(DT, filters=filters, fields=["name", "crop_name", "crop_group", "product", "harvest_uom", "color", "enabled"],
		order_by="crop_name asc", limit_page_length=0)


def harvest_uom(field_crop, default=None):
	if not field_crop:
		return default
	return frappe.db.get_value(DT, field_crop, "harvest_uom") or default


def singular(name: str) -> str:
	"""'Potatoes' -> 'Potato', 'Tomatoes' -> 'Tomato'; names that are not a plain plural are kept."""
	n = (name or "").strip()
	low = n.lower()
	if low.endswith("oes") and len(n) > 4:
		return n[:-2]
	if low.endswith("ies") and len(n) > 4:
		return n[:-3] + "y"
	return n


def from_variety(variety):
	return frappe.db.get_value("Production Variety", variety, "field_crop") if variety else None


def from_item(item, section=None):
	"""The Field Crop an item belongs to: a variety's own item, a field crop's product item, or a variety's product."""
	if not item:
		return None
	row = frappe.db.get_value("Production Variety", {"item": item}, "field_crop")
	if row:
		return row
	row = frappe.db.get_value(DT, {"product": item}, "name")
	if row:
		return row
	return frappe.db.get_value("Production Variety", {"product": item, "field_crop": ("is", "set")}, "field_crop")


def check_section(field_crop, section):
	"""A crop is no longer tied to one section (any section's varieties may name it), so nothing to check."""
	return


def for_unit(unit, section=None):
	"""The Field Crop of the block's current cycle (else its latest cycle that has one)."""
	if not unit:
		return None
	row = frappe.db.get_value("Production Crop Cycle", {"unit": unit, "status": ("in", ("Active", "Harvesting")), "field_crop": ("is", "set")},
		"field_crop", order_by="start_date desc")
	if row:
		return row
	return frappe.db.get_value("Production Crop Cycle", {"unit": unit, "field_crop": ("is", "set")}, "field_crop", order_by="start_date desc")


def stamp(doc, *, cycle_field="cycle", with_uom=False) -> None:
	"""Fill `field_crop` on a record from its cycle, else its item, else the block's current cycle. Leaves a value
	already set. With `with_uom` the record's `uom` follows the Field Crop's harvest unit when that is set."""
	if not doc.meta.has_field("field_crop"):
		return
	if not doc.get("field_crop"):
		fc = None
		if doc.get(cycle_field):
			fc = frappe.db.get_value("Production Crop Cycle", doc.get(cycle_field), "field_crop")
		if not fc and doc.meta.has_field("item") and doc.get("item"):
			fc = from_item(doc.item, doc.get("crop"))
		if not fc and doc.get("unit") and has_field_crops(doc.get("crop") or frappe.db.get_value("Production Unit", doc.unit, "crop")):
			fc = for_unit(doc.unit)
		if not fc:
			fc = only_crop(doc.get("crop") or (frappe.db.get_value("Production Unit", doc.unit, "crop") if doc.get("unit") else None))
		doc.field_crop = fc
	if doc.field_crop:
		check_section(doc.field_crop, doc.get("crop"))
		if with_uom and doc.meta.has_field("uom"):
			uom = harvest_uom(doc.field_crop)
			if uom:
				doc.uom = uom


def stamp_doc_event(doc, method=None):
	"""doc_events hook for records that only carry the Field Crop for reports (samples, forecasts, commitments, grading)."""
	stamp(doc, with_uom=doc.doctype in ("Yield Sample", "Crop Forecast", "Buyer Commitment"))


def require_on_cycle(doc) -> None:
	if not doc.get("field_crop") and has_field_crops(doc.get("crop")):
		frappe.throw(_("Choose the crop of this cycle (the section {0} has crops).").format(doc.crop), frappe.ValidationError)


def totals_by_crop(rows, qty_key="qty", crop_key="field_crop", uom_key="uom") -> list:
	"""[{field_crop, uom, qty}] from rows, one line per (field crop, unit): units are never added together."""
	out = {}
	for r in rows:
		k = (r.get(crop_key) or "", r.get(uom_key) or "")
		out[k] = out.get(k, 0) + flt(r.get(qty_key))
	return [{"field_crop": fc or None, "uom": u or None, "qty": q} for (fc, u), q in sorted(out.items())]


# -- creating Field Crops from varieties, and linking existing records (the patch) ------------------


PIECE_CROPS = {"cabbage"}  # counted by the head
PIECES = "Pieces"


def _default_uom(item_name, stock_uom):
	if (item_name or "").strip().lower() in PIECE_CROPS and frappe.db.exists("UOM", PIECES):
		return PIECES
	return stock_uom or DEFAULT_UOM


def align_item_uom(item, uom) -> bool:
	"""Make the item's stock unit the crop's harvest unit while nothing has been stocked in the old one."""
	if not item or not uom:
		return False
	current = frappe.db.get_value("Item", item, "stock_uom")
	if current == uom or frappe.db.exists("Stock Ledger Entry", {"item_code": item}) or frappe.db.exists("Bin", {"item_code": item}):
		return False
	frappe.db.set_value("Item", item, "stock_uom", uom, update_modified=False)
	return True


def align_items(field_crop) -> None:
	"""align_item_uom for the Field Crop's product item and the items of its varieties."""
	uom, product = frappe.db.get_value(DT, field_crop, ["harvest_uom", "product"])
	items = set(frappe.get_all("Production Variety", filters={"field_crop": field_crop}, pluck="item"))
	if product:
		items.add(product)
	for item in items:
		align_item_uom(item, uom)


def crop_for_product(product):
	"""The crop of an item: by its product item, else by the singular of its item name."""
	if not product:
		return None
	name = frappe.db.get_value(DT, {"product": product}, "name")
	if name:
		return name
	item_name = frappe.db.get_value("Item", product, "item_name") or product
	return frappe.db.get_value(DT, {"crop_name": singular(item_name)}, "name")


def create_from_varieties(min_products=2) -> list:
	"""A crop per distinct product item of each section whose varieties grow `min_products` or more products
	(a mixed section such as Fruits & Vegetables). Crops are matched by name, not by section. A new crop gets its
	group from the standard map when the name is known (else crop_hierarchy sets or lists it). Returns the names
	of the crops made now."""
	from upande_production.patches import crop_hierarchy

	crop_hierarchy.ensure_groups()
	made = []
	for section in frappe.get_all("Production Crop", pluck="name"):
		products = frappe.get_all("Production Variety", filters={"crop": section, "product": ("is", "set")}, pluck="product", distinct=True)
		if len(products) < min_products:
			continue
		for product in products:
			if frappe.db.exists(DT, {"product": product}):
				continue
			item_name, stock_uom = frappe.db.get_value("Item", product, ["item_name", "stock_uom"]) or (product, None)
			name = singular(item_name or product)
			if frappe.db.exists(DT, name):
				if not frappe.db.get_value(DT, name, "product"):
					frappe.db.set_value(DT, name, "product", product)
				continue
			doc = frappe.get_doc({"doctype": DT, "crop_name": name, "crop_group": crop_hierarchy.group_of(name), "product": product,
				"harvest_uom": _default_uom(item_name, stock_uom), "enabled": 1})
			doc.flags.ignore_mandatory = True  # the group of an unknown crop is set by hand
			doc.insert(ignore_permissions=True)
			made.append(doc.name)
	return made


def link_records() -> dict:
	"""Set `field_crop` on the varieties, protocols, cycles, harvests and report records that lack it.
	Returns {doctype: rows updated}. Safe to run again: only empty links are filled."""
	counts = {}

	def setv(doctype, name, fc):
		frappe.db.set_value(doctype, name, "field_crop", fc, update_modified=False)
		counts[doctype] = counts.get(doctype, 0) + 1

	if not frappe.db.count(DT):
		return counts
	for v in frappe.get_all("Production Variety", filters={"field_crop": ("is", "not set"), "product": ("is", "set")},
			fields=["name", "product"]):
		fc = crop_for_product(v.product)
		if fc:
			setv("Production Variety", v.name, fc)
	sections = list(set(frappe.get_all("Production Variety", filters={"field_crop": ("is", "set")}, pluck="crop")))
	if not sections:
		return counts
	for p in frappe.get_all("Production Protocol", filters={"crop": ("in", sections), "field_crop": ("is", "not set")},
			fields=["name", "crop", "item", "variety"]):
		fc = from_variety(p.variety) or from_item(p.item, p.crop)
		if fc:
			setv("Production Protocol", p.name, fc)
	for c in frappe.get_all("Production Crop Cycle", filters={"crop": ("in", sections), "field_crop": ("is", "not set")},
			fields=["name", "crop", "item", "variety"]):
		fc = from_variety(c.variety) or from_item(c.item, c.crop)
		if fc:
			setv("Production Crop Cycle", c.name, fc)
	cycle_crop = dict(frappe.get_all("Production Crop Cycle", filters={"field_crop": ("is", "set")}, fields=["name", "field_crop"], as_list=True))
	for doctype in ("Production Harvest", "Harvest Batch", "Yield Sample", "Crop Forecast", "Harvest Grading Log", "Buyer Commitment"):
		fields = ["name", "crop"] + (["cycle"] if frappe.get_meta(doctype).has_field("cycle") else []) \
			+ (["item"] if frappe.get_meta(doctype).has_field("item") else []) \
			+ (["unit"] if frappe.get_meta(doctype).has_field("unit") else [])
		for r in frappe.get_all(doctype, filters={"crop": ("in", sections), "field_crop": ("is", "not set")}, fields=fields,
				limit_page_length=0):
			fc = cycle_crop.get(r.get("cycle")) or from_item(r.get("item"), r.crop) or (for_unit(r.get("unit")) if r.get("unit") else None)
			if fc:
				setv(doctype, r.name, fc)
	return counts


# -- reading ---------------------------------------------------------------------------------------


def label(field_crop, variety=None) -> str | None:
	"""'Cabbage (Gloria F1)': the text a cycle or a task carries on the screens."""
	if not field_crop:
		return variety or None
	return f"{field_crop} ({variety})" if variety else field_crop


def annotate_cycles(rows, cycle_key="cycle") -> None:
	"""Add field_crop, variety and crop_label to rows (dicts) that point at a cycle."""
	names = list({r.get(cycle_key) for r in rows if r.get(cycle_key)})
	info = {}
	if names:
		info = {c.name: c for c in frappe.get_all("Production Crop Cycle", filters={"name": ("in", names)},
			fields=["name", "field_crop", "variety"], limit_page_length=0)}
	for r in rows:
		c = info.get(r.get(cycle_key))
		r["field_crop"] = c.field_crop if c else None
		r["variety"] = c.variety if c else None
		r["crop_label"] = label(r["field_crop"], r["variety"])


def with_units(section=None) -> dict:
	"""{field_crop: {"uom", "color"}} for the section (all sections when empty)."""
	filters = {}
	if section:
		names = frappe.get_all("Production Variety", filters={"crop": section, "field_crop": ("is", "set")}, pluck="field_crop", distinct=True)
		filters = {"name": ("in", names or [""])}
	return {r.name: {"uom": r.harvest_uom, "color": r.color} for r in frappe.get_all(DT, filters=filters, fields=["name", "harvest_uom", "color"], limit_page_length=0)}


def harvest_by_crop(rows) -> list:
	"""[{field_crop, uom, qty}] one line per Field Crop and unit, from rows with field_crop, uom and qty."""
	return totals_by_crop(rows)
