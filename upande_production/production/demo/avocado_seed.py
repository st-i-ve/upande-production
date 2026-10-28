"""Idempotent demo data for the avocado forecast pages (Mutara, 2026 season).

bench --site mutara.local execute upande_production.production.demo.avocado_seed.run

Fills what the Avocado Yield doctypes need so every section of the five pages has
content: dry matter visits rising through the 24% export floor, harvest and grade
logs for the delivered early crop, yield history, typed forecasts, a season budget,
fruit counts, sick trees and gaps, and the picker crew. Blocks A and B already exist
from the main demo seed. The farm has only those two blocks: earlier versions of this
seed also made demo blocks C, D and E; run() now removes them and everything hung on
them. Each block's boundary is copied from its Production Unit's geojson.

Every invented figure is in DEMO below. Dates are relative to today so the data
never goes stale: dry matter visits are the last eight weeks, the early crop is
fixed to May-June of the season.
"""

import random

import frappe
from frappe.utils import add_days, flt, getdate, nowdate

DEMO = {
	"seed": 20261028,
	"farm": "Mutara",
	"season": 2026,
	"price_per_kg": 95,
	"crew_available": 14,  # saved as the Administrator's crew default
	# block -> master data. A and B already exist and are updated in place.
	"blocks": {
		"A": {"variety": "Hass", "area_ha": 6.5, "planting_year": 2018, "total_trees": 1040,
			  "live_trees": 1018, "sick_trees": 38, "to_infill": 22, "bearing_trees": 980},
		"B": {"variety": "Fuerte, Hass", "area_ha": 5.2, "planting_year": 2018, "total_trees": 832,
			  "live_trees": 810, "sick_trees": 29, "to_infill": 22, "bearing_trees": 790},
	},
	# Dry matter visits: block -> (DM % eight visits ago, gain per week). One visit a
	# week for eight weeks ending a week ago; four fruit sizes per visit, spread
	# around the mean by SIZE_OFFSETS. A crosses 24% in the last two visits, B is
	# about two weeks short.
	"dry_matter": {"A": (19.8, 0.68), "B": (18.6, 0.60)},
	"dm_visits": 8,
	"size_offsets": {14: -0.5, 16: -0.2, 18: 0.2, 20: 0.5},
	# Fruit counts this week (fruit per tree, fruit weight g, expected drop %).
	"fruit_counts": {"A": (365, 215, 8), "B": (330, 210, 8)},
	# Delivered history, kg: block -> {(year, part): (kg, start, end)}. 2026 Early is
	# the delivered crop (also in the harvest logs); 2025 Late is what each block's
	# own late crop did last year and dates this year's pick when there is no sample.
	"history": {
		"A": {(2024, "Year"): (93500, None, None), (2025, "Late"): (52400, "2025-09-01", "2025-10-20"),
			  (2026, "Early"): (78400, "2026-05-11", "2026-06-20")},
		"B": {(2024, "Year"): (71800, None, None), (2025, "Late"): (41300, "2025-09-08", "2025-10-27"),
			  (2026, "Early"): (59300, "2026-05-13", "2026-06-19")},
	},
	# Typed forecasts. Early = what the estate said the delivered crop would give.
	"early_estimates": {"A": 70000, "B": 64000},
	"typed_forecasts": {"A": 79000, "B": 61500},
	# Harvest logs for the early crop: picks per block, packed grade split, pickers.
	"harvest": {"picks": 8, "grade_1": 0.72, "grade_2": 0.20, "kg_per_picker_day": (470, 610),
				"fruit_weight_g": (205, 235), "dm_pct": (24.4, 26.8)},
	# One mis-keyed log (several days rolled into one row) for the data-problem list.
	"bad_harvest": {"block": "B", "days_ago": 150, "kg": 9000, "pickers": 6},
	# Season budget (whole season), kg by month, KES per kg budgeted.
	"budget": {"price_per_kg": 105, "months": [("May", 52000), ("June", 66000), ("August", 22000),
											   ("September", 52000), ("October", 74000),
											   ("November", 46000)]},
}

from upande_production.production.logic.harvest import BATCH_LOG_PREFIX  # noqa: E402

HARVEST_DT = "Avocado Harvest Log"
MATURITY_DT = "Avocado Maturity Test"


def _rng(key):
	return random.Random(f"{DEMO['seed']}:{key}")


def _upsert_block(code, spec, farm):
	if frappe.db.exists("Avocado Yield Block", code):
		doc = frappe.get_doc("Avocado Yield Block", code)
	else:
		doc = frappe.new_doc("Avocado Yield Block")
		doc.block_code = code
	doc.update({"farm": farm, "status": "Active", "trees_per_ha": 250, **spec})
	doc.save(ignore_permissions=True)


# Demo blocks an earlier version of this seed created; the farm only has A and B.
REMOVED_BLOCKS = ("C", "D", "E")
# doctype -> field holding the block code
BLOCK_CHILDREN = {
	"Avocado Maturity Test": "orchard_block",
	"Avocado Harvest Log": "orchard_block",
	"Avocado Production Forecast": "orchard_block",
	"Avocado Fruit Count": "orchard_block",
	"Avocado Yield History": "block_code",
}


def remove_demo_blocks():
	"""Delete blocks C, D, E and every record hung on them. Idempotent."""
	removed = 0
	for code in REMOVED_BLOCKS:
		for dt, field in BLOCK_CHILDREN.items():
			for name in frappe.get_all(dt, filters={field: code}, pluck="name", limit_page_length=0):
				frappe.delete_doc(dt, name, force=True, ignore_permissions=True)
				removed += 1
		if frappe.db.exists("Avocado Yield Block", code):
			frappe.delete_doc("Avocado Yield Block", code, force=True, ignore_permissions=True)
			removed += 1
	return removed


def seed_boundaries():
	"""Copy each block's boundary from its Production Unit's geojson (Avocado Block A/B)."""
	import json

	done = 0
	for code in DEMO["blocks"]:
		unit = f"Avocado Block {code}"
		if not frappe.db.exists("Production Unit", unit):
			continue
		raw = frappe.db.get_value("Production Unit", unit, "geojson")
		if not raw:
			continue
		try:
			feat = json.loads(raw)
			geom = feat.get("geometry") or feat
			ring = geom["coordinates"][0]
			lon = sum(p[0] for p in ring) / len(ring)
			lat = sum(p[1] for p in ring) / len(ring)
		except Exception:
			continue
		frappe.db.set_value("Avocado Yield Block", code,
							{"geojson": raw, "centroid_lat": round(lat, 6), "centroid_lon": round(lon, 6)})
		done += 1
	return done


def seed_blocks():
	for code, spec in DEMO["blocks"].items():
		_upsert_block(code, spec, DEMO["farm"])


def _dm(start, gain, i, size):
	return round(start + gain * i + DEMO["size_offsets"][size], 2)


def _maturity_test(block, date, size, dm, planting_year, weeks_note=None):
	if frappe.db.exists(MATURITY_DT, {"orchard_block": block, "test_date": date,
									  "fruit_count_size": size}):
		return False
	frappe.get_doc({
		"doctype": MATURITY_DT, "naming_series": "AMT-.YYYY.-.####", "orchard_block": block,
		"planting_year": planting_year, "week_number": getdate(date).isocalendar()[1],
		"test_date": date, "fruit_count_size": size,
		"moisture_pct": round(1 - dm / 100.0, 4), "source": "avocado_seed",
		"notes": weeks_note,
	}).insert(ignore_permissions=True)
	return True


def seed_dry_matter():
	# test dates are relative to today, so re-runs on another day must not stack a second
	# set: drop the seed's own tests (source = avocado_seed) and write them again.
	for n in frappe.get_all(MATURITY_DT, filters={"source": "avocado_seed"}, pluck="name", limit_page_length=0):
		frappe.delete_doc(MATURITY_DT, n, force=True, ignore_permissions=True)
	today = getdate(nowdate())
	made = 0
	n = DEMO["dm_visits"]
	for block, (start, gain) in DEMO["dry_matter"].items():
		py = DEMO["blocks"][block]["planting_year"]
		for i in range(n):
			date = str(add_days(today, -7 * (n - i)))
			for size in DEMO["size_offsets"]:
				made += _maturity_test(block, date, size, _dm(start, gain, i, size), py)
	return made


def seed_fruit_counts():
	today = getdate(nowdate())
	made = 0
	for block, (fpt, grams, drop) in DEMO["fruit_counts"].items():
		ref = f"avocado-seed-count-{block}"
		if frappe.db.exists("Avocado Fruit Count", {"client_ref": ref}):
			continue
		frappe.get_doc({
			"doctype": "Avocado Fruit Count", "naming_series": "AFC-.YYYY.-.####",
			"orchard_block": block, "count_date": add_days(today, -7), "trees_counted": 40,
			"fruit_per_tree": fpt, "avg_fruit_weight_g": grams, "drop_pct": drop,
			"client_ref": ref,
		}).insert(ignore_permissions=True)
		made += 1
	return made


def seed_history():
	made = 0
	for block, parts in DEMO["history"].items():
		trees = DEMO["blocks"][block]["total_trees"]
		for (year, part), (kg, start, end) in parts.items():
			name = f"{block}-{year}-{part}"
			if frappe.db.exists("Avocado Yield History", name):
				frappe.db.set_value("Avocado Yield History", name,
									{"kg_harvested": kg, "harvest_start": start, "harvest_end": end})
				continue
			doc = frappe.get_doc({
				"doctype": "Avocado Yield History", "block_code": block, "year": year,
				"season_part": part, "farm": DEMO["farm"], "kg_harvested": kg, "trees": trees,
				"harvest_start": start, "harvest_end": end,
				"window_basis": "the dates on the harvest sheet" if start else None,
				"source": "avocado_seed",
			})
			doc.insert(ignore_permissions=True)
			made += 1
	return made


def seed_harvest_logs():
	h = DEMO["harvest"]
	season = DEMO["season"]
	made = 0
	for block, parts in DEMO["history"].items():
		if (season, "Early") not in parts:
			continue
		kg_total, start, end = parts[(season, "Early")]
		spec = DEMO["blocks"][block]
		d0, d1 = getdate(start), getdate(end)
		span = (d1 - d0).days
		r = _rng(f"harvest:{block}")
		# Even-ish picks, heavier in the middle, scaled to the delivered total.
		weights = [1 + 0.6 * (1 - abs(i - (h["picks"] - 1) / 2) / ((h["picks"] - 1) / 2))
				   for i in range(h["picks"])]
		scale = kg_total / sum(weights)
		for i in range(h["picks"]):
			day = add_days(d0, round(span * i / (h["picks"] - 1)))
			ref = f"avocado-seed-harvest-{block}-{i}"
			if frappe.db.exists(HARVEST_DT, {"client_ref": ref}):
				continue
			kg = round(weights[i] * scale, 0)
			rate = r.uniform(*h["kg_per_picker_day"])
			g1 = round(kg * h["grade_1"] * r.uniform(0.96, 1.04), 0)
			g2 = round(kg * h["grade_2"] * r.uniform(0.95, 1.05), 0)
			frappe.get_doc({
				"doctype": HARVEST_DT, "naming_series": "AHL-.YYYY.-.####", "harvest_date": day,
				"orchard_block": block, "farm": DEMO["farm"], "variety": spec["variety"],
				"total_kg": kg, "trees_harvested": round(spec["bearing_trees"] / h["picks"]),
				"pickers_count": max(round(kg / rate), 1), "bins_harvested": round(kg / 380),
				"avg_fruit_weight_g": round(r.uniform(*h["fruit_weight_g"])),
				"dry_matter_pct": round(r.uniform(*h["dm_pct"]), 1),
				"grade_1_kg": g1, "grade_2_kg": g2, "reject_kg": max(kg - g1 - g2, 0),
				"status": "Packed", "client_ref": ref,
			}).insert(ignore_permissions=True)
			made += 1
	bad = DEMO["bad_harvest"]
	ref = "avocado-seed-harvest-bad"
	if not frappe.db.exists(HARVEST_DT, {"client_ref": ref}):
		frappe.get_doc({
			"doctype": HARVEST_DT, "naming_series": "AHL-.YYYY.-.####",
			"harvest_date": add_days(getdate(nowdate()), -bad["days_ago"]),
			"orchard_block": bad["block"], "farm": DEMO["farm"], "total_kg": bad["kg"],
			"pickers_count": bad["pickers"], "status": "Packed", "client_ref": ref,
			"notes": "Several days keyed as one row.",
		}).insert(ignore_permissions=True)
		made += 1
	return made


def seed_manual():
	season, today = DEMO["season"], nowdate()
	made = 0
	rows = [("Early", DEMO["early_estimates"]), ("Whole Season", DEMO["typed_forecasts"])]
	for crop, per_block in rows:
		for block, kg in per_block.items():
			name = frappe.db.exists("Avocado Production Forecast",
									{"orchard_block": block, "season": season, "crop": crop})
			doc = (frappe.get_doc("Avocado Production Forecast", name) if name
				   else frappe.new_doc("Avocado Production Forecast"))
			doc.update({"naming_series": "APF-.YYYY.-.####", "orchard_block": block,
						"season": season, "crop": crop, "expected_kg": kg,
						"price_per_kg": DEMO["price_per_kg"], "entry_date": today,
						"client_ref": doc.client_ref or f"avocado-seed-forecast-{crop}-{block}"})
			doc.save(ignore_permissions=True)
			made += 0 if name else 1
	b = DEMO["budget"]
	name = frappe.db.exists("Avocado Production Budget", {"season": season, "crop": "Whole Season"})
	doc = (frappe.get_doc("Avocado Production Budget", name) if name
		   else frappe.new_doc("Avocado Production Budget"))
	doc.update({"naming_series": "APB-.YYYY.-.####", "season": season, "crop": "Whole Season",
				"entry_date": add_days(getdate(today), -60), "budget_price_per_kg": b["price_per_kg"],
				"notes": "Season target agreed ahead of the early crop.",
				"client_ref": doc.client_ref or "avocado-seed-budget"})
	doc.set("months", [])
	for month, kg in b["months"]:
		doc.append("months", {"month": month, "budget_kg": kg})
	doc.save(ignore_permissions=True)
	return made + (0 if name else 1)


# -- one source of truth: mirror into the generic Production Harvest / Forecast -----------

GENERIC_ITEM = {"A": "Hass Avocado", "B": "Fuerte Avocado"}
BUYER = "Kakuzi Export"
COVER = (0.70, 0.90)  # buyer commitments cover this share of the forecast week


def _plausible(h):
	from upande_production.api.avocadolabour import is_plausible
	return is_plausible(h)


def _unit_cycle(unit):
	return frappe.db.get_value("Production Crop Cycle", {"unit": unit, "status": ("in", ["Harvesting", "Active"])}, "name")


def mirror_harvests():
	"""Every valid Avocado Harvest Log becomes a Production Harvest on its block's unit."""
	price = DEMO["price_per_kg"]
	logs = frappe.get_all(HARVEST_DT, fields=["name", "orchard_block", "harvest_date", "total_kg",
		"pickers_count", "grade_1_kg", "grade_2_kg", "client_ref"], limit_page_length=0)
	keep, made = set(), 0
	for h in logs:
		if (h.client_ref or "").startswith(BATCH_LOG_PREFIX):
			continue  # a Harvest Batch writes its own Production Harvest; mirroring the log would count it twice
		unit = f"Avocado Block {h.orchard_block}"
		if not h.harvest_date or not frappe.db.exists("Production Unit", unit) or not _plausible(h):
			continue
		g1, g2 = flt(h.grade_1_kg), flt(h.grade_2_kg)
		grade = "Class 1" if g1 >= g2 and g1 else ("Class 2" if g2 else "Class 1")
		item = GENERIC_ITEM.get(h.orchard_block)
		vals = {"harvest_date": h.harvest_date, "unit": unit, "crop": "Avocado", "cycle": _unit_cycle(unit),
				"item": item, "qty": flt(h.total_kg), "uom": "Kg", "grade": grade, "price_per_uom": price}
		# the log's own name is the identity: unit + date + qty (a log is one dated event)
		name = frappe.db.exists("Production Harvest", {"unit": unit, "harvest_date": h.harvest_date, "qty": flt(h.total_kg)})
		if name:
			doc = frappe.get_doc("Production Harvest", name)
			doc.update(vals)
			doc.save(ignore_permissions=True)
		else:
			doc = frappe.get_doc({"doctype": "Production Harvest", **vals})
			doc.insert(ignore_permissions=True)
			made += 1
		keep.add(doc.name)
	stale = [n for n in frappe.get_all("Production Harvest", filters={"crop": "Avocado", "harvest_batch": ("is", "not set")},
									   pluck="name", limit_page_length=0) if n not in keep]
	for n in stale:
		frappe.delete_doc("Production Harvest", n, force=True, ignore_permissions=True)
	return made, len(stale)


def _early_weeks():
	"""Early-crop estimate per block spread over its pick weeks the way the picks were weighted."""
	out = {}
	for block, est in DEMO["early_estimates"].items():
		parts = DEMO["history"][block][(DEMO["season"], "Early")]
		d0, d1 = getdate(parts[1]), getdate(parts[2])
		n = DEMO["harvest"]["picks"]
		span = (d1 - d0).days
		weights = [1 + 0.6 * (1 - abs(i - (n - 1) / 2) / ((n - 1) / 2)) for i in range(n)]
		tot = sum(weights)
		wk = {}
		for i in range(n):
			day = add_days(d0, round(span * i / (n - 1)))
			ws = str(add_days(day, -getdate(day).weekday()))
			wk[ws] = wk.get(ws, 0.0) + est * weights[i] / tot
		out[block] = wk
	return out


def _late_weeks(f):
	"""The Season Outlook timeline's forecast, split per block (same spread as weekly_spread)."""
	from upande_production.api import avocadoapi
	out = {}
	for s in f["schedule"]["scheduled"]:
		weights = avocadoapi._pick_weights(s["weeks"])
		tot = sum(weights)
		wk = out.setdefault(s["block"], {})
		for i, w in enumerate(weights):
			ws = str(add_days(getdate(s["start"]), i * 7))
			wk[ws] = wk.get(ws, 0.0) + s["expected_kg"] * w / tot
	return out


def mirror_forecast():
	"""Weekly Avocado forecast (early estimate in its pick weeks, late crop from the outlook
	schedule) into one Production Forecast per block for the season. Returns {week: kg}."""
	from upande_production.api import avocadoapi
	f = avocadoapi.overview(price_per_kg=DEMO["price_per_kg"])
	early, late = _early_weeks(), _late_weeks(f)
	total = {}
	for block in DEMO["blocks"]:
		unit = f"Avocado Block {block}"
		if not frappe.db.exists("Production Unit", unit):
			continue
		weeks = {}
		for src in (early.get(block, {}), late.get(block, {})):
			for ws, kg in src.items():
				weeks[ws] = weeks.get(ws, 0.0) + kg
		name = frappe.db.exists("Production Forecast", {"unit": unit, "season": DEMO["season"]})
		doc = frappe.get_doc("Production Forecast", name) if name else frappe.new_doc("Production Forecast")
		doc.update({"unit": unit, "crop": "Avocado", "cycle": _unit_cycle(unit), "season": DEMO["season"],
					"source": "Manual", "uom": "Kg"})
		doc.set("weeks", [])
		for ws in sorted(weeks):
			doc.append("weeks", {"week_start": ws, "expected_qty": round(weeks[ws], 1)})
			total[ws] = total.get(ws, 0.0) + round(weeks[ws], 1)
		doc.save(ignore_permissions=True)
	return total


def mirror_commitments(week_totals):
	"""Kakuzi Export commits 70-90% of each coming forecast week; replaces older avocado offers."""
	cust = frappe.db.get_value("Customer", {"customer_name": BUYER})
	if not cust:
		return 0
	monday = add_days(getdate(nowdate()), -getdate(nowdate()).weekday())
	keep, made = set(), 0
	for i, ws in enumerate(sorted(w for w in week_totals if getdate(w) > monday)[:6]):
		kg = week_totals[ws]
		cover = _rng(f"commit:{ws}").uniform(*COVER)
		vals = {"customer": cust, "crop": "Avocado", "item": "Hass Avocado", "week_start": ws,
				"committed_qty": round(kg * cover, -1), "uom": "Kg", "price_per_uom": DEMO["price_per_kg"],
				"status": "Confirmed" if i < 3 else "Open"}
		name = frappe.db.exists("Buyer Commitment", {"customer": cust, "item": "Hass Avocado", "week_start": ws})
		if name:
			frappe.db.set_value("Buyer Commitment", name, vals)
		else:
			name = frappe.get_doc({"doctype": "Buyer Commitment", **vals}).insert(ignore_permissions=True).name
			made += 1
		keep.add(name)
	for n in frappe.get_all("Buyer Commitment", filters={"crop": "Avocado"}, pluck="name"):
		if n not in keep:
			frappe.delete_doc("Buyer Commitment", n, force=True, ignore_permissions=True)
	return made


def seed_generic_mirror():
	harvests, dropped = mirror_harvests()
	totals = mirror_forecast()
	commitments = mirror_commitments(totals)
	return {"harvests_mirrored_new": harvests, "stale_avocado_harvests_removed": dropped,
			"forecast_weeks": len(totals), "commitments_new": commitments}


def seed_prefs():
	frappe.defaults.set_user_default("avocado_price_per_kg", DEMO["price_per_kg"], user="Administrator")
	frappe.defaults.set_user_default("avocado_crew_available", DEMO["crew_available"], user="Administrator")
	frappe.defaults.set_user_default("avocado_forecast_mode", "automatic", user="Administrator")


def run(commit=True):
	frappe.flags.in_seed = True
	out = {"demo_block_records_removed": remove_demo_blocks()}
	seed_blocks()
	out["boundaries_copied"] = seed_boundaries()
	out["dry_matter_tests_created"] = seed_dry_matter()
	out["fruit_counts_created"] = seed_fruit_counts()
	out["history_rows_created"] = seed_history()
	out["harvest_logs_created"] = seed_harvest_logs()
	out["manual_or_budget_created"] = seed_manual()
	out.update(seed_generic_mirror())
	seed_prefs()
	if commit:
		frappe.db.commit()
	print(out)
	return out
