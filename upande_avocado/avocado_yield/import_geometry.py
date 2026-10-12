# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

# Block boundaries, as surveyed.
#
# The estate keeps its orchard geometry against Warehouse records — one Polygon
# per block, with the tree count and the measured area alongside. That geometry is
# what turns a list of block names into a map you can point at, so it is worth
# carrying into the block master rather than joining across at read time.
#
# The two naming schemes differ by one word: the survey calls a block
# "WESA BLK 3" and the yield sheets call it "WESA 3". The 2018 planting is called
# "BLOCK BLK 1..12" in the survey and "LK01..LK12" in the sheets. Both are mapped
# here, and anything that fails to match is REPORTED rather than guessed at — a
# boundary drawn on the wrong block is worse than no boundary.

import csv
import json
import os
import re

import frappe
from frappe.utils import flt

DOCTYPE = "Avocado Yield Block"
DEFAULT_FILE = "/mnt/c/Users/teddy/Downloads/Warehouse.csv"


def survey_to_block_code(name):
	"""'WESA BLK 3' -> 'WESA 3';  'BLOCK BLK 7' -> 'LK07'."""
	label = re.sub(r"\s+", " ", str(name or "").strip().upper())
	label = label.replace(" - KL", "")
	m = re.match(r"^(.+?)\s+BLK\s+(\d+)$", label)
	if not m:
		return label
	area, number = m.group(1).strip(), int(m.group(2))
	if area == "BLOCK":
		# The survey's plain "BLOCK" is the 2018 planting, LK01-LK12 in the sheets.
		return f"LK{number:02d}"
	return f"{area} {number}"


def centroid(coordinates):
	"""Centre of a polygon ring, for placing a marker or the map's first view."""
	ring = coordinates[0] if coordinates and isinstance(coordinates[0][0], list) else coordinates
	pts = [p for p in ring if isinstance(p, list) and len(p) >= 2]
	if not pts:
		return None, None
	lon = sum(p[0] for p in pts) / len(pts)
	lat = sum(p[1] for p in pts) / len(pts)
	return round(lat, 8), round(lon, 8)


def read_survey(path=DEFAULT_FILE):
	"""[{block_code, survey_name, geojson, centroid, area_m2, tree_count}]"""
	out = []
	with open(path, encoding="utf-8-sig") as fh:
		for row in csv.DictReader(fh):
			raw = (row.get("Raw Geojson") or "").strip()
			name = (row.get("Warehouse Name") or "").strip()
			if not raw or not name:
				continue
			try:
				gj = json.loads(raw)
			except ValueError:
				out.append({"survey_name": name, "error": "geojson will not parse"})
				continue
			features = gj.get("features") or []
			if not features:
				out.append({"survey_name": name, "error": "no feature in the collection"})
				continue
			feature = features[0]
			props = feature.get("properties") or {}
			lat, lon = centroid((feature.get("geometry") or {}).get("coordinates") or [])
			out.append({
				"survey_name": name,
				"block_code": survey_to_block_code(name),
				"geojson": json.dumps(gj, separators=(",", ":")),
				"centroid_lat": lat,
				"centroid_lon": lon,
				"area_m2": flt(props.get("area_m2")),
				"tree_count": props.get("tree_count"),
			})
	return out


def run(path=DEFAULT_FILE, commit=True):
	if not os.path.exists(path):
		frappe.throw(f"No survey file at {path}")

	rows = read_survey(path)
	known = set(frappe.get_all(DOCTYPE, pluck="name"))

	matched, unmatched, broken = 0, [], []
	for r in rows:
		if r.get("error"):
			broken.append(r)
			continue
		code = r["block_code"]
		if code not in known:
			unmatched.append(r)
			continue
		doc = frappe.get_doc(DOCTYPE, code)
		doc.geojson = r["geojson"]
		doc.centroid_lat = r["centroid_lat"]
		doc.centroid_lon = r["centroid_lon"]
		doc.mapped_area_m2 = r["area_m2"]
		doc.save(ignore_permissions=True)
		matched += 1

	if commit:
		frappe.db.commit()

	print(f"boundaries loaded onto {matched} block(s)")
	if unmatched:
		print(f"{len(unmatched)} surveyed block(s) have no block record — not guessed at:")
		for r in unmatched[:12]:
			print(f"   {r['survey_name']:<20} -> looked for {r['block_code']}")
	if broken:
		print(f"{len(broken)} row(s) with unreadable geometry: "
			  + ", ".join(r["survey_name"] for r in broken[:6]))

	# The survey measured every block on the ground. Where that disagrees badly with
	# the hectarage the yield sheets carry, the forecast is sized on the wrong area.
	drift = frappe.db.sql(
		f"""SELECT name, area_ha, mapped_area_m2 / 10000 AS mapped_ha
			FROM `tab{DOCTYPE}`
			WHERE mapped_area_m2 > 0 AND area_ha > 0
			  AND ABS(mapped_area_m2 / 10000 - area_ha) / area_ha > 0.25
			ORDER BY ABS(mapped_area_m2 / 10000 - area_ha) / area_ha DESC""",
		as_dict=True,
	)
	if drift:
		print(f"{len(drift)} block(s) where the surveyed area differs from the sheets by "
			  f"more than a quarter:")
		for d in drift[:8]:
			print(f"   {d.name:<14} sheets {flt(d.area_ha):>6.2f} ha vs surveyed "
				  f"{flt(d.mapped_ha):>6.2f} ha")
	return {"matched": matched, "unmatched": len(unmatched), "broken": len(broken),
			"area_drift": len(drift)}
