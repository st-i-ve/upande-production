"""JSON endpoints for the Fruits & Vegetables field logs (irrigation, grading).

`irrigation` and `grading` return everything their page draws; `save_irrigation_run` and
`save_grading` are the write actions. Units are in the field names (`_mm`, `_kg`, `_pct`,
`_ha`). Weeks are the Monday as `YYYY-MM-DD`. Every endpoint returns data or
`{"error": msg}` (see api/envelope.py).
"""

import json
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import add_days, flt, get_datetime, getdate, nowdate

from upande_production.api.envelope import as_dict, run
from upande_production.production.logic import bands as band_logic
from upande_production.production.logic.units import unit_filter

CROP = "Fruits & Vegetables"

# A pivot is "utilised" by the hours it ran against all the hours in the period.
HOURS_PER_DAY = 24.0
READ_ROLES = {"Production Manager", "Production Supervisor", "Production Viewer", "System Manager"}


def _need_read(doctype):
	if frappe.session.user == "Administrator" or READ_ROLES & set(frappe.get_roles()):
		return
	frappe.throw(_("You are not permitted to see {0}.").format(doctype), frappe.PermissionError)


def _week_start(d):
	d = getdate(d)
	return add_days(d, -d.weekday())


def _range(from_date, to_date):
	to = getdate(to_date) if to_date else getdate(nowdate())
	frm = getdate(from_date) if from_date else add_days(to, -41)
	if frm > to:
		frm, to = to, frm
	return frm, to


def _weeks(frm, to):
	out, w = [], _week_start(frm)
	while w <= to:
		out.append(w)
		w = add_days(w, 7)
	return out


def weekly_target_mm(variety=None):
	"""Weekly irrigation target in mm: the variety's own, else the crop's. 0 when neither is set."""
	if variety:
		v = flt(frappe.db.get_value("Production Variety", variety, "irrigation_mm_week"))
		if v > 0:
			return v
	return flt(frappe.db.get_value("Production Crop", CROP, "irrigation_mm_week"))


def grade_rules(crop=CROP):
	"""The crop's Production Grade rows: [{grade, rank, is_top}] in rank order."""
	rows = frappe.get_all("Production Grade", filters={"parent": crop, "parenttype": "Production Crop"},
						  fields=["grade", "rank", "is_top_grade"], order_by="rank asc, idx asc", limit_page_length=0)
	return [{"grade": r.grade, "rank": r.rank, "is_top": bool(r.is_top_grade)} for r in rows]


def is_top_grade(name, grades):
	n = (name or "").strip().lower()
	return any(g["is_top"] and g["grade"].strip().lower() == n for g in grades or [])


def _geometry(names):
	"""{unit: parsed geojson feature geometry} for units that have geometry."""
	if not names:
		return {}
	rows = frappe.get_all("Production Unit", filters={"name": ("in", list(names))}, fields=["name", "geojson"])
	out = {}
	for r in rows:
		try:
			g = json.loads(r.geojson) if r.geojson else None
		except Exception:
			g = None
		if g:
			out[r.name] = g.get("geometry") if g.get("type") == "Feature" else g
	return out


def _bounds(geoms):
	xs, ys = [], []

	def walk(c):
		if c and isinstance(c[0], (int, float)):
			xs.append(c[0])
			ys.append(c[1])
		else:
			for i in c or []:
				walk(i)

	for g in geoms:
		walk((g or {}).get("coordinates"))
	return [[min(xs), min(ys)], [max(xs), max(ys)]] if xs else None


# -- irrigation ---------------------------------------------------------------


def pivot_tree(pivot=None):
	"""[{name, area_ha, slices: [{name, area_ha, item}]}] for every pivot (or the one asked)."""
	filters = {"unit_type": "Pivot", "status": ("not in", ["Inactive", "Retired"])}
	if pivot:
		filters["name"] = pivot
	pivots = frappe.get_all("Production Unit", filters=filters, fields=["name", "area_ha", "crop"], order_by="name asc")
	names = [p.name for p in pivots]
	kids = frappe.get_all(
		"Production Unit", filters={"parent_production_unit": ("in", names or [""]), "status": ("!=", "Retired")},
		fields=["name", "area_ha", "parent_production_unit as parent"], order_by="name asc",
	)
	items, varieties = {}, {}
	for c in frappe.get_all(
		"Production Crop Cycle", filters={"unit": ("in", [k.name for k in kids] or [""]), "status": ("in", ["Active", "Harvesting", "Planned"])},
		fields=["unit", "item", "variety", "status", "start_date"], order_by="start_date asc",
	):
		items[c.unit] = c.item
		varieties[c.unit] = c.variety
	by_parent = defaultdict(list)
	for k in kids:
		by_parent[k.parent].append({"name": k.name, "area_ha": flt(k.area_ha), "item": items.get(k.name), "variety": varieties.get(k.name)})
	return [{"name": p.name, "area_ha": flt(p.area_ha), "slices": by_parent.get(p.name, [])} for p in pivots]


def compute_irrigation(runs, pivots, frm, to, target_week, slice_weekly=None):
	"""Pure rollup over run dicts (unit, start_time, end_time, hours, depth_mm, fault, slices[list]).

	Returns the numbers the page draws; see `irrigation` for the shape. Separate from the
	query so it can be tested without a site. `slice_weekly` is {slice: weekly mm} for slices whose
	variety has its own target; the others use `target_week`.
	"""
	days = (to - frm).days + 1
	weeks_in_range = days / 7.0
	target_mm = round(target_week * weeks_in_range, 1)
	slice_parent = {s["name"]: p["name"] for p in pivots for s in p["slices"]}
	mm = defaultdict(float)
	per_pivot = {p["name"]: {"runs": 0, "hours": 0.0, "mm_sum": 0.0, "faults": 0} for p in pivots}
	weekly = defaultdict(lambda: {"hours": 0.0, "mm_sum": 0.0, "runs": 0, "slice_runs": 0})
	n_slices = max(len(slice_parent), 1)
	for r in runs:
		pv = r["unit"]
		if pv not in per_pivot:
			continue
		covered = [s for s in (r.get("slices") or []) if slice_parent.get(s) == pv] or [
			s["name"] for p in pivots if p["name"] == pv for s in p["slices"]]
		for s in covered:
			mm[s] += flt(r["depth_mm"])
		pp = per_pivot[pv]
		pp["runs"] += 1
		pp["hours"] += flt(r["hours"])
		pp["mm_sum"] += flt(r["depth_mm"]) * len(covered)
		if r.get("fault") and r["fault"] != "None":
			pp["faults"] += 1
		w = weekly[str(_week_start(r["start_time"]))]
		w["hours"] += flt(r["hours"])
		w["mm_sum"] += flt(r["depth_mm"]) * len(covered)
		w["runs"] += 1
	slice_target = {s["name"]: round((slice_weekly or {}).get(s["name"], target_week) * weeks_in_range, 1)
					for p in pivots for s in p["slices"]}
	return {"mm_by_slice": dict(mm), "per_pivot": per_pivot, "weekly": weekly, "target_mm": target_mm,
			"slice_target_mm": slice_target,
			"n_slices": n_slices, "days": days}


@frappe.whitelist()
@run
def irrigation(from_date=None, to_date=None, pivot=None):
	_need_read("Pivot Irrigation Run")
	frm, to = _range(from_date, to_date)
	pivots_all = pivot_tree()
	pivots = [p for p in pivots_all if not pivot or p["name"] == pivot]
	names = [p["name"] for p in pivots]
	rows = frappe.get_all(
		"Pivot Irrigation Run",
		filters={"unit": ("in", names or [""]), "start_time": ("between", [f"{frm} 00:00:00", f"{to} 23:59:59"])},
		fields=["name", "unit", "start_time", "end_time", "hours", "direction", "percent_timer", "depth_mm",
				"water_source", "operator", "fault", "notes"],
		order_by="start_time asc",
	)
	cover = defaultdict(list)
	for c in frappe.get_all("Pivot Irrigation Slice", filters={"parent": ("in", [r.name for r in rows] or [""])}, fields=["parent", "slice"]):
		cover[c.parent].append(c.slice)
	opnames = {e.name: e.employee_name for e in frappe.get_all(
		"Employee", filters={"name": ("in", [r.operator for r in rows if r.operator] or [""])}, fields=["name", "employee_name"])}
	runs = [{**r, "slices": cover.get(r.name, []), "start_time": str(r.start_time), "end_time": str(r.end_time),
			 "operator_name": opnames.get(r.operator)} for r in rows]
	target_week = weekly_target_mm()
	slice_weekly = {s["name"]: weekly_target_mm(s["variety"]) for p in pivots for s in p["slices"] if s.get("variety")}
	agg = compute_irrigation(runs, pivots, frm, to, target_week, slice_weekly)
	target = agg["target_mm"]
	bands = band_logic.get_bands()
	on_target_from = band_logic.on_target_from(bands.get("Irrigation % of target"))

	slice_rows, features = [], []
	geoms = _geometry([s["name"] for p in pivots for s in p["slices"]] + names)
	for p in pivots:
		pp = agg["per_pivot"][p["name"]]
		pivot_mm = [agg["mm_by_slice"].get(s["name"], 0.0) for s in p["slices"]]
		for s in p["slices"]:
			m = round(agg["mm_by_slice"].get(s["name"], 0.0), 1)
			st = agg["slice_target_mm"][s["name"]]
			pct = round(m / st * 100, 0) if st else 0
			row = {"slice": s["name"], "pivot": p["name"], "item": s["item"], "mm": m, "target_mm": st, "pct_of_target": pct}
			slice_rows.append(row)
			if s["name"] in geoms:
				features.append({"type": "Feature", "properties": row, "geometry": geoms[s["name"]]})
		pp.update({
			"name": p["name"], "area_ha": p["area_ha"], "slices": len(p["slices"]),
			"mm_per_slice": round(sum(pivot_mm) / len(pivot_mm), 1) if pivot_mm else 0.0,
			"hours": round(pp["hours"], 1),
			"utilisation_pct": round(pp["hours"] / (agg["days"] * HOURS_PER_DAY) * 100, 1),
		})
		pp.pop("mm_sum", None)
	faults = [{"name": r["name"], "pivot": r["unit"], "start_time": r["start_time"], "hours": flt(r["hours"]), "fault": r["fault"],
			   "depth_mm": flt(r["depth_mm"]), "operator": r["operator_name"], "notes": r["notes"]}
			  for r in reversed(runs) if r["fault"] and r["fault"] != "None"]
	n_runs = len(runs)
	hours = sum(flt(r["hours"]) for r in runs)
	slice_mms = [r["mm"] for r in slice_rows]
	weekly_series = []
	for w in _weeks(frm, to):
		d = agg["weekly"].get(str(w), {"hours": 0.0, "mm_sum": 0.0, "runs": 0})
		weekly_series.append({"week": str(w), "runs": d["runs"], "hours": round(d["hours"], 1),
							  "mm_per_slice": round(d["mm_sum"] / agg["n_slices"], 1)})
	return {
		"from_date": str(frm), "to_date": str(to), "pivot": pivot or None,
		"pivots": [pp for pp in agg["per_pivot"].values() if "name" in pp],
		"pivot_names": [p["name"] for p in pivots_all],
		"target": {"weekly_mm": target_week, "period_mm": target, "weeks": round(agg["days"] / 7.0, 1)},
		"bands": bands,
		"kpis": {
			"runs": n_runs, "hours": round(hours, 1),
			"mm_total": round(sum(flt(r["depth_mm"]) for r in runs), 1),
			"mm_per_slice_avg": round(sum(slice_mms) / len(slice_mms), 1) if slice_mms else 0.0,
			"slices_on_target": sum(1 for r in slice_rows if on_target_from is not None and r["pct_of_target"] >= on_target_from),
			"slices": len(slice_rows),
			"faults": len(faults),
			"utilisation_pct": round(hours / (agg["days"] * HOURS_PER_DAY * max(len(pivots), 1)) * 100, 1),
		},
		"series": weekly_series,
		"slices": slice_rows,
		"runs": runs,
		"faults": faults,
		"map": {"type": "FeatureCollection", "features": features, "bounds": _bounds(list(geoms.values()))},
		"form": {"pivots": [{"name": p["name"], "slices": [s["name"] for s in p["slices"]]} for p in pivots_all],
				 "faults": ["None", "Tower misalignment", "Pressure drop", "Power", "Stuck"],
				 "directions": ["Forward", "Reverse"], "water_sources": _water_sources()},
	}


def _water_sources():
	rows = frappe.db.sql("select distinct water_source from `tabPivot Irrigation Run` where ifnull(water_source,'')!='' limit 20")
	return sorted({r[0] for r in rows}) or ["Borehole", "River", "Dam"]


@frappe.whitelist()
@run
def save_irrigation_run(data=None):
	data = as_dict(data)
	if not frappe.has_permission("Pivot Irrigation Run", "create"):
		frappe.throw(_("You are not permitted to record irrigation runs."), frappe.PermissionError)
	doc = build_run(data)
	doc.insert()
	frappe.db.commit()
	return {"ok": True, "name": doc.name, "hours": doc.hours}


def build_run(data):
	for k, label in (("unit", "Pivot"), ("start_time", "Start"), ("end_time", "End")):
		if not data.get(k):
			frappe.throw(_("{0} is required.").format(label))
	if data.get("depth_mm") in (None, ""):
		frappe.throw(_("Depth applied is required."))
	return frappe.get_doc({
		"doctype": "Pivot Irrigation Run", "unit": data["unit"],
		"start_time": get_datetime(data["start_time"]), "end_time": get_datetime(data["end_time"]),
		"depth_mm": flt(data["depth_mm"]), "direction": data.get("direction") or "Forward",
		"percent_timer": flt(data.get("percent_timer")) or None,
		"water_source": data.get("water_source") or None, "operator": data.get("operator") or None,
		"fault": data.get("fault") or "None", "notes": data.get("notes") or None,
		"slices": [{"slice": s} for s in (data.get("slices") or [])],
	})


# -- grading ------------------------------------------------------------------


def compute_grading(logs, frm, to, grades=None):
	"""Pure rollup over grading dicts: {unit, item, grading_date, received_kg, rejects_kg,
	reject_reason, lines: [{grade, kg, crates}]}. `grades` is the crop's `grade_rules`: which grades are top
	and the order they are listed in; a grade not in it follows the ranked ones."""
	grades = grades or []
	rank = {g["grade"].strip().lower(): i for i, g in enumerate(sorted(grades, key=lambda g: g["rank"] or 0))}
	is_top_grade_ = lambda name: is_top_grade(name, grades)
	total_graded = total_received = total_rejects = top = 0.0
	grades_seen = []
	by_item, by_block = {}, {}
	reasons = defaultdict(float)
	weekly = defaultdict(lambda: {"graded": 0.0, "top": 0.0, "rejects": 0.0, "received": 0.0})

	def bucket(d, key):
		return d.setdefault(key, {"graded_kg": 0.0, "rejects_kg": 0.0, "received_kg": 0.0, "grades": defaultdict(float)})

	for g in logs:
		for ln in g["lines"]:
			if ln["grade"] not in grades_seen:
				grades_seen.append(ln["grade"])
		rec, rej = flt(g["received_kg"]), flt(g["rejects_kg"])
		graded = sum(flt(ln["kg"]) for ln in g["lines"])
		g_top = sum(flt(ln["kg"]) for ln in g["lines"] if is_top_grade_(ln["grade"]))
		total_graded += graded
		total_received += rec
		total_rejects += rej
		top += g_top
		if rej and g.get("reject_reason"):
			reasons[g["reject_reason"]] += rej
		w = weekly[str(_week_start(g["grading_date"]))]
		w["graded"] += graded
		w["top"] += g_top
		w["rejects"] += rej
		w["received"] += rec
		for d, key in ((by_item, g.get("item") or "Unspecified"), (by_block, g["unit"])):
			b = bucket(d, key)
			b["graded_kg"] += graded
			b["rejects_kg"] += rej
			b["received_kg"] += rec
			for ln in g["lines"]:
				b["grades"][ln["grade"]] += flt(ln["kg"])
	order = sorted(grades_seen, key=lambda x: (not is_top_grade_(x), rank.get(x.lower(), 99), x.lower()))

	def finish(d):
		out = []
		for k, b in sorted(d.items()):
			out.append({"key": k, "graded_kg": round(b["graded_kg"], 1), "rejects_kg": round(b["rejects_kg"], 1),
						"received_kg": round(b["received_kg"], 1),
						"grades": {gr: round(b["grades"].get(gr, 0.0), 1) for gr in order},
						"class1_pct": round(sum(v for gr, v in b["grades"].items() if is_top_grade_(gr)) / b["graded_kg"] * 100, 1) if b["graded_kg"] else 0.0,
						"reject_pct": round(b["rejects_kg"] / b["received_kg"] * 100, 1) if b["received_kg"] else 0.0})
		return out

	series = []
	for w in _weeks(frm, to):
		d = weekly.get(str(w), {"graded": 0.0, "top": 0.0, "rejects": 0.0, "received": 0.0})
		series.append({"week": str(w), "graded_kg": round(d["graded"], 1),
					   "class1_pct": round(d["top"] / d["graded"] * 100, 1) if d["graded"] else 0.0,
					   "reject_pct": round(d["rejects"] / d["received"] * 100, 1) if d["received"] else 0.0})
	reason_rows = [{"reason": r, "kg": round(k, 1), "pct": round(k / total_rejects * 100, 1) if total_rejects else 0.0}
				   for r, k in sorted(reasons.items(), key=lambda kv: -kv[1])]
	return {
		"kpis": {
			"graded_kg": round(total_graded, 1), "received_kg": round(total_received, 1),
			"rejects_kg": round(total_rejects, 1),
			"class1_pct": round(top / total_graded * 100, 1) if total_graded else 0.0,
			"reject_pct": round(total_rejects / total_received * 100, 1) if total_received else 0.0,
			"top_reject_reason": reason_rows[0]["reason"] if reason_rows else None,
			"top_reject_pct": reason_rows[0]["pct"] if reason_rows else 0.0,
			"logs": len(logs),
		},
		"grades": order, "by_item": finish(by_item), "by_block": finish(by_block),
		"reasons": reason_rows, "series": series,
	}


@frappe.whitelist()
@run
def grading(from_date=None, to_date=None, unit=None, item=None):
	_need_read("Harvest Grading Log")
	frm, to = _range(from_date, to_date)
	filters = unit_filter({"grading_date": ("between", [str(frm), str(to)])})
	if unit:
		filters["unit"] = unit
	if item:
		filters["item"] = item
	rows = frappe.get_all(
		"Harvest Grading Log", filters=filters,
		fields=["name", "unit", "cycle", "item", "grading_date", "received_kg", "received_crates", "graded_kg",
				"rejects_kg", "reject_reason", "graded_by", "notes"],
		order_by="grading_date desc, name desc",
	)
	lines = defaultdict(list)
	for ln in frappe.get_all("Harvest Grading Line", filters={"parent": ("in", [r.name for r in rows] or [""]), "parenttype": "Harvest Grading Log"},
							 fields=["parent", "grade", "kg", "crates"], order_by="idx asc"):
		lines[ln.parent].append({"grade": ln.grade, "kg": flt(ln.kg), "crates": flt(ln.crates)})
	logs = [{**r, "grading_date": str(r.grading_date), "lines": lines.get(r.name, [])} for r in rows]
	grades = grade_rules()
	out = compute_grading(logs, frm, to, grades)
	out["rows"] = [{**g, "class1_kg": round(sum(l["kg"] for l in g["lines"] if is_top_grade(l["grade"], grades)), 1)} for g in logs]
	opts_rows = frappe.get_all("Harvest Grading Log", filters=unit_filter(), fields=["unit", "item"], limit_page_length=0)
	out.update({
		"from_date": str(frm), "to_date": str(to), "unit": unit or None, "item": item or None,
		"units": sorted({r.unit for r in opts_rows if r.unit}), "items": sorted({r.item for r in opts_rows if r.item}),
		"form": {"units": _grading_units(), "reasons": ["Undersize", "Greening", "Rot", "Mechanical damage", "Pest damage"],
				 "default_grades": [g["grade"] for g in grades]},
	})
	return out


def _grading_units():
	"""Blocks that carry a crop cycle, with the item and cycle to default the dialog from."""
	cycles = frappe.get_all(
		"Production Crop Cycle", filters=unit_filter({"status": ("in", ["Active", "Harvesting"])}),
		fields=["name", "unit", "item"], order_by="start_date desc",
	)
	seen, out = set(), []
	units = {u.name: u for u in frappe.get_all("Production Unit", filters={"unit_type": "Pivot Block"}, fields=["name", "parent_production_unit as parent"])}
	for c in cycles:
		if c.unit in units and c.unit not in seen:
			seen.add(c.unit)
			out.append({"name": c.unit, "parent": units[c.unit].parent, "item": c.item, "cycle": c.name})
	return sorted(out, key=lambda u: u["name"])


@frappe.whitelist()
@run
def save_grading(data=None):
	data = as_dict(data)
	if not frappe.has_permission("Harvest Grading Log", "create"):
		frappe.throw(_("You are not permitted to record grading."), frappe.PermissionError)
	doc = build_grading(data)
	doc.insert()
	frappe.db.commit()
	return {"ok": True, "name": doc.name, "graded_kg": doc.graded_kg}


def build_grading(data):
	for k, label in (("unit", "Block"), ("grading_date", "Grading date")):
		if not data.get(k):
			frappe.throw(_("{0} is required.").format(label))
	lines = [ln for ln in (data.get("lines") or []) if (ln.get("grade") or "").strip() and flt(ln.get("kg")) > 0]
	cycle = data.get("cycle") or None
	item = data.get("item") or None
	if not (cycle and item):
		c = frappe.db.get_value("Production Crop Cycle", {"unit": data["unit"], "status": ("in", ["Active", "Harvesting"])},
								["name", "item"], as_dict=True)
		if c:
			cycle, item = cycle or c.name, item or c.item
	return frappe.get_doc({
		"doctype": "Harvest Grading Log", "unit": data["unit"], "cycle": cycle, "item": item,
		"grading_date": data["grading_date"], "received_kg": flt(data.get("received_kg")),
		"received_crates": flt(data.get("received_crates")) or None, "graded_by": data.get("graded_by") or None,
		"rejects_kg": flt(data.get("rejects_kg")), "reject_reason": data.get("reject_reason") or None,
		"notes": data.get("notes") or None,
		"lines": [{"grade": ln["grade"].strip(), "kg": flt(ln["kg"]), "crates": flt(ln.get("crates"))} for ln in lines],
	})
