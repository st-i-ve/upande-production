"""Data for the flower-crop screens of /production_app (Overview, Blocks & Beds, Crop Cycles, Farm Map).

Margin Par grows flowers in two shapes. Roses are planted per greenhouse (Crop Cycle.greenhouse). The
summer flowers are planted per block: the cycle leaves `greenhouse` empty and names a Block through the
custom field `custom_block`, its beds through `custom_beds_planted` / `bed_range`, and keeps its own figures in
`custom_live_plant_count`, `custom_area_planted_sqm`, `custom_block_area_sqm` and `custom_planting_date`. The farm is
on the cycle, or on its block, or in the cycle's name ("CC-<farm> - Block 10A1-2025W39").

One call returns both shapes in one form. Every custom field is read only when the doctype has it
(`frappe.get_meta(...).has_field`), so sites without them (Mutara) are untouched. Items are shown by
item_name, with the code kept alongside.
"""

import re

import frappe

CYCLE_BASE = ["name", "farm", "greenhouse", "variety", "status", "planting_date", "qty_planted", "plants_standing", "planted_area",
	"bed_range"]
CYCLE_CUSTOM = ["custom_block", "custom_greenhouse", "custom_sf_variety", "custom_live_plant_count", "custom_area_planted_sqm",
	"custom_block_area_sqm", "custom_planting_date", "custom_beds_planted", "custom_cycle_scope"]
UNIT_BASE = ["name", "farm", "number_of_beds", "number_of_plants", "area_planted", "varieties"]


def _fields(doctype, wanted):
	"""The wanted fields this site's doctype really has."""
	if not frappe.db.exists("DocType", doctype):
		return []
	meta = frappe.get_meta(doctype)
	return [f for f in wanted if f == "name" or meta.has_field(f)]


def _num(*vals):
	for v in vals:
		if v:
			return float(v)
	return 0.0


def _farm_from_name(name):
	m = re.match(r"^CC-(.+?) - (?:Block|GH|Greenhouse)\b", name or "")
	return m.group(1) if m else None


def _label(name, farm):
	"""'Kariki Thika - Block 9B' -> 'Block 9B' (the farm is its own column)."""
	if farm and name.startswith(farm + " - "):
		return name[len(farm) + 3:]
	return name


def _crop_items(crop):
	"""The item codes of this crop's varieties, and those claimed by any other crop."""
	rows = frappe.get_all("Production Variety", fields=["name", "crop", "item", "product", "variety_name"])
	mine = {r.item: r for r in rows if r.crop == crop}
	other = {r.item for r in rows if r.crop != crop}
	return mine, other


def _empty():
	return {"mode": "greenhouse", "units": [], "cycles": [], "farms": [], "totals": {
		"units": 0, "beds": 0, "plants": 0, "area_planted": 0, "gross_area": 0, "cycles": 0, "active": 0, "varieties": 0}}


@frappe.whitelist()
def flower_data(crop):
	"""{mode, units, cycles, farms, totals} for one flower Production Crop."""
	if not frappe.db.exists("DocType", "Crop Cycle"):  # the Crop Production module is not on this site
		return _empty()
	frappe.has_permission("Crop Cycle", "read", throw=True)
	mine, others = _crop_items(crop)

	cfields = _fields("Crop Cycle", CYCLE_BASE + CYCLE_CUSTOM)
	rows = frappe.get_all("Crop Cycle", fields=cfields, order_by="modified desc", limit_page_length=0)
	cycles_raw = []
	for r in rows:
		item = r.get("custom_sf_variety") or r.get("variety")
		if mine:
			if item not in mine:
				continue
		elif item in others:
			continue
		cycles_raw.append((r, item))

	# Item display names, one query for every code used here
	codes = {i for _, i in cycles_raw if i} | set(mine)
	names = {}
	if codes:
		for it in frappe.get_all("Item", filters={"name": ("in", list(codes))}, fields=["name", "item_name", "item_group"]):
			names[it.name] = it

	ufields = _fields("Block", UNIT_BASE + ["block_area", "custom_is_summer_flower_block", "custom_sf_plantable_sqm"])
	blocks = {b.name: b for b in frappe.get_all("Block", fields=ufields, limit_page_length=0)} if ufields else {}
	gfields = _fields("Greenhouse", ["name", "farm", "number_of_beds", "number_of_plants", "area_planted", "gross_area", "varieties"])
	houses = {g.name: g for g in frappe.get_all("Greenhouse", fields=gfields, limit_page_length=0)} if gfields else {}

	cycles, by_unit = [], {}
	for r, item in cycles_raw:
		unit = r.get("greenhouse") or r.get("custom_greenhouse") or r.get("custom_block")
		kind = "greenhouse" if (r.get("greenhouse") or r.get("custom_greenhouse")) else "block" if r.get("custom_block") else None
		src = blocks.get(unit) if kind == "block" else houses.get(unit)
		farm = r.get("farm") or (src or {}).get("farm") or _farm_from_name(r["name"])
		plants = _num(r.get("custom_live_plant_count"), r.get("plants_standing"), r.get("qty_planted"))
		area = _num(r.get("custom_area_planted_sqm"), r.get("planted_area"))
		beds = int(_num(r.get("custom_beds_planted")))
		if not beds and r.get("bed_range"):
			beds = len([p for p in re.split(r"[,;]", r["bed_range"]) if p.strip()])
		nm = names.get(item)
		pv = mine.get(item)
		c = {
			"name": r["name"], "unit": unit, "unit_kind": kind, "farm": farm, "variety": item,
			"variety_name": (nm.item_name if nm else None) or (pv.variety_name if pv else None) or item,
			"product": (pv.product if pv else None) or (nm.item_group if nm else None),
			"status": r.get("status"), "planting_date": str(r.get("custom_planting_date") or r.get("planting_date") or "") or None,
			"plants": plants, "area": area, "beds": beds,
		}
		cycles.append(c)
		if unit:
			by_unit.setdefault(unit, []).append(c)

	block_mode = any(c["unit_kind"] == "block" for c in cycles) and not any(c["unit_kind"] == "greenhouse" for c in cycles)
	units = []
	if block_mode:
		wanted = set(by_unit)
		for n, b in blocks.items():
			# a flagged block with nothing in it (no cycle, no beds, no plants) is not part of the picture
			if b.get("custom_is_summer_flower_block") and (b.get("number_of_beds") or b.get("number_of_plants")):
				wanted.add(n)
		for n in sorted(wanted):
			b = blocks.get(n) or {}
			cs = by_unit.get(n, [])
			farm = b.get("farm") or next((c["farm"] for c in cs if c["farm"]), None)
			units.append({
				"name": n, "label": _label(n, farm), "farm": farm,
				"beds": int(b.get("number_of_beds") or sum(c["beds"] for c in cs)),
				"plants": int(_num(b.get("number_of_plants"), sum(c["plants"] for c in cs))),
				"area_planted": _num(b.get("area_planted"), sum(c["area"] for c in cs)),
				"gross_area": _num(b.get("block_area")),
				"varieties": len({c["variety"] for c in cs}) or int(b.get("varieties") or 0),
				"cycles": len(cs),
			})
	else:
		for n, g in sorted(houses.items()):
			cs = by_unit.get(n, [])
			units.append({
				"name": n, "label": n, "farm": g.get("farm"), "beds": int(g.get("number_of_beds") or 0),
				"plants": int(g.get("number_of_plants") or 0), "area_planted": float(g.get("area_planted") or 0),
				"gross_area": float(g.get("gross_area") or 0), "varieties": int(g.get("varieties") or 0), "cycles": len(cs),
			})

	farms = {}
	for u in units:
		f = farms.setdefault(u["farm"] or "(no farm)", {"farm": u["farm"] or "(no farm)", "units": 0, "beds": 0, "plants": 0, "area": 0.0})
		f["units"] += 1
		f["beds"] += u["beds"]
		f["plants"] += u["plants"]
		f["area"] += u["area_planted"]
	return {
		"mode": "block" if block_mode else "greenhouse",
		"units": units, "cycles": cycles, "farms": sorted(farms.values(), key=lambda f: -f["plants"]),
		"totals": {
			"units": len(units), "beds": sum(u["beds"] for u in units), "plants": sum(u["plants"] for u in units),
			"area_planted": sum(u["area_planted"] for u in units), "gross_area": sum(u["gross_area"] for u in units),
			"cycles": len(cycles), "active": len([c for c in cycles if c["status"] == "Active"]),
			"varieties": len({c["variety"] for c in cycles if c["variety"]}),
		},
	}


@frappe.whitelist()
def item_names(codes):
	"""{item code: item_name} for the codes given (a JSON list)."""
	codes = frappe.parse_json(codes) or []
	if not codes:
		return {}
	return {r.name: r.item_name for r in frappe.get_all("Item", filters={"name": ("in", codes)}, fields=["name", "item_name"])}
