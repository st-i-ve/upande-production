# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

# Entering a dry matter test the way the lab actually runs one.
#
# A test is not one number. Fruit is sorted into export count sizes — a low count is big
# fruit and a high count small fruit — and each size is dried
# and weighed separately, because a small fruit matures ahead of a big one on the
# same tree. So one visit to one block produces up to ten readings, and the desk
# form's one-record-at-a-time is the wrong shape for that: ten saves, ten chances
# to mistype the block.
#
# The lab records MOISTURE. Dry matter is the remainder, and the export window is
# set on the avocado crop. Nobody should be doing that subtraction by hand — reading 0.77 as dry
# matter instead of moisture calls a green fruit ripe, and that is a rejected
# container.

import frappe
from frappe.utils import cint, flt, getdate, nowdate

from upande_production.api import avocado_model

DOCTYPE = "Avocado Maturity Test"

# The export count sizes and the gram band each one covers are rows on the avocado
# Production Crop (count_sizes); the window is its dry matter target and max.


def _dry_matter(moisture):
	"""Moisture as a fraction (0.77) or a percentage (77) — dry matter either way."""
	v = flt(moisture)
	if v <= 0:
		return 0.0
	if v <= 1.0:
		return round((1.0 - v) * 100, 1)
	if v >= 50:
		return round(100 - v, 1)
	# Between 1 and 50 it cannot be moisture for any fruit that exists: an avocado
	# is 60-85% water. Treated as already being dry matter.
	return round(v, 1)


@frappe.whitelist()
def get_form():
	"""Everything the entry screen needs to draw itself."""
	model = avocado_model.load_model()
	blocks, source = [], None
	try:
		from upande_production.api.avocadoapi import _read_blocks

		rows, source = _read_blocks()
		blocks = sorted(
			({"block": r["name"], "farm": r.get("farm"), "planting_year": r.get("planting_year")}
			 for r in rows),
			key=lambda r: str(r["block"]),
		)
	except Exception:
		# No block master yet is not a reason to refuse a reading — an area-level
		# test is still worth recording.
		blocks = []

	areas = sorted({a for a in frappe.get_all(DOCTYPE, pluck="planting_area", limit_page_length=0) if a})
	return {
		"blocks": blocks,
		"block_source": source,
		"areas": areas,
		"sizes": [{"count": c, "min_g": lo, "max_g": hi} for c, lo, hi in model["count_sizes"]],
		"min_pct": model["dm_min"],
		"max_pct": model["dm_max"],
		"today": nowdate(),
		"week_number": getdate(nowdate()).isocalendar()[1],
	}


@frappe.whitelist()
def save_readings(readings, orchard_block=None, planting_area=None, week_number=None,
				  test_date=None, notes=None):
	"""Save one visit: several fruit sizes for one block, in one go.

	`readings` is [{count_size, moisture}] — sizes left blank are simply not saved,
	because a size that was not tested is not a zero.
	"""
	if isinstance(readings, str):
		import json

		readings = json.loads(readings)
	model = avocado_model.load_model()

	orchard_block = (orchard_block or "").strip()
	planting_area = (planting_area or "").strip()
	if not (orchard_block or planting_area):
		frappe.throw("Say which block the fruit came off, or which planting area it "
					 "belongs to. A reading with neither cannot be used.")
	if not cint(week_number):
		frappe.throw("A week number is needed — it is how the maturity run is tracked.")

	planting_year = None
	minimum = model["dm_min"]
	if orchard_block:
		try:
			from upande_production.api.avocadoapi import _block_source

			planting_year, variety = frappe.db.get_value(_block_source(), orchard_block,
														 ["planting_year", "variety"])
			minimum = avocado_model.dm_min_for(model, variety)
		except Exception:
			planting_year = None

	saved, skipped = [], []
	for r in readings:
		size = cint(r.get("count_size"))
		moisture = r.get("moisture")
		if not size or moisture in (None, ""):
			continue
		dm = _dry_matter(moisture)
		if not dm:
			skipped.append({"count_size": size, "why": "not a reading we can use"})
			continue
		band = next((b for b in model["count_sizes"] if b[0] == size), None)
		doc = frappe.get_doc({
			"doctype": DOCTYPE,
			"orchard_block": orchard_block or None,
			"planting_area": planting_area or None,
			"planting_year": planting_year,
			"week_number": cint(week_number),
			"test_date": getdate(test_date or nowdate()),
			"fruit_count_size": size,
			"fruit_min_g": band[1] if band else None,
			"fruit_max_g": band[2] if band else None,
			"moisture_pct": flt(moisture),
			"notes": notes,
			"source": "entered on the maturity screen",
		}).insert(ignore_permissions=False)
		saved.append({"name": doc.name, "count_size": size,
					  "dry_matter_pct": flt(doc.dry_matter_pct),
					  "ready": flt(doc.dry_matter_pct) >= minimum})

	if not saved:
		frappe.throw("Nothing to save — enter the moisture for at least one fruit size.")

	frappe.db.commit()
	dms = [s["dry_matter_pct"] for s in saved]
	return {
		"saved": saved,
		"skipped": skipped,
		"average_dry_matter": round(sum(dms) / len(dms), 1),
		"ready": sum(1 for s in saved if s["ready"]),
		"of": len(saved),
		"verdict": _verdict(sum(dms) / len(dms), minimum, model["dm_max"]),
	}


def _verdict(dm, minimum, maximum):
	if dm >= maximum:
		return f"{dm:.1f}% — over the {maximum:.0f}% top of the window. Pick now."
	if dm >= minimum:
		return f"{dm:.1f}% — inside the export window. Ready to pick."
	return (f"{dm:.1f}% — below the {minimum:.0f}% export floor. "
			f"Not pickable for export yet.")


@frappe.whitelist()
def recent(orchard_block=None, limit=40):
	"""This block's own readings, newest first, with what they imply."""
	model = avocado_model.load_model()
	minimums = _block_minimums(model)
	filters = {"orchard_block": orchard_block} if orchard_block else {}
	rows = frappe.get_all(
		DOCTYPE, filters=filters,
		fields=["name", "orchard_block", "planting_area", "week_number", "test_date",
				"fruit_count_size", "moisture_pct", "dry_matter_pct"],
		order_by="test_date desc, fruit_count_size asc", limit_page_length=cint(limit) or 40,
	)
	# Group a visit back together: one date is one trip to one block, however many
	# sizes were dried.
	visits = {}
	for r in rows:
		key = (str(r.test_date), r.orchard_block or r.planting_area, r.week_number)
		v = visits.setdefault(key, {"test_date": str(r.test_date),
									"where": r.orchard_block or r.planting_area,
									"measured_on": "block" if r.orchard_block else "area",
									"week_number": r.week_number, "sizes": []})
		v["sizes"].append({"count_size": r.fruit_count_size,
						   "dry_matter_pct": flt(r.dry_matter_pct),
						   "moisture_pct": flt(r.moisture_pct)})
	out = []
	for v in visits.values():
		dms = [s["dry_matter_pct"] for s in v["sizes"] if s["dry_matter_pct"]]
		v["average_dry_matter"] = round(sum(dms) / len(dms), 1) if dms else 0
		v["ready"] = v["average_dry_matter"] >= (minimums.get(v["where"]) or model["dm_min"])
		out.append(v)
	out.sort(key=lambda v: v["test_date"], reverse=True)
	return {"visits": out, "min_pct": model["dm_min"], "max_pct": model["dm_max"]}


def _block_minimums(model):
	"""{block: export minimum}; empty where this site has no block master."""
	try:
		from upande_production.api.avocadoapi import block_minimums

		return block_minimums(model)
	except Exception:
		return {}
