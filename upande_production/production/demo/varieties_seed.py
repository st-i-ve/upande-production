"""Idempotent demo data for varieties, growth stages and per-variety protocols (Mutara).

bench --site mutara.local execute upande_production.production.demo.varieties_seed.run

Creates a stock Item per variety, the Production Variety with its stages, one Active v1 protocol per
variety (copied from the product's Active protocol and adjusted), sets operation categories, then fixes
the existing data: every Avocado / Fruits & Vegetables cycle gets a variety, its item and protocol and a
computed current stage, pond stockings get a strain, and F&V harvest records / grading logs follow the
cycle's variety item. Every invented figure is in DEMO below.
"""

import frappe
from frappe.utils import add_days, cint, getdate, today

from upande_production.patches import convert_protocol_steps
from upande_production.production.logic import stages

# stage = (name, start_day, length_days[, is_harvest])
DEMO = {
	"item_group": "Products",
	"operation_categories": {
		"Pruning": "Pruning", "Passion Pruning": "Pruning", "Fertiliser Application": "Fertilising",
		"Top Dressing": "Fertilising", "Irrigation Check": "Irrigation", "Weeding": "Weeding",
		"Spraying": "Spraying", "Harvest Picking": "Harvesting", "Harvest": "Harvesting",
		"Honey Harvest": "Harvesting", "Feeding": "Feeding",
	},  # every other operation is "Other"
	# crop -> list of varieties. `base_protocol` is the product protocol copied (None: keep/own);
	# `timing` {operation: (day_offset, repeat_every, repeat_count)} replaces those steps' timing;
	# `drop` operations removed from the copy; `anchored` extra steps
	# (operation, anchor_stage, day_offset, repeat_every, repeat_count, planned_qty, note).
	"varieties": [
		{"name": "Shangi", "crop": "Fruits & Vegetables", "product": "Potatoes", "item": "Potatoes - Shangi",
		 "anchor": "Planting", "first_harvest": 90, "window": 15, "yield_ha": 25000, "plants_ha": 44000, "yield_plant": 0.57,
		 "stages": [("Planting", 0, 7), ("Emergence", 7, 14), ("Vegetative", 21, 17), ("Tuber initiation", 38, 12),
			("Bulking", 50, 25), ("Maturation", 75, 15), ("Harvest", 90, 15, 1)],
		 "base_protocol": "Potato", "timing": {"Weeding": (18, 18, 2), "Harvest": (90, 0, 1)}, "drop": ["Top Dressing"],
		 "anchored": [("Top Dressing", "Vegetative", 10, 0, 1, 120, "Top-dress with CAN at 10 days into the vegetative stage")],
		 "notes": "Early, fast-bulking; the main table and chips potato for the Nairobi market."},
		{"name": "Dutch Robjin", "crop": "Fruits & Vegetables", "product": "Potatoes", "item": "Potatoes - Dutch Robjin",
		 "anchor": "Planting", "first_harvest": 105, "window": 15, "yield_ha": 30000, "plants_ha": 44000, "yield_plant": 0.68,
		 "stages": [("Planting", 0, 7), ("Emergence", 7, 14), ("Vegetative", 21, 19), ("Tuber initiation", 40, 15),
			("Bulking", 55, 35), ("Maturation", 90, 15), ("Harvest", 105, 15, 1)],
		 "base_protocol": "Potato", "timing": {"Spraying": (14, 7, 8), "Harvest": (105, 0, 1)}, "drop": ["Top Dressing"],
		 "anchored": [("Top Dressing", "Vegetative", 10, 0, 1, 120, "Top-dress at 10 days into the vegetative stage")],
		 "notes": "Late, high-yielding and blight-susceptible: tighter spray rounds."},
		{"name": "Markies", "crop": "Fruits & Vegetables", "product": "Potatoes", "item": "Potatoes - Markies",
		 "anchor": "Planting", "first_harvest": 100, "window": 15, "yield_ha": 28000, "plants_ha": 44000, "yield_plant": 0.64,
		 "stages": [("Planting", 0, 7), ("Emergence", 7, 14), ("Vegetative", 21, 19), ("Tuber initiation", 40, 15),
			("Bulking", 55, 30), ("Maturation", 85, 15, 0), ("Harvest", 100, 15, 1)],
		 "base_protocol": "Potato", "timing": {"Harvest": (100, 0, 1)}, "drop": ["Top Dressing"],
		 "anchored": [("Top Dressing", "Vegetative", 10, 0, 1, 120, "Top-dress at 10 days into the vegetative stage")],
		 "notes": "Processing potato (crisps); haulm is killed in maturation."},
		{"name": "Gloria F1", "crop": "Fruits & Vegetables", "product": "Cabbage", "item": "Cabbage - Gloria F1",
		 "anchor": "Planting", "first_harvest": 80, "window": 14, "yield_ha": 55000, "plants_ha": 33000, "yield_plant": 1.67,
		 "stages": [("Transplanting", 0, 7), ("Establishment", 7, 18), ("Vegetative", 25, 20), ("Head formation", 45, 20),
			("Head maturation", 65, 15), ("Harvest", 80, 14, 1)],
		 "base_protocol": "Cabbage", "timing": {"Harvest": (80, 0, 1)}, "drop": ["Top Dressing"],
		 "anchored": [("Top Dressing", "Establishment", 10, 0, 1, 120, "First top-dress"),
			("Top Dressing", "Head formation", 0, 0, 1, 120, "Second top-dress at head initiation")],
		 "notes": "Hybrid, compact heads, early."},
		{"name": "Copenhagen Market", "crop": "Fruits & Vegetables", "product": "Cabbage", "item": "Cabbage - Copenhagen Market",
		 "anchor": "Planting", "first_harvest": 90, "window": 14, "yield_ha": 45000, "plants_ha": 33000, "yield_plant": 1.36,
		 "stages": [("Transplanting", 0, 7), ("Establishment", 7, 21), ("Vegetative", 28, 22), ("Head formation", 50, 22),
			("Head maturation", 72, 18), ("Harvest", 90, 14, 1)],
		 "base_protocol": "Cabbage", "timing": {"Harvest": (90, 0, 1), "Spraying": (10, 10, 6)}, "drop": [],
		 "anchored": [("Top Dressing", "Head formation", 0, 0, 1, 120, "Second top-dress at head initiation")],
		 "notes": "Open-pollinated, larger heads."},
		{"name": "Red Creole", "crop": "Fruits & Vegetables", "product": "Onion", "item": "Onion - Red Creole",
		 "anchor": "Planting", "first_harvest": 120, "window": 20, "yield_ha": 30000, "plants_ha": 400000, "yield_plant": 0.075,
		 "stages": [("Transplanting", 0, 7), ("Establishment", 7, 23), ("Vegetative", 30, 30), ("Bulb initiation", 60, 20),
			("Bulb bulking", 80, 25), ("Maturation", 105, 15), ("Harvest", 120, 20, 1)],
		 "base_protocol": "Onion", "timing": {}, "drop": [],
		 "anchored": [("Top Dressing", "Establishment", 14, 0, 1, 120, "Top-dress with CAN")],
		 "notes": "Standard Kenyan red onion, good storage."},
		{"name": "Red Pinoy F1", "crop": "Fruits & Vegetables", "product": "Onion", "item": "Onion - Red Pinoy F1",
		 "anchor": "Planting", "first_harvest": 105, "window": 20, "yield_ha": 38000, "plants_ha": 400000, "yield_plant": 0.095,
		 "stages": [("Transplanting", 0, 7), ("Establishment", 7, 18), ("Vegetative", 25, 25), ("Bulb initiation", 50, 20),
			("Bulb bulking", 70, 22), ("Maturation", 92, 13), ("Harvest", 105, 20, 1)],
		 "base_protocol": "Onion", "timing": {"Harvest": (105, 0, 1), "Spraying": (15, 12, 5), "Weeding": (22, 18, 3)}, "drop": [],
		 "anchored": [("Top Dressing", "Vegetative", 7, 0, 1, 120, "Top-dress with CAN")],
		 "notes": "Hybrid, earlier and higher yielding."},
		{"name": "Purple", "crop": "Fruits & Vegetables", "product": "Passion Fruit", "item": "Passion Fruit - Purple",
		 "anchor": "Planting", "first_harvest": 170, "window": 270, "yield_ha": 12000, "plants_ha": 1600, "yield_plant": 7.5,
		 "stages": [("Planting", 0, 14), ("Establishment", 14, 46), ("Vegetative", 60, 50), ("Flowering", 110, 30),
			("Fruit development", 140, 30), ("Harvest", 170, 270, 1)],
		 "base_protocol": "Passion", "timing": {"Spraying": (0, 30, 12)}, "drop": ["Passion Pruning", "Harvest"],
		 "anchored": [("Passion Pruning", "Vegetative", 0, 90, 4, 600, "Training and pruning on the trellis"),
			("Harvest", "Harvest", 0, 14, 26, 150, "Fortnightly picking")],
		 "notes": "Purple passion fruit: the export and juice standard."},
		{"name": "Sweet Yellow", "crop": "Fruits & Vegetables", "product": "Passion Fruit", "item": "Passion Fruit - Sweet Yellow",
		 "anchor": "Planting", "first_harvest": 150, "window": 270, "yield_ha": 15000, "plants_ha": 1600, "yield_plant": 9.4,
		 "stages": [("Planting", 0, 14), ("Establishment", 14, 36), ("Vegetative", 50, 45), ("Flowering", 95, 25),
			("Fruit development", 120, 30), ("Harvest", 150, 270, 1)],
		 "base_protocol": "Passion", "timing": {"Spraying": (0, 28, 13)}, "drop": ["Passion Pruning", "Harvest"],
		 "anchored": [("Passion Pruning", "Vegetative", 0, 90, 4, 600, "Training and pruning on the trellis"),
			("Harvest", "Harvest", 0, 12, 30, 150, "Picking every 12 days")],
		 "notes": "Sweeter yellow type, earlier and heavier bearing."},
		{"name": "Hass", "crop": "Avocado", "product": None, "item": "Hass Avocado",
		 "anchor": "Flowering", "first_harvest": 240, "window": 120, "yield_ha": 12000, "plants_ha": 160, "yield_plant": 75,
		 "stages": [("Flowering", 0, 30), ("Fruit set", 30, 30), ("Fruit development", 60, 150), ("Maturity", 210, 30),
			("Harvest", 240, 120, 1)],
		 "base_protocol": "Avocado Season", "own_protocol": True,  # Hass keeps the existing Avocado Season family
		 "notes": "Export variety; harvest is gated by dry matter."},
		{"name": "Fuerte", "crop": "Avocado", "product": None, "item": "Fuerte Avocado",
		 "anchor": "Flowering", "first_harvest": 210, "window": 100, "yield_ha": 10000, "plants_ha": 160, "yield_plant": 62,
		 "stages": [("Flowering", 0, 30), ("Fruit set", 30, 25), ("Fruit development", 55, 125), ("Maturity", 180, 30),
			("Harvest", 210, 100, 1)],
		 "base_protocol": "Avocado Season", "protocol_name": "Avocado Season - Fuerte",
		 "timing": {"Fruit Count": (55, 0, 1), "Fertiliser Application": (14, 28, 5)}, "drop": [],
		 "anchored": [("Fruit Count", "Fruit development", 30, 0, 1, 100, "Count fruit once the fruit has set")],
		 "notes": "Earlier maturing, lower yielding; local and regional market."},
		{"name": "GIFT", "crop": "Aquaculture", "product": "Tilapia", "item": "Tilapia - GIFT",
		 "anchor": "Stocking", "first_harvest": 180, "window": 30, "yield_ha": 12000, "plants_ha": 30000, "yield_plant": 0.4,
		 "stages": [("Fingerling", 0, 30), ("Juvenile", 30, 45), ("Grow-out", 75, 90), ("Harvest-ready", 165, 30, 1)],
		 "base_protocol": "Pond Cycle", "timing": {"Harvest": (165, 0, 1)}, "drop": ["Harvest"],
		 "anchored": [("Harvest", "Harvest-ready", 0, 0, 1, 500, "Harvest at 400-500 g")],
		 "notes": "Genetically improved farmed tilapia, fast growing."},
		{"name": "Nile (local)", "crop": "Aquaculture", "product": "Tilapia", "item": "Tilapia - Nile (local)",
		 "anchor": "Stocking", "first_harvest": 210, "window": 30, "yield_ha": 7000, "plants_ha": 20000, "yield_plant": 0.35,
		 "stages": [("Fingerling", 0, 35), ("Juvenile", 35, 55), ("Grow-out", 90, 105), ("Harvest-ready", 195, 30, 1)],
		 "base_protocol": "Pond Cycle", "timing": {"Feeding": (0, 7, 30)}, "drop": ["Harvest"],
		 "anchored": [("Harvest", "Harvest-ready", 0, 0, 1, 400, "Harvest at 350-400 g")],
		 "notes": "Local Nile tilapia stock, slower growing."},
	],
	# existing cycles -> variety: by unit; F&V by protocol family default when a unit is not listed
	"cycle_varieties": {
		"Avocado Block A": "Hass", "Avocado Block B": "Fuerte",
		"P1-B1": "Shangi", "P1-B2": "Dutch Robjin", "P1-B3": "Gloria F1", "P1-B4": "Copenhagen Market",
		"P2-B1": "Red Creole", "P2-B2": "Red Creole", "P2-B3": "Markies", "P2-B4": "Shangi",
		"P3-B1": "Gloria F1", "P3-B2": "Copenhagen Market", "P3-B3": "Red Pinoy F1", "P3-B4": "Red Creole",
		"P4-B1": "Purple", "P4-B2": "Sweet Yellow", "P4-B3": "Purple", "P4-B4": "Sweet Yellow",
	},
	# earlier (closed) cycles on a block: variety by the previous crop's product
	"previous_variety": {"Potatoes": "Markies", "Cabbage": "Gloria F1", "Onion": "Red Pinoy F1"},
	# avocado flowering actuals: days before the cycle record the flowering was observed
	"flowering_days_before_start": {"Hass": 190, "Fuerte": 130},
	"ponds": {"Pond 1": "GIFT", "Pond 2": "Nile (local)", "Pond 3": "GIFT", "Pond 4": "Nile (local)"},
}


# ------------------------------------------------------------------ items

def _ensure_item(v):
	if frappe.db.exists("Item", v["item"]):
		return
	product = v["product"]
	group = (frappe.db.get_value("Item", product, "item_group") if product and frappe.db.exists("Item", product)
		else DEMO["item_group"])
	frappe.get_doc({"doctype": "Item", "item_code": v["item"], "item_name": v["item"], "item_group": group,
		"stock_uom": "Kg", "is_stock_item": 1, "include_item_in_manufacturing": 0}).insert(ignore_permissions=True)


def _inherit_item_figures(v):
	"""A variety item weighs and values like its product (crate weight, valuation rate)."""
	product = v["product"]
	if not product or not frappe.db.exists("Item", product):
		return
	for f in ("production_avg_kg_per_crate", "valuation_rate"):
		val = frappe.db.get_value("Item", product, f)
		if val and not frappe.db.get_value("Item", v["item"], f):
			frappe.db.set_value("Item", v["item"], f, val)


# ------------------------------------------------------------------ varieties

def _ensure_variety(v):
	rows = [{"stage": s[0], "start_day": s[1], "length_days": s[2], "is_harvest": 1 if len(s) > 3 and s[3] else 0}
		for s in v["stages"]]
	vals = {"crop": v["crop"], "product": v["product"], "item": v["item"], "enabled": 1, "stage_anchor": v["anchor"],
		"days_to_first_harvest": v["first_harvest"], "harvest_window_days": v["window"],
		"expected_yield_per_ha": v["yield_ha"], "expected_yield_per_plant": v["yield_plant"],
		"plants_per_ha": v["plants_ha"], "notes": v.get("notes")}
	if frappe.db.exists("Production Variety", v["name"]):
		doc = frappe.get_doc("Production Variety", v["name"])
		doc.update(vals)
		doc.set("stages", rows)
	else:
		doc = frappe.get_doc({"doctype": "Production Variety", "variety_name": v["name"], **vals, "stages": rows})
	doc.save(ignore_permissions=True)


# ------------------------------------------------------------------ protocols

def _op(crop, name):
	return frappe.db.get_value("Production Operation", {"crop": crop, "operation_name": name}, "name")


def _protocol_for(v):
	"""Create (or find) the variety's Active v1 protocol; returns its name."""
	crop = v["crop"]
	if v.get("own_protocol"):  # Hass: the existing family, stamped with the variety
		fam = v["base_protocol"]
		for n in frappe.get_all("Production Protocol", filters={"protocol_family": fam}, pluck="name"):
			frappe.db.set_value("Production Protocol", n, "variety", v["name"], update_modified=False)
		return fam
	pname = v.get("protocol_name") or f"{v['product']} - {v['name']}"
	if frappe.db.exists("Production Protocol", pname):
		return pname
	src_name = frappe.db.get_value("Production Protocol",
		{"protocol_family": v["base_protocol"], "version_status": "Active"}, "name", order_by="version desc") or v["base_protocol"]
	src = frappe.get_doc("Production Protocol", src_name)
	drop = set(v.get("drop") or [])
	timing = v.get("timing") or {}
	steps = []
	for s in src.steps:
		opname = frappe.db.get_value("Production Operation", s.operation, "operation_name")
		if opname in drop:
			continue
		off, every, count = timing.get(opname, (s.day_offset, s.repeat_every_days, s.repeat_count))
		steps.append({"operation": s.operation, "day_offset": off, "repeat_every_days": every, "repeat_count": count,
			"planned_qty": s.planned_qty, "note": s.note})
	for op, stage, off, every, count, qty, note in v.get("anchored") or []:
		opn = _op(crop, op)
		if opn:
			steps.append({"operation": opn, "anchor_stage": stage, "day_offset": off, "repeat_every_days": every,
				"repeat_count": count, "planned_qty": qty, "note": note})
	frappe.flags.in_demo_seed = True
	try:
		doc = frappe.get_doc({"doctype": "Production Protocol", "protocol_name": pname, "crop": crop, "item": v["item"],
			"variety": v["name"], "steps": steps}).insert(ignore_permissions=True)  # demo flag: v1 Active
		convert_protocol_steps.convert(doc)  # key and cultural rows (anchored steps use the variety's stages)
	finally:
		frappe.flags.in_demo_seed = False
	return pname


# ------------------------------------------------------------------ data fixes

def _set_categories():
	cats = DEMO["operation_categories"]
	n = 0
	for op in frappe.get_all("Production Operation", fields=["name", "operation_name"]):
		frappe.db.set_value("Production Operation", op.name, "category", cats.get(op.operation_name, "Other"),
			update_modified=False)
		n += 1
	return n


def _variety_for_cycle(cy):
	vmap = DEMO["cycle_varieties"]
	if cy.status == "Closed":
		return DEMO["previous_variety"].get(stages.product_item(cy.item))
	return vmap.get(cy.unit)


def _fix_cycles():
	frappe.flags.in_demo_seed = True
	fixed = 0
	try:
		cycles = frappe.get_all("Production Crop Cycle", filters={"crop": ("in", ["Avocado", "Fruits & Vegetables"])},
			fields=["name", "unit", "status", "item", "start_date"], order_by="start_date asc")
		for cy in cycles:
			vname = _variety_for_cycle(cy)
			if not vname:
				continue
			doc = frappe.get_doc("Production Crop Cycle", cy.name)
			doc.variety = vname
			doc.protocol = None  # re-resolved from the variety (Active protocol)
			doc.expected_harvest_start = doc.expected_harvest_end = None
			flower = DEMO["flowering_days_before_start"].get(vname)
			if flower and not any(r.stage == "Flowering" for r in doc.stage_actuals):
				doc.append("stage_actuals", {"stage": "Flowering", "actual_date": add_days(doc.start_date, -flower),
					"note": "Flowering observed before this season record was opened"})
			doc.save(ignore_permissions=True)
			fixed += 1
	finally:
		frappe.flags.in_demo_seed = False
	return fixed


def _fix_ponds():
	n = 0
	for pond, strain in DEMO["ponds"].items():
		for s in frappe.get_all("Pond Stocking", filters={"pond": pond, "strain": ("is", "not set")}, pluck="name"):
			frappe.db.set_value("Pond Stocking", s, "strain", strain, update_modified=False)
			n += 1
	return n


def _fix_harvest_items():
	"""F&V harvest records and grading logs follow the item of the cycle they belong to."""
	n = 0
	product_items = {v["product"] for v in DEMO["varieties"] if v["crop"] == "Fruits & Vegetables"}
	for dt in ("Production Harvest", "Harvest Grading Log"):
		for r in frappe.get_all(dt, filters={"item": ("in", list(product_items)), "cycle": ("is", "set")},
				fields=["name", "cycle"]):
			item = frappe.db.get_value("Production Crop Cycle", r.cycle, "item")
			if item and item not in product_items:
				frappe.db.set_value(dt, r.name, "item", item, update_modified=False)
				n += 1
	return n


def run():
	made = {"varieties": 0}
	crops = {}
	for v in DEMO["varieties"]:
		_ensure_item(v)
		_inherit_item_figures(v)
		_ensure_variety(v)
		made["varieties"] += 1
		crops[v["crop"]] = crops.get(v["crop"], 0) + 1
	frappe.db.commit()
	for v in DEMO["varieties"]:
		proto = _protocol_for(v)
		frappe.db.set_value("Production Variety", v["name"], "default_protocol", proto)
	frappe.db.commit()
	made["operation_categories"] = _set_categories()
	made["cycles_fixed"] = _fix_cycles()
	made["ponds_with_strain"] = _fix_ponds()
	made["harvest_items_moved"] = _fix_harvest_items()
	made["by_crop"] = crops
	frappe.db.commit()
	print(f"varieties seed: {made}")
	return made
