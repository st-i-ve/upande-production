"""Desk endpoints for the Apiary field logs: hive inspections and honey harvests.

Hive groups are Production Units of crop Apiary. A "colony" is one hive. Every endpoint
returns data or `{"error": msg}` (see api/envelope.py). Units are in the field names:
`_kg`, `_pct`; mites are per 100 bees (`mites_per_100`). Weeks are the Monday as
`YYYY-MM-DD`, oldest first, empty weeks included so a chart has no holes.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, nowdate

from upande_production.api.envelope import as_dict, run
from upande_production.production.logic import bands as band_logic

CROP = "Apiary"
INSPECTION = "Hive Inspection Log"
HARVEST = "Honey Harvest Log"

DEFAULT_DAYS = 90
MAX_WEEKS = 60


# -- helpers -------------------------------------------------------------------------


def _need(doctype, ptype="read"):
	if not frappe.has_permission(doctype, ptype):
		frappe.throw(_("You do not have permission to do this."), frappe.PermissionError)


def _range(from_date, to_date):
	end = getdate(to_date or nowdate())
	start = getdate(from_date) if from_date else add_days(end, -DEFAULT_DAYS)
	if start > end:
		frappe.throw(_("The start date is after the end date."))
	return start, end


def _monday(d):
	d = getdate(d)
	return add_days(d, -d.weekday())


def _weeks(start, end):
	out, w = [], _monday(start)
	last = _monday(end)
	while w <= last and len(out) < MAX_WEEKS:
		out.append(w)
		w = add_days(w, 7)
	return out


def hive_groups():
	"""The crop's hive groups, leaf units only."""
	rows = frappe.get_all(
		"Production Unit", filters={"crop": CROP, "is_group": 0}, fields=["name", "unit_name", "farm"],
		order_by="unit_name asc", limit_page_length=0,
	)
	return [{"value": r.name, "label": r.unit_name or r.name, "farm": r.farm} for r in rows]


def _unit_filter(unit):
	if unit:
		return {"unit": unit}
	names = [g["value"] for g in hive_groups()]
	return {"unit": ("in", names or ["__none__"])}


def limits():
	"""Mite threshold (treat above), mite watch (rising from) and honey moisture limit, from the Apiary crop;
	None where the manager has not set one."""
	return band_logic.crop_limits(CROP, "mite_threshold", "mite_watch", "honey_moisture_limit")


def mite_status(v, threshold, watch):
	if v is None:
		return "none"
	if threshold is None:
		return "none"
	return "high" if v > threshold else "watch" if watch is not None and v >= watch else "ok"


def queen_status(inspected, queenright, bands=None):
	"""Share of colonies with a laying queen decides the chip, by the Queen status bands."""
	if not inspected:
		return "none"
	return queen_label(100.0 * queenright / inspected, bands)


QUEEN_BY_SEVERITY = {"Good": "queenright", "Watch": "weak", "Critical": "queenless"}


def queen_label(pct, bands=None):
	"""The chip code for a queenright share: the Queen status band's severity (Good/Watch/Critical) as
	queenright/weak/queenless, so a manager can rename or move the bands without breaking the page."""
	row = band_logic.band_of("Queen status", pct, bands)
	return QUEEN_BY_SEVERITY[row["severity"]] if row else "none"


def _avg(vals):
	vals = [v for v in vals if v is not None]
	return round(sum(vals) / len(vals), 2) if vals else None


def _employees():
	return [
		{"value": e.name, "label": e.employee_name or e.name}
		for e in frappe.get_all("Employee", filters={"status": "Active"}, fields=["name", "employee_name"],
								order_by="employee_name asc", limit_page_length=300)
	]


# -- hive inspections ------------------------------------------------------------------


def _inspection_rows(start, end, unit):
	flt_ = _unit_filter(unit)
	flt_["inspection_date"] = ("between", [start, end])
	return frappe.get_all(
		INSPECTION, filters=flt_, order_by="inspection_date desc, creation desc", limit_page_length=0,
		fields=["name", "unit", "inspection_date", "inspector", "colonies_inspected", "colonies_queenright",
				"queen_seen", "eggs_seen", "brood_pattern", "temperament", "varroa_per_100", "disease_signs",
				"frames_brood", "frames_honey", "frames_stores", "feeding_kg", "actions"],
	)


def _kpis(rows):
	colonies = sum(cint(r.colonies_inspected) for r in rows)
	qr = sum(cint(r.colonies_queenright) for r in rows)
	mites = [flt(r.varroa_per_100) for r in rows if r.varroa_per_100 is not None]
	return {
		"inspections": len(rows),
		"colonies": colonies,
		"queenright_pct": round(100.0 * qr / colonies, 1) if colonies else None,
		"avg_mites": _avg(mites),
		"disease_flags": sum(1 for r in rows if (r.disease_signs or "None") != "None"),
	}


@frappe.whitelist()
@run
def hive_inspections(from_date=None, to_date=None, unit=None):
	_need(INSPECTION)
	start, end = _range(from_date, to_date)
	unit = unit or None
	rows = _inspection_rows(start, end, unit)
	lim = limits()
	threshold, watch = lim["mite_threshold"], lim["mite_watch"]
	all_bands = band_logic.get_bands()
	k = _kpis(rows)
	k["queen_status"] = queen_label(k["queenright_pct"], all_bands) if k["queenright_pct"] is not None else "none"

	# Previous period of the same length, for the mite-load trend.
	span = (end - start).days + 1
	prev = _inspection_rows(add_days(start, -span), add_days(start, -1), unit)
	prev_avg = _avg([flt(r.varroa_per_100) for r in prev if r.varroa_per_100 is not None])
	k["avg_mites_prev"] = prev_avg
	k["mites_trend"] = round(k["avg_mites"] - prev_avg, 2) if k["avg_mites"] is not None and prev_avg is not None else None

	# Latest reading per group: colonies above the threshold are the colonies of groups
	# whose latest inspection is over it.
	latest = {}
	by_unit = {}
	for r in rows:  # rows are newest first
		by_unit.setdefault(r.unit, []).append(r)
		latest.setdefault(r.unit, r)
	k["colonies_above_threshold"] = sum(
		cint(r.colonies_inspected) for r in latest.values() if threshold is not None and r.varroa_per_100 is not None and flt(r.varroa_per_100) > threshold
	)
	k["groups_above_threshold"] = sum(
		1 for r in latest.values() if threshold is not None and r.varroa_per_100 is not None and flt(r.varroa_per_100) > threshold
	)

	# Weekly series (oldest first).
	weeks = _weeks(start, end)
	bucket = {w: [] for w in weeks}
	for r in rows:
		bucket.get(_monday(r.inspection_date), []).append(r)
	series = []
	for w in weeks:
		b = bucket[w]
		kk = _kpis(b)
		series.append({
			"week": str(w), "inspections": kk["inspections"], "colonies": kk["colonies"],
			"queenright_pct": kk["queenright_pct"], "avg_mites": kk["avg_mites"], "disease_flags": kk["disease_flags"],
		})

	groups = []
	for g in hive_groups():
		if unit and g["value"] != unit:
			continue
		mine = by_unit.get(g["value"], [])
		lt = latest.get(g["value"])
		item = {"unit": g["value"], "label": g["label"], "farm": g["farm"], "inspections": len(mine)}
		if lt:
			inspected, queenright = cint(lt.colonies_inspected), cint(lt.colonies_queenright)
			mites = flt(lt.varroa_per_100) if lt.varroa_per_100 is not None else None
			item.update({
				"last_date": str(lt.inspection_date), "days_since": (getdate(nowdate()) - getdate(lt.inspection_date)).days,
				"colonies": inspected, "queenright": queenright,
				"queenright_pct": round(100.0 * queenright / inspected, 1) if inspected else None,
				"queen_status": queen_status(inspected, queenright, all_bands), "queen_seen": bool(lt.queen_seen),
				"eggs_seen": bool(lt.eggs_seen), "mites_per_100": mites, "mite_status": mite_status(mites, threshold, watch),
				"brood_pattern": lt.brood_pattern or None, "temperament": lt.temperament or None,
				"disease_signs": lt.disease_signs or "None", "frames_brood": lt.frames_brood,
				"frames_honey": lt.frames_honey, "frames_stores": lt.frames_stores, "inspector": lt.inspector,
				"trend": [
					{"date": str(r.inspection_date), "mites": flt(r.varroa_per_100) if r.varroa_per_100 is not None else None,
					 "queenright_pct": round(100.0 * cint(r.colonies_queenright) / cint(r.colonies_inspected), 1)
					 if cint(r.colonies_inspected) else None}
					for r in reversed(mine)
				],
			})
		else:
			item.update({"last_date": None, "queen_status": "none", "mite_status": "none", "trend": []})
		groups.append(item)

	return {
		"from_date": str(start), "to_date": str(end), "unit": unit, "threshold": threshold, "watch": watch, "bands": all_bands,
		"kpis": k, "series": series, "groups": groups,
		"rows": [{**r, "unit_label": next((g["label"] for g in hive_groups() if g["value"] == r.unit), r.unit),
				  "inspection_date": str(r.inspection_date), "queen_seen": bool(r.queen_seen),
				  "eggs_seen": bool(r.eggs_seen), "mite_status": mite_status(flt(r.varroa_per_100) if r.varroa_per_100 is not None else None, threshold, watch)}
				 for r in rows],
		"form": inspection_form(),
	}


def inspection_form():
	return {
		"units": hive_groups(), "employees": _employees(), "today": nowdate(),
		"brood_patterns": ["Solid", "Patchy", "None"], "temperaments": ["Calm", "Nervous", "Aggressive"],
		"disease_options": ["None", "Chalkbrood", "AFB/EFB suspect", "Small hive beetle", "Wax moth"],
		"threshold": limits()["mite_threshold"], "watch": limits()["mite_watch"],
	}


def _check_unit(unit):
	if not unit:
		frappe.throw(_("Choose a hive group."))
	if frappe.db.get_value("Production Unit", unit, "crop") != CROP:
		frappe.throw(_("{0} is not an Apiary hive group.").format(unit))


def create_inspection(data):
	"""Shared by the desk and mobile endpoints. Returns the saved doc."""
	data = as_dict(data)
	_check_unit(data.get("unit"))
	doc = frappe.get_doc({
		"doctype": INSPECTION, "unit": data.get("unit"),
		"inspection_date": data.get("inspection_date") or nowdate(),
		"inspector": data.get("inspector") or None,
		"colonies_inspected": cint(data.get("colonies_inspected")),
		"colonies_queenright": cint(data.get("colonies_queenright")),
		"queen_seen": cint(data.get("queen_seen")), "eggs_seen": cint(data.get("eggs_seen")),
		"brood_pattern": data.get("brood_pattern") or None, "temperament": data.get("temperament") or None,
		"varroa_per_100": None if data.get("varroa_per_100") in (None, "") else flt(data.get("varroa_per_100")),
		"disease_signs": data.get("disease_signs") or "None",
		"frames_brood": flt(data.get("frames_brood")), "frames_honey": flt(data.get("frames_honey")),
		"frames_stores": flt(data.get("frames_stores")), "feeding_kg": flt(data.get("feeding_kg")),
		"actions": (data.get("actions") or "").strip() or None,
	})
	if getdate(doc.inspection_date) > getdate(nowdate()):
		frappe.throw(_("The inspection date cannot be in the future."))
	doc.insert()
	return doc


@frappe.whitelist()
@run
def save_hive_inspection(data=None):
	doc = create_inspection(data)
	return {"ok": True, "name": doc.name, "message": _("Inspection saved.")}


# -- honey harvest ---------------------------------------------------------------------


def _colonies_by_unit(end):
	"""Colonies per group from the latest inspection on or before `end`."""
	out = {}
	for r in frappe.get_all(
		INSPECTION, filters={"inspection_date": ("<=", end)}, fields=["unit", "colonies_inspected"],
		order_by="inspection_date asc, creation asc", limit_page_length=0,
	):
		out[r.unit] = cint(r.colonies_inspected)
	return out


def _harvest_kpis(rows):
	kg = sum(flt(r.honey_kg) for r in rows)
	moist = [(flt(r.moisture_pct), flt(r.honey_kg)) for r in rows if r.moisture_pct]
	w = sum(k for _m, k in moist)
	grade_a = sum(flt(r.honey_kg) for r in rows if r.grade == "A")
	return {
		"kg": round(kg, 1), "harvests": len(rows),
		"avg_moisture": round(sum(m * k for m, k in moist) / w, 1) if w else None,
		"grade_a_pct": round(100.0 * grade_a / kg, 1) if kg else None,
		"wax_kg": round(sum(flt(r.wax_kg) for r in rows), 1),
	}


@frappe.whitelist()
@run
def honey_harvest(from_date=None, to_date=None, unit=None):
	_need(HARVEST)
	start, end = _range(from_date, to_date)
	unit = unit or None
	flt_ = _unit_filter(unit)
	flt_["harvest_date"] = ("between", [start, end])
	rows = frappe.get_all(
		HARVEST, filters=flt_, order_by="harvest_date desc, creation desc", limit_page_length=0,
		fields=["name", "unit", "harvest_date", "supers_removed", "frames_extracted", "honey_kg", "moisture_pct",
				"grade", "wax_kg", "notes"],
	)
	labels = {g["value"]: g["label"] for g in hive_groups()}
	colonies = _colonies_by_unit(end)
	k = _harvest_kpis(rows)
	producing = {r.unit for r in rows}
	hives = sum(colonies.get(u, 0) for u in producing)
	k["colonies"] = hives
	k["kg_per_hive"] = round(k["kg"] / hives, 2) if hives else None

	weeks = _weeks(start, end)
	bucket = {w: [] for w in weeks}
	for r in rows:
		bucket.get(_monday(r.harvest_date), []).append(r)
	series = []
	for w in weeks:
		kk = _harvest_kpis(bucket[w])
		series.append({"week": str(w), "kg": kk["kg"], "avg_moisture": kk["avg_moisture"], "grade_a_pct": kk["grade_a_pct"]})

	by_unit = {}
	for r in rows:
		by_unit.setdefault(r.unit, []).append(r)
	groups = []
	for g in hive_groups():
		if unit and g["value"] != unit:
			continue
		mine = by_unit.get(g["value"], [])
		kk = _harvest_kpis(mine)
		n = colonies.get(g["value"], 0)
		groups.append({
			"unit": g["value"], "label": g["label"], "farm": g["farm"], "harvests": kk["harvests"], "kg": kk["kg"],
			"colonies": n, "kg_per_hive": round(kk["kg"] / n, 2) if n and kk["kg"] else None,
			"avg_moisture": kk["avg_moisture"], "grade_a_pct": kk["grade_a_pct"], "wax_kg": kk["wax_kg"],
			"supers_removed": sum(cint(r.supers_removed) for r in mine),
			"last_harvest": str(mine[0].harvest_date) if mine else None,
		})
	return {
		"from_date": str(start), "to_date": str(end), "unit": unit, "kpis": k, "series": series, "groups": groups,
		"rows": [{**r, "unit_label": labels.get(r.unit, r.unit), "harvest_date": str(r.harvest_date)} for r in rows],
		"bands": band_logic.get_bands(),
		"form": {"units": hive_groups(), "today": nowdate(), "grades": ["A", "B", "C"], "moisture_limit": limits()["honey_moisture_limit"]},
	}


def create_harvest(data):
	data = as_dict(data)
	_check_unit(data.get("unit"))
	doc = frappe.get_doc({
		"doctype": HARVEST, "unit": data.get("unit"), "harvest_date": data.get("harvest_date") or nowdate(),
		"supers_removed": cint(data.get("supers_removed")), "frames_extracted": cint(data.get("frames_extracted")),
		"honey_kg": flt(data.get("honey_kg")),
		"moisture_pct": flt(data.get("moisture_pct")) if data.get("moisture_pct") not in (None, "") else None,
		"grade": data.get("grade") or "A", "wax_kg": flt(data.get("wax_kg")),
		"notes": (data.get("notes") or "").strip() or None,
	})
	if getdate(doc.harvest_date) > getdate(nowdate()):
		frappe.throw(_("The harvest date cannot be in the future."))
	doc.insert()
	return doc


@frappe.whitelist()
@run
def save_honey_harvest(data=None):
	doc = create_harvest(data)
	return {"ok": True, "name": doc.name, "message": _("Harvest saved.")}
