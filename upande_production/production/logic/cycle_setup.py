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

from upande_production.production.logic import field_crops, stages

CYCLE_DT = "Production Crop Cycle"
RUNNING = ("Active", "Harvesting")
STATUSES = ("Planned", "Active", "Harvesting", "Closed")
CYCLE_TYPES = ("Season", "Planting")

TEMPLATE_COLUMNS = [
	"block", "variety", "planting_date", "trees", "area_ha", "current_stage", "last_season_kg",
	"last_flowering_date", "last_harvest_date",
]
TEMPLATE_EXAMPLE = ["PH1-B1", "Hass", "2019-03-15", "1650", "10.2", "Fruit development", "42000", "2026-08-20", ""]
# Other crops: the date the cycle was planted or started in the other system, an optional stage and harvest history.
TEMPLATE_COLUMNS_OTHER = [
	"block", "variety", "item", "protocol", "planting_date", "area_ha", "plant_count", "current_stage",
	"already_harvesting", "last_harvest_date", "last_season_kg",
]
TEMPLATE_EXAMPLE_OTHER = ["FV-B1", "", "Tomato", "", "2026-09-01", "1.5", "", "", "", "", ""]
# A section with Field Crops (Fruits & Vegetables) names the crop of each row: Cabbage, Maize, Onion ...
TEMPLATE_COLUMNS_FIELD_CROPS = ["block", "crop", "variety", "protocol", "planting_date", "area_ha", "plant_count", "current_stage",
	"already_harvesting", "last_harvest_date", "last_season_kg"]
TEMPLATE_EXAMPLE_FIELD_CROPS = ["P1-B3", "Cabbage", "Gloria F1", "", "2026-09-01", "1.5", "", "", "", "", ""]
_ALIASES = {
	"block": "block", "unit": "block", "block_code": "block", "variety": "variety",
	"planting_date": "planting_date", "planted": "planting_date", "planted_on": "planting_date",
	"trees": "trees", "tree_count": "trees", "plant_count": "trees", "trees_standing": "trees",
	"area": "area_ha", "area_ha": "area_ha", "current_stage": "current_stage", "stage": "current_stage",
	"last_season_kg": "last_season_kg", "last_season_yield_kg": "last_season_kg", "last_season_yield": "last_season_kg",
	"last_flowering_date": "last_flowering_date", "last_harvest_date": "last_harvest_date",
	"item": "item", "item_code": "item", "protocol": "protocol", "start_date": "planting_date", "started": "planting_date",
	"started_on": "planting_date", "date_started": "planting_date", "already_harvesting": "already_harvesting",
	"harvesting": "already_harvesting", "crop": "field_crop", "field_crop": "field_crop",
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


def is_avocado(crop) -> bool:
	"""Avocado keeps its own rules (a stage is required, last flowering date, tree columns)."""
	return bool(crop) and frappe.db.get_value("Production Crop", crop, "crop_key") == "avocado"


def _variety(name):
	v = frappe.db.get_value("Production Variety", name, ["name", "crop", "plants_per_ha", "stage_anchor", "field_crop"], as_dict=True) if name else None
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
	existing = bool(data.get("existing"))
	if not data.get("variety") and not (existing and data.get("item")):
		frappe.throw(_("Choose a variety or an item.") if existing else _("Choose a variety."), frappe.ValidationError)
	v = _variety(data.get("variety")) if data.get("variety") else frappe._dict(name=None, plants_per_ha=0, field_crop=None)
	chosen = data.get("field_crop") or None
	if chosen:
		field_crops.check_section(chosen, unit.crop)
		if v.name and v.field_crop and v.field_crop != chosen:
			frappe.throw(_("{0} is a {1} variety, not {2}.").format(v.name, v.field_crop, chosen), frappe.ValidationError)
	area = flt(data.get("area_ha")) or flt(unit.area_ha)
	trees = cint(data.get("plant_count")) or cint(unit.plant_count) or int(round(flt(v.plants_per_ha) * area))
	vals = {"doctype": CYCLE_DT, "unit": unit.name, "crop": unit.crop, "variety": v.name, "area_ha": area,
		"plant_count": trees, "cycle_type": data.get("cycle_type") or "Season", "protocol": data.get("protocol") or None,
		"field_crop": v.field_crop or chosen}
	if not v.name:
		if not frappe.db.exists("Item", data.get("item")):
			frappe.throw(_("Item {0} not found").format(data.get("item")), frappe.ValidationError)
		vals["item"] = data.get("item")
	if existing:
		avocado = is_avocado(unit.crop)
		planting = data.get("planting_date")
		if not planting:
			frappe.throw(_("Enter the planting date of an existing cycle.") if avocado
				else _("Enter the date the cycle was planted or started."), frappe.ValidationError)
		if getdate(planting) > getdate(today()):
			frappe.throw(_("The planting date is in the future."), frappe.ValidationError)
		stage_name = (data.get("current_stage") or "").strip()
		if v.name and (stage_name or avocado):
			start, flowering, actuals = existing_anchor(v.name, stage_name, planting, data.get("last_flowering_date"))
			cur = _match_stage(_stage_rows(v.name), stage_name)
		else:  # no stage to honour: the cycle runs from the date it was started in the other system
			start, flowering, actuals, cur = getdate(planting), None, [], None
		harvesting = bool((cur and cur["is_harvest"]) or cint(data.get("already_harvesting")))
		vals.update(start_date=start, existing_cycle=1, planting_date=getdate(planting), schedule_from=getdate(today()),
			status="Harvesting" if harvesting else "Active", actual_flowering_date=flowering,
			last_harvest_date=data.get("last_harvest_date") or None,
			last_season_yield_kg=flt(data.get("last_season_yield_kg")) or None, stage_actuals=actuals)
	else:
		start = getdate(data.get("start_date") or today())
		vals.update(start_date=start, status="Active" if start <= getdate(today()) else "Planned")
		if vals["cycle_type"] == "Planting":
			vals["planting_date"] = start
	return vals


def _keep_area(doc, area):
	"""The doctype's area_ha is fetched from the block on every save; the area typed for the cycle wins."""
	if area is not None and flt(doc.area_ha) != flt(area):
		frappe.db.set_value(CYCLE_DT, doc.name, "area_ha", flt(area), update_modified=False)
		doc.area_ha = flt(area)


def create_cycle(data) -> dict:
	"""Insert one cycle (permission checked by the caller). {name, warnings}."""
	vals = build_values(data)
	doc = frappe.get_doc(vals)
	doc.insert()
	_keep_area(doc, vals.get("area_ha"))
	return {"name": doc.name, "warnings": capacity_warnings(doc.unit) if doc.status in RUNNING else []}


# -- bulk import --------------------------------------------------------------------------------


def template_columns(crop=None) -> list:
	if not crop or is_avocado(crop):
		return TEMPLATE_COLUMNS
	return TEMPLATE_COLUMNS_FIELD_CROPS if field_crops.has_field_crops(crop) else TEMPLATE_COLUMNS_OTHER


def template_csv(crop=None) -> str:
	buf = io.StringIO()
	w = csv.writer(buf)
	w.writerow(template_columns(crop))
	w.writerow(TEMPLATE_EXAMPLE if not crop or is_avocado(crop) else
		TEMPLATE_EXAMPLE_FIELD_CROPS if field_crops.has_field_crops(crop) else TEMPLATE_EXAMPLE_OTHER)
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
	if "block" not in cols or not ("variety" in cols or "item" in cols):
		frappe.throw(_("The first row must have the columns block and variety (or item); see the template."), frappe.ValidationError)
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


def _field_crop_for(crop, text):
	t = str(text or "").strip()
	if not t:
		return None
	return frappe.db.get_value("Production Field Crop", {"name": t}, "name") or frappe.db.get_value(
		"Production Field Crop", {"crop_name": t}, "name")


def _variety_for(crop, text, field_crop=None):
	t = str(text or "").strip()
	if not t:
		return None
	extra = {"field_crop": field_crop} if field_crop else {}
	return frappe.db.get_value("Production Variety", {"name": t, "crop": crop, **extra}, "name") or frappe.db.get_value(
		"Production Variety", {"variety_name": t, "crop": crop, **extra}, "name")


def check_rows(crop, rows) -> list:
	"""[{row, values, errors, warnings}]: each import row normalised and validated. `values` is what
	`create_cycle` takes. Capacity is counted across the rows of the same block."""
	out, claimed = [], {}
	avocado = is_avocado(crop)
	for i, raw in enumerate(rows, start=2):  # 2: the sheet's first data row
		errors, warnings, vals = [], [], {"existing": 1}
		unit = _unit_for(crop, raw.get("block"))
		if not unit:
			errors.append(_("Block {0} not found").format(raw.get("block") or "(empty)"))
		vals["unit"] = unit
		field_crop = None
		crop_text = raw.get("field_crop") if raw.get("field_crop") not in (None, "") else raw.get("crop")
		if crop_text not in (None, ""):
			field_crop = _field_crop_for(crop, crop_text)
			if not field_crop:
				errors.append(_("Crop {0} not found").format(crop_text))
		variety = _variety_for(crop, raw.get("variety"), field_crop)
		item = str(raw.get("item") or "").strip()
		if not variety and (avocado or raw.get("variety") or not item):
			if field_crop and raw.get("variety") and _variety_for(crop, raw.get("variety")):
				errors.append(_("Variety {0} is not a {1} variety").format(raw.get("variety"), field_crop))
			else:
				errors.append(_("Variety {0} not found").format(raw.get("variety") or "(empty)") if avocado or raw.get("variety")
					else _("Variety or item is required"))
		vals["variety"] = variety
		if variety and not field_crop:
			field_crop = field_crops.from_variety(variety)
		elif not variety and not field_crop and item:
			field_crop = field_crops.from_item(item, crop)
		if not field_crop and not errors and field_crops.has_field_crops(crop):
			errors.append(_("Crop is required"))
		vals["field_crop"] = field_crop
		if not variety and item:
			if frappe.db.exists("Item", item):
				vals["item"] = item
			else:
				errors.append(_("Item {0} not found").format(item))
		proto_text = str(raw.get("protocol") or "").strip()
		if proto_text:
			proto = frappe.db.get_value("Production Protocol", {"name": proto_text, "crop": crop}, ["name", "version_status"], as_dict=True) or \
				frappe.db.get_value("Production Protocol", {"protocol_name": proto_text, "crop": crop, "version_status": "Active"}, ["name", "version_status"], as_dict=True)
			if not proto:
				errors.append(_("Protocol {0} not found").format(proto_text))
			elif proto.version_status != "Active":
				errors.append(_("Protocol {0} is not Active").format(proto_text))
			else:
				vals["protocol"] = proto.name
		vals["already_harvesting"] = 1 if str(raw.get("already_harvesting") or "").strip().lower() in ("1", "yes", "y", "true", "x") else 0
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
		if variety and (stage_text or avocado):
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


def edit_info(name) -> dict:
	"""What the Edit cycle form starts from: the editable fields, and whether tasks exist (the block is then fixed)."""
	doc = frappe.get_doc(CYCLE_DT, name)
	out = {k: doc.get(k) for k in ("name", "unit", "crop", "field_crop", "variety", "item", "protocol", "start_date", "planting_date",
		"area_ha", "plant_count", "expected_harvest_start", "expected_harvest_end", "status", "notes", "existing_cycle")}
	out["has_tasks"] = bool(frappe.db.exists("Work Plan Task", {"cycle": name}))
	return out


def update_cycle(name, data) -> dict:
	"""Edit a cycle already made: {name, warnings, notes}. Changing the protocol or start date of a running
	cycle re-plans from today (`schedule_from`), never back-fills; tasks already in weekly plans stay."""
	doc = frappe.get_doc(CYCLE_DT, name)
	data = data or {}
	notes = []
	old_unit, old_status = doc.unit, doc.status
	status = data.get("status") if "status" in data else doc.status
	if status not in STATUSES:
		frappe.throw(_("Status must be one of {0}.").format(", ".join(STATUSES)), frappe.ValidationError)
	if "unit" in data and data["unit"] != doc.unit:
		if frappe.db.exists("Work Plan Task", {"cycle": name}):
			frappe.throw(_("The block cannot change once the cycle has tasks."), frappe.ValidationError)
		doc.unit = data["unit"]
	unit = frappe.db.get_value("Production Unit", doc.unit, ["is_group", "status"], as_dict=True)
	if not unit or unit.is_group:
		frappe.throw(_("Choose a block."), frappe.ValidationError)
	if unit.status == "Retired" and status != "Closed" and (doc.unit != old_unit or status != old_status):
		frappe.throw(_("{0} is retired").format(doc.unit), frappe.ValidationError)

	def d(key):
		return getdate(data[key]) if data.get(key) else None

	try:
		start = d("start_date") if "start_date" in data else getdate(doc.start_date)
		planting = d("planting_date") if "planting_date" in data else (getdate(doc.planting_date) if doc.planting_date else None)
		h_from = d("expected_harvest_start") if "expected_harvest_start" in data else (getdate(doc.expected_harvest_start) if doc.expected_harvest_start else None)
		h_to = d("expected_harvest_end") if "expected_harvest_end" in data else (getdate(doc.expected_harvest_end) if doc.expected_harvest_end else None)
	except Exception:
		frappe.throw(_("One of the dates is not a date."), frappe.ValidationError)
	if not start:
		frappe.throw(_("Enter the start date."), frappe.ValidationError)
	if planting and planting > getdate(today()):
		frappe.throw(_("The planting date is in the future."), frappe.ValidationError)
	if h_from and h_to and h_to < h_from:
		frappe.throw(_("Harvest until is before harvest from."), frappe.ValidationError)
	if h_from and h_from < start:
		frappe.throw(_("Harvest from is before the start date."), frappe.ValidationError)
	for key in ("area_ha", "plant_count"):
		if key in data and flt(data[key]) < 0:
			frappe.throw(_("Area and plant count cannot be negative."), frappe.ValidationError)

	replan = (("protocol" in data and (data["protocol"] or None) != (doc.protocol or None))
		or ("start_date" in data and start != getdate(doc.start_date)))
	if "variety" in data:
		doc.variety = data["variety"] or None
	if "protocol" in data:
		doc.protocol = data["protocol"] or None
	doc.start_date, doc.planting_date = start, planting
	doc.expected_harvest_start, doc.expected_harvest_end = h_from, h_to
	if "area_ha" in data:
		doc.area_ha = flt(data["area_ha"])
	if "plant_count" in data:
		doc.plant_count = cint(data["plant_count"])
	if "notes" in data:
		doc.notes = data["notes"] or None
	doc.status = status
	if replan and status in RUNNING:
		doc.schedule_from = getdate(today())
		notes.append(_("Tasks are planned from today; nothing before today is back-filled. Tasks already in weekly plans are unchanged."))
	area = flt(doc.area_ha)  # the loaded or the edited area, before the save fetches the block's
	doc.save()
	_keep_area(doc, area)
	warnings = capacity_warnings(doc.unit) if doc.status in RUNNING else []  # the saved cycle is counted already
	return {"name": doc.name, "warnings": warnings, "notes": notes}


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
