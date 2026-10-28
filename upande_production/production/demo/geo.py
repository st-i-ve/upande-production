"""Simulated field geometry for the Mutara demo. Idempotent. Run:

bench --site mutara.local execute upande_production.production.demo.geo.run

Mutara's real position is not recorded on the site (Farm.location is empty, no Location or
Address rows, no SCP Map Settings), so the layout sits at Mutara, Laikipia, Kenya
(about 0.06 N, 36.75 E). Every figure is in GEO below; coordinates are deterministic, so a
re-run rewrites identical GeoJSON.
"""

import json
import math

import frappe

GEO = {
	"origin": (0.06, 36.75),  # (lat, lng) centre of the whole farm
	# Pivots: centres in metres east/north of the origin. Circle radius comes from area_ha.
	"pivot_centres": {"Pivot 1": (-330, 330), "Pivot 2": (330, 330), "Pivot 3": (-330, -330), "Pivot 4": (330, -330)},
	"pivot_start_deg": 45,  # first slice starts here (clockwise from north) so four slices form an X
	"circle_points": 72,
	# Orchard blocks: centre (east, north) and length:width ratio; sized to area_ha.
	"orchard_centres": {"Avocado Block A": (1050, 120), "Avocado Block B": (1050, -260)},
	"orchard_aspect": 1.6,
	# Ponds: row south of the pivots, spaced apart; superellipse "rounded rectangle".
	"pond_row_north": -900,
	"pond_row_east_start": -150,
	"pond_spacing": 90,
	"pond_aspect": 1.4,
	"pond_roundness": 3.0,
	# Hive groups: small squares north of the pivots.
	"hive_centres": {"Hive Group North": (-120, 900), "Hive Group South": (120, 880)},
	"hive_side_m": 22,
	# Fallback areas (ha) when a unit has none.
	"default_area_ha": {"Pond": 0.1, "Hive Group": 0.05, "Orchard Block": 4.0, "Pivot Block": 5.0},
}


def _to_lnglat(east, north):
	lat0, lng0 = GEO["origin"]
	lat = lat0 + north / 111320.0
	lng = lng0 + east / (111320.0 * math.cos(math.radians(lat0)))
	return [round(lng, 6), round(lat, 6)]


def _ring(points_m):
	pts = [_to_lnglat(e, n) for e, n in points_m]
	if pts[0] != pts[-1]:
		pts.append(pts[0])
	return pts


def _feature(name, ring):
	return {"type": "Feature", "properties": {"name": name}, "geometry": {"type": "Polygon", "coordinates": [ring]}}


def _arc(cx, cy, r, a0, a1, steps):
	"""Points along an arc; angles in degrees clockwise from north."""
	out = []
	for i in range(steps + 1):
		a = math.radians(a0 + (a1 - a0) * i / steps)
		out.append((cx + r * math.sin(a), cy + r * math.cos(a)))
	return out


def circle_feature(name, cx, cy, r):
	return _feature(name, _ring(_arc(cx, cy, r, 0, 360, GEO["circle_points"])[:-1]))


def slice_feature(name, cx, cy, r, a0, a1):
	steps = max(6, int(GEO["circle_points"] * (a1 - a0) / 360))
	return _feature(name, _ring([(cx, cy)] + _arc(cx, cy, r, a0, a1, steps)))


def rect_feature(name, cx, cy, w, h):
	return _feature(name, _ring([(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)]))


def superellipse_feature(name, cx, cy, w, h, n):
	pts = []
	for i in range(48):
		t = 2 * math.pi * i / 48
		c, s = math.cos(t), math.sin(t)
		x = (w / 2) * math.copysign(abs(c) ** (2 / n), c)
		y = (h / 2) * math.copysign(abs(s) ** (2 / n), s)
		pts.append((cx + x, cy + y))
	return _feature(name, _ring(pts))


def _radius_m(area_ha):
	return math.sqrt(area_ha * 10000 / math.pi)


def _set(name, feature):
	frappe.db.set_value("Production Unit", name, "geojson", json.dumps(feature, separators=(",", ":")), update_modified=False)


def run():
	units = frappe.get_all(
		"Production Unit",
		fields=["name", "unit_type", "parent_production_unit as parent", "is_group", "area_ha"],
		order_by="lft asc, name asc",
	)
	by_parent = {}
	for u in units:
		by_parent.setdefault(u.parent, []).append(u)
	default = GEO["default_area_ha"]
	done = {"pivots": 0, "slices": 0, "orchard": 0, "ponds": 0, "hives": 0}

	for u in units:
		if u.unit_type == "Pivot":
			cx, cy = GEO["pivot_centres"].get(u.name, (0, 0))
			r = _radius_m(u.area_ha or default["Pivot Block"] * 4)
			_set(u.name, circle_feature(u.name, cx, cy, r))
			done["pivots"] += 1
			kids = sorted(by_parent.get(u.name, []), key=lambda k: k.name)
			if not kids:
				continue
			span = 360.0 / len(kids)
			for i, k in enumerate(kids):
				a0 = GEO["pivot_start_deg"] + i * span
				_set(k.name, slice_feature(k.name, cx, cy, r, a0, a0 + span))
				done["slices"] += 1
	ponds = sorted([u for u in units if u.unit_type == "Pond"], key=lambda u: u.name)
	for i, u in enumerate(ponds):
		area = (u.area_ha or default["Pond"]) * 10000
		h = math.sqrt(area / GEO["pond_aspect"])
		w = h * GEO["pond_aspect"]
		_set(u.name, superellipse_feature(u.name, GEO["pond_row_east_start"] + i * GEO["pond_spacing"], GEO["pond_row_north"], w, h, GEO["pond_roundness"]))
		done["ponds"] += 1
	for i, u in enumerate(sorted([u for u in units if u.unit_type == "Orchard Block"], key=lambda u: u.name)):
		cx, cy = GEO["orchard_centres"].get(u.name, (1050, 400 - i * 380))
		area = (u.area_ha or default["Orchard Block"]) * 10000
		h = math.sqrt(area / GEO["orchard_aspect"])
		_set(u.name, rect_feature(u.name, cx, cy, h * GEO["orchard_aspect"], h))
		done["orchard"] += 1
	for i, u in enumerate(sorted([u for u in units if u.unit_type == "Hive Group"], key=lambda u: u.name)):
		cx, cy = GEO["hive_centres"].get(u.name, (-120 + i * 240, 900))
		side = GEO["hive_side_m"]
		_set(u.name, rect_feature(u.name, cx, cy, side, side))
		done["hives"] += 1
	frappe.db.commit()
	print(f"geometry written: {done}")
	return done
