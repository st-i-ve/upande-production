"""Setting crop cycles up: a new cycle on a block, an existing cycle already in production, a bulk import.

Several cycles may run on one block at the same time (different varieties, or one variety planted in
parts). When their combined area or tree count is more than the block's, that is a warning, never an
error: `capacity_warnings`.

An existing cycle starts mid-protocol. Its real planting date gives the trees' age; its start date is
the anchor of the variety's stages (the last flowering date, else a date that puts the chosen stage at
today); `schedule_from` is today so the scheduler plans nothing before it (no overdue backlog).
"""

import base64
import csv
import io

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, today

from upande_production.production.logic import stages

CYCLE_DT = "Production Crop Cycle"
RUNNING = ("Active", "Harvesting")
CYCLE_TYPES = ("Season", "Planting")

TEMPLATE_COLUMNS = [
	"block", "variety", "planting_date", "trees", "area_ha", "current_stage", "last_season_kg",
	"last_flowering_date", "last_harvest_date",
]
TEMPLATE_EXAMPLE = ["PH1-B1", "Hass", "2019-03-15", "1650", "10.2", "Fruit development", "42000", "2026-08-20", ""]
_ALIASES = {
	"block": "block", "unit": "block", "block_code": "block", "variety": "variety",
	"planting_date": "planting_date", "planted": "planting_date", "planted_on": "planting_date",
	"trees": "trees", "tree_count": "trees", "plant_count": "trees", "trees_standing": "trees",
	"area": "area_ha", "area_ha": "area_ha", "current_stage": "current_stage", "stage": "current_stage",
	"last_season_kg": "last_season_kg", "last_season_yield_kg": "last_season_kg", "last_season_yield": "last_season_kg",
	"last_flowering_date": "last_flowering_date", "last_harvest_date": "last_harvest_date",
}


# -- block load ---------------------------------------------------------------------------------


def running_load(unit, exclude=None) -> dict:
	"""Area and trees of the cycles running on a unit now (Active / Harvesting), without `exclude`."""
	filters = {"unit": unit, "status": ("in", RUNNING)}
	if exclude:
		filters["name"] = ("!=", exclude)
	rows = frappe.get_all(CYCLE_DT, filters=filters, fields=["area_ha", "plant_count"])
	return {"cycles": len(rows), "area_ha": sum(flt(r.area_ha) for r in rows), "trees": sum(cint(r.plant_count) for r in rows)}


def capacity_warnings(unit, area_ha=0, trees=0, exclude=None, extra=None) -> list:
	"""Warnings when the running cycles on the unit, plus the given area / trees (and `extra`, area and
	trees already claimed in the same import), cover more than the block has."""
	block = frappe.db.get_value("Production Unit", unit, ["area_ha", "plant_count"], as_dict=True)
	if not block:
		return []
	load = running_load(unit, exclude)
	extra = extra or {}
	area = load["area_ha"] + flt(area_ha) + flt(extra.get("area_ha"))
	count = load["trees"] + cint(trees) + cint(extra.get("trees"))
	out = []
	if flt(block.area_ha) and area > flt(block.area_ha) * 1.0001:
		out.append(_("Running cycles on {0} cover {1} ha, more than the block's {2} ha.").format(
			unit, round(area, 2), round(flt(block.area_ha), 2)))
	if cint(block.plant_count) and count > cint(block.plant_count):
		out.append(_("Running cycles on {0} hold {1} trees, more than the block's {2}.").format(
			unit, count, cint(block.plant_count)))
	return out


def warn_overlap(doc) -> list:
	"""Called from Production Crop Cycle.validate: a running cycle that takes the block past its area or
	trees shows a warning (msgprint) and saves anyway."""
	if not doc.unit or doc.status not in RUNNING:
		return []
	warns = capacity_warnings(doc.unit, doc.area_ha, doc.plant_count, exclude=None if doc.is_new() else doc.name)
	for w in warns:
		frappe.msgprint(w, title=_("Block over capacity"), indicator="orange", alert=True)
	return warns


def tree_age_years(planting_date, on=None):
	if not planting_date:
		return None
	days = (getdate(on or today()) - getdate(planting_date)).days
	return round(max(days, 0) / 365.25, 1)


# -- building a cycle ---------------------------------------------------------------------------


def _variety(name):
	v = frappe.db.get_value("Production Variety", name, ["name", "crop", "plants_per_ha", "stage_anchor"], as_dict=True) if name else None
	if not v:
		frappe.throw(_("Variety {0} not found").format(name), frappe.ValidationError)
	return v


def _stage_rows(variety):
	return stages.stages_for(variety)


def _match_stage(rows, text):
	t = (text or "").strip().lower()
	return next((r for r in rows if (r["stage"] or "").lower() == t), None)


def existing_anchor(variety, stage_name, planting_date, last_flowering_date=None, on=None):
	"""(start_date, actual_flowering_date, extra stage actuals) for a cycle that is already in `stage_name`.
	The start date anchors the variety's stages; the stage chosen is made true on `on` (today)."""
	on = getdate(on or today())
	v = _variety(variety)
	rows = _stage_rows(variety)
	cur = _match_stage(rows, stage_name)
	if not cur:
		frappe.throw(_("{0} is not a stage of {1}").format(stage_name, variety), frappe.ValidationError)
	actuals, flowering = [], None
	if v.stage_anchor == "Flowering":
		first = rows[0]
		start = getdate(last_flowering_date) if last_flowering_date else add_days(on, -cur["start_day"])
		if start > on:
			frappe.throw(_("The last flowering date is in the future."), frappe.ValidationError)
		if last_flowering_date:
			flowering = start
	else:
		start = getdate(planting_date)
	probe = {"start_date": start, "variety": variety, "cycle_no": 1,
		"stage_actuals": [frappe._dict(stage=rows[0]["stage"], actual_date=flowering)] if flowering and rows else []}
	now = stages.stage_on(probe, on)["stage"]
	if now != cur["stage"]:
		if rows and cur["stage"] == rows[0]["stage"] and v.stage_anchor == "Flowering":
			start, flowering = on, None  # the first stage is the one it is in: it began today
		else:
			actuals.append({"stage": cur["stage"], "actual_date": on})
	return start, flowering, actuals


def build_values(data) -> dict:
	"""The Production Crop Cycle values for a new or an existing cycle; raises on bad input."""
	unit = frappe.db.get_value("Production Unit", data.get("unit"),
		["name", "crop", "area_ha", "plant_count", "is_group", "status"], as_dict=True)
	if not unit:
		frappe.throw(_("Block {0} not found").format(data.get("unit")), frappe.ValidationError)
	if unit.is_group:
		frappe.throw(_("{0} is a group; choose a block").format(unit.name), frappe.ValidationError)
	if unit.status == "Retired":
		frappe.throw(_("{0} is retired").format(unit.name), frappe.ValidationError)
	if not data.get("variety"):
		frappe.throw(_("Choose a variety."), frappe.ValidationError)
	v = _variety(data.get("variety"))
	area = flt(data.get("area_ha")) or flt(unit.area_ha)
	trees = cint(data.get("plant_count")) or cint(unit.plant_count) or int(round(flt(v.plants_per_ha) * area))
	vals = {"doctype": CYCLE_DT, "unit": unit.name, "crop": unit.crop, "variety": v.name, "area_ha": area,
		"plant_count": trees, "cycle_type": data.get("cycle_type") or "Season", "protocol": data.get("protocol") or None}
	if data.get("existing"):
		planting = data.get("planting_date")
		if not planting:
			frappe.throw(_("Enter the planting date of an existing cycle."), frappe.ValidationError)
		if getdate(planting) > getdate(today()):
			frappe.throw(_("The planting date is in the future."), frappe.ValidationError)
		start, flowering, actuals = existing_anchor(v.name, data.get("current_stage"), planting, data.get("last_flowering_date"))
		rows = _stage_rows(v.name)
		cur = _match_stage(rows, data.get("current_stage"))
		vals.update(start_date=start, existing_cycle=1, planting_date=getdate(planting), schedule_from=getdate(today()),
			status="Harvesting" if cur["is_harvest"] else "Active", actual_flowering_date=flowering,
			last_harvest_date=data.get("last_harvest_date") or None,
			last_season_yield_kg=flt(data.get("last_season_yield_kg")) or None, stage_actuals=actuals)
	else:
		start = getdate(data.get("start_date") or today())
		vals.update(start_date=start, status="Active" if start <= getdate(today()) else "Planned")
		if vals["cycle_type"] == "Planting":
			vals["planting_date"] = start
	return vals


def create_cycle(data) -> dict:
	"""Insert one cycle (permission checked by the caller). {name, warnings}."""
	vals = build_values(data)
	doc = frappe.get_doc(vals)
	doc.insert()
	return {"name": doc.name, "warnings": capacity_warnings(doc.unit) if doc.status in RUNNING else []}


# -- bulk import --------------------------------------------------------------------------------


def template_csv() -> str:
	buf = io.StringIO()
	w = csv.writer(buf)
	w.writerow(TEMPLATE_COLUMNS)
	w.writerow(TEMPLATE_EXAMPLE)
	return buf.getvalue()


def _norm(h):
	return _ALIASES.get((str(h or "").strip().lower().replace(" ", "_").replace("-", "_")), None)


def parse_file(filename, content_b64) -> list:
	"""Rows of a CSV or XLSX upload as dicts keyed by the template columns (unknown columns dropped)."""
	raw = base64.b64decode(content_b64 or "")
	name = (filename or "").lower()
	if name.endswith((".xlsx", ".xlsm")):
		from openpyxl import load_workbook

		ws = load_workbook(io.BytesIO(raw), read_only=True, data_only=True).active
		grid = [list(r) for r in ws.iter_rows(values_only=True)]
	else:
		text = raw.decode("utf-8-sig", errors="replace")
		grid = list(csv.reader(io.StringIO(text)))
	grid = [r for r in grid if any(str(c).strip() for c in r if c is not None)]
	if not grid:
		return []
	cols = [_norm(h) for h in grid[0]]
	if "block" not in cols or "variety" not in cols:
		frappe.throw(_("The first row must have the columns block and variety (see the template)."), frappe.ValidationError)
	out = []
	for r in grid[1:]:
		row = {}
		for c, cell in zip(cols, r):
			if c:
				row[c] = cell
		out.append(row)
	return out


def _date(v):
	if v is None or str(v).strip() == "":
		return None
	if hasattr(v, "strftime"):
		return getdate(v)
	s = str(v).strip()
	for sep in ("/", "."):
		parts = s.split(sep)
		if len(parts) == 3 and len(parts[2]) == 4:  # day first, as the farms write it
			return getdate(f"{parts[2]}-{int(parts[1]):02d}-{int(parts[0]):02d}")
	return getdate(s)


def _num(v):
	if v is None or str(v).strip() == "":
		return None
	return flt(str(v).replace(",", "").strip())


def _unit_for(crop, text):
	t = str(text or "").strip()
	if not t:
		return None
	for field in ("name", "unit_name", "avocado_block_code"):
		hit = frappe.db.get_value("Production Unit", {field: t, "crop": crop, "is_group": 0, "status": ("!=", "Retired")}, "name")
		if hit:
			return hit
	return None


def _variety_for(crop, text):
	t = str(text or "").strip()
	if not t:
		return None
	return frappe.db.get_value("Production Variety", {"name": t, "crop": crop}, "name") or frappe.db.get_value(
		"Production Variety", {"variety_name": t, "crop": crop}, "name")


def check_rows(crop, rows) -> list:
	"""[{row, values, errors, warnings}]: each import row normalised and validated. `values` is what
	`create_cycle` takes. Capacity is counted across the rows of the same block."""
	out, claimed = [], {}
	for i, raw in enumerate(rows, start=2):  # 2: the sheet's first data row
		errors, warnings, vals = [], [], {"existing": 1}
		unit = _unit_for(crop, raw.get("block"))
		if not unit:
			errors.append(_("Block {0} not found").format(raw.get("block") or "(empty)"))
		vals["unit"] = unit
		variety = _variety_for(crop, raw.get("variety"))
		if not variety:
			errors.append(_("Variety {0} not found").format(raw.get("variety") or "(empty)"))
		vals["variety"] = variety
		try:
			planting = _date(raw.get("planting_date"))
		except Exception:
			planting = None
			errors.append(_("Planting date {0} is not a date").format(raw.get("planting_date")))
		if raw.get("planting_date") in (None, "") or (planting is None and not errors):
			errors.append(_("Planting date is required"))
		elif planting and planting > getdate(today()):
			errors.append(_("Planting date is in the future"))
		vals["planting_date"] = str(planting) if planting else None
		for key in ("last_flowering_date", "last_harvest_date"):
			try:
				d = _date(raw.get(key))
			except Exception:
				d = None
				errors.append(_("{0} is not a date").format(key))
			vals[key] = str(d) if d else None
		area, trees = _num(raw.get("area_ha")), _num(raw.get("trees"))
		unit_doc = frappe.db.get_value("Production Unit", unit, ["area_ha", "plant_count"], as_dict=True) if unit else None
		vals["area_ha"] = area or (flt(unit_doc.area_ha) if unit_doc else 0)
		vals["plant_count"] = int(trees) if trees else None
		vals["last_season_yield_kg"] = _num(raw.get("last_season_kg"))
		stage_text = str(raw.get("current_stage") or "").strip()
		if variety:
			st = _match_stage(_stage_rows(variety), stage_text)
			if not st:
				errors.append(_("Stage {0} is not a stage of {1}").format(stage_text or "(empty)", variety))
			else:
				stage_text = st["stage"]
		vals["current_stage"] = stage_text
		if unit and not errors:
			warnings = capacity_warnings(unit, vals["area_ha"], vals["plant_count"] or (unit_doc.plant_count if unit_doc else 0),
				extra=claimed.get(unit))
			c = claimed.setdefault(unit, {"area_ha": 0, "trees": 0})
			c["area_ha"] += flt(vals["area_ha"])
			c["trees"] += cint(vals["plant_count"] or (unit_doc.plant_count if unit_doc else 0))
		out.append({"row": i, "raw": {k: (str(v) if v is not None else "") for k, v in raw.items()}, "values": vals,
			"errors": errors, "warnings": warnings})
	return out


def import_rows(crop, rows) -> list:
	"""Create the valid rows (re-checked here); one row failing does not stop the others."""
	results = []
	for r in check_rows(crop, rows):
		if r["errors"]:
			results.append({"row": r["row"], "ok": False, "error": "; ".join(r["errors"])})
			continue
		frappe.db.savepoint("cycle_import_row")
		try:
			res = create_cycle(r["values"])
			results.append({"row": r["row"], "ok": True, "name": res["name"], "warnings": r["warnings"]})
		except Exception as e:
			frappe.db.rollback(save_point="cycle_import_row")
			results.append({"row": r["row"], "ok": False, "error": str(e)})
	return results
