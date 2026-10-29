"""The real, surveyed blocks and what the demo does with them.

bench --site mutara.local execute upande_production.production.demo.real_blocks.run

The farm's units come from the mapping session (avocado Phase 1 / Phase 2 with PH1-B1.., PH2-B1..; F&V
Pivot 1 / Pivot 2 with P1-B1.., P2-B1..). Their outlines live on their warehouses (custom_raw_geojson, a
FeatureCollection). This module never touches a unit's area, warehouse, cost centre or budget. It

* retires the demo-only units (status Retired, never deleted) and deletes the leaked test fixture,
* copies each unit's outline from its warehouse onto Production Unit.geojson as a single Feature,
  the shape the maps read,
* gives the seeds one place to ask "which blocks, and what figures from the survey".
"""

import json

import frappe
from frappe.utils import cint, flt

from upande_production.production.demo.config import DEMO

DEMO_ONLY = (
	"Avocado Block A", "Avocado Block B", "Pivot 3", "Pivot 4",
	*(f"P3-B{i}" for i in range(1, 5)), *(f"P4-B{i}" for i in range(1, 5)),
)
TEST_FIXTURES = ("TM Unit",)


# ---------------------------------------------------------------- outlines

def as_feature(raw) -> dict | None:
	"""A Feature from a FeatureCollection, Feature or bare geometry (several polygons become one MultiPolygon)."""
	if not raw:
		return None
	try:
		gj = json.loads(raw) if isinstance(raw, str) else raw
	except ValueError:
		return None
	if gj.get("type") == "Feature":
		return gj
	if gj.get("type") == "FeatureCollection":
		feats = [f for f in gj.get("features") or [] if f.get("geometry")]
		if not feats:
			return None
		if len(feats) == 1:
			return feats[0]
		polys = []
		for f in feats:
			g = f["geometry"]
			polys += g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
		return {"type": "Feature", "properties": feats[0].get("properties") or {},
			"geometry": {"type": "MultiPolygon", "coordinates": polys}}
	if gj.get("coordinates"):
		return {"type": "Feature", "properties": {}, "geometry": gj}
	return None


def centroid(feature) -> tuple[float | None, float | None]:
	g = (feature or {}).get("geometry") or {}
	coords = g.get("coordinates") or []
	ring = (coords[0][0] if g.get("type") == "MultiPolygon" else coords[0]) if coords else []
	if not ring:
		return None, None
	return round(sum(p[1] for p in ring) / len(ring), 6), round(sum(p[0] for p in ring) / len(ring), 6)


def _warehouse_of(unit) -> str | None:
	if unit.warehouse:
		return unit.warehouse
	abbr = frappe.db.get_value("Company", unit.company, "abbr") if unit.company else None
	name = f"{unit.name} - {abbr}" if abbr else None
	return name if name and frappe.db.exists("Warehouse", name) else None


def real_units(crop=None, leaf=None):
	"""Units that are not retired, optionally of one crop and leaf-only (leaf=True) or groups-only (False)."""
	filters = {"status": ("!=", "Retired"), "unit_type": ("in", ["Orchard Block", "Pivot", "Pivot Block", "Other"])}
	if crop:
		filters["crop"] = crop
	if leaf is not None:
		filters["is_group"] = 0 if leaf else 1
	return frappe.get_all("Production Unit", filters=filters,
		fields=["name", "unit_name", "crop", "company", "warehouse", "area_ha", "geojson", "is_group", "plant_count",
			"parent_production_unit", "avocado_block_code"], order_by="lft asc", limit_page_length=0)


def sync_outlines() -> int:
	"""Copy each real unit's outline from its warehouse (groups: the warehouse named like the unit)."""
	changed = 0
	for u in real_units():
		wh = _warehouse_of(u)
		raw = frappe.db.get_value("Warehouse", wh, "custom_raw_geojson") if wh else None
		feat = as_feature(raw)
		if not feat:
			continue
		new = json.dumps(feat, separators=(",", ":"))
		old = as_feature(u.geojson)
		if old == feat and u.geojson == new:
			continue
		frappe.db.set_value("Production Unit", u.name, "geojson", new, update_modified=False)
		changed += 1
	return changed


# ---------------------------------------------------------------- retiring the demo units

def retire_demo_units() -> int:
	n = 0
	for name in DEMO_ONLY:
		if frappe.db.exists("Production Unit", name) and frappe.db.get_value("Production Unit", name, "status") != "Retired":
			frappe.db.set_value("Production Unit", name, "status", "Retired", update_modified=False)
			n += 1
	return n


def delete_test_fixtures() -> int:
	n = 0
	for name in TEST_FIXTURES:
		if frappe.db.exists("Production Unit", name):
			for dt in ("Production Crop Cycle", "Yield Sample", "Production Harvest", "Value Adder Work"):
				for d in frappe.get_all(dt, filters={"unit": name}, pluck="name"):
					doc = frappe.get_doc(dt, d)
					if doc.docstatus == 1:
						doc.cancel()
					frappe.delete_doc(dt, d, force=True, ignore_permissions=True)
			for plan in frappe.get_all("Production Plan Task", filters={"unit": name}, pluck="parent"):
				frappe.delete_doc("Production Work Plan", plan, force=True, ignore_permissions=True)
			frappe.delete_doc("Production Unit", name, force=True, ignore_permissions=True)
			n += 1
	return n


# ---------------------------------------------------------------- what the seeds ask

def _avocado_cfg():
	return DEMO["avocado"]


def avocado_blocks() -> list[dict]:
	"""Every real avocado block with the figures the seeds use: area from the survey, trees from the area,
	variety and planting year from DEMO["avocado"]; `active` blocks carry cycles, work and harvests."""
	cfg = _avocado_cfg()
	out = []
	for u in real_units("Avocado", leaf=True):
		code = u.name
		year = next((y for names, y in cfg["planted"] if code in names), cfg["default_planted"])
		active = code in cfg["active"]
		area = flt(u.area_ha)
		total = round(area * cfg["trees_per_ha"])
		live = round(total * cfg["live_share"])
		bearing = round(live * cfg["bearing_share"]) if year <= cfg["bearing_from_planted"] else 0
		variety = "Fuerte" if code in cfg["fuerte"] else "Hass"
		out.append({
			"name": code, "code": code, "area": area, "trees": total, "live": live, "bearing": bearing,
			"sick": round(live * cfg["sick_share"]), "infill": round(live * cfg["infill_share"]),
			"variety": variety, "item": f"{variety} Avocado", "planting_year": year, "active": active,
			"phase": u.parent_production_unit,
		})
	return out


def active_avocado() -> list[dict]:
	return [b for b in avocado_blocks() if b["active"]]


def avocado_unit(code) -> str | None:
	"""The Production Unit of an avocado block code."""
	return frappe.db.get_value("Production Unit", {"avocado_block_code": code, "status": ("!=", "Retired")})


def fv_blocks() -> list[dict]:
	"""Real F&V pivot blocks (leaf units) with their pivot and survey area."""
	return [{"name": u.name, "pivot": u.parent_production_unit, "area": flt(u.area_ha)}
		for u in real_units("Fruits & Vegetables", leaf=True)]


def run():
	out = {
		"retired": retire_demo_units(),
		"fixtures_deleted": delete_test_fixtures(),
		"outlines_synced": sync_outlines(),
	}
	frappe.db.commit()
	print(f"real blocks: {out}")
	return out
