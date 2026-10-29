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

import json
import random

import frappe
from frappe.utils import add_days, cint, flt, getdate, nowdate

from upande_production.production.logic.units import unit_filter

DEMO = {
	"seed": 20261028,
	"farm": "Mutara",
	"season": 2026,
	"price_per_kg": 95,
	"crew_available": 14,  # pickers on the avocado harvest teams (the crew now comes from the teams)
	# The blocks are the surveyed Phase 1 / Phase 2 units (see real_blocks); their master data, dry matter
	# visits, fruit counts, delivered history, typed forecasts and bad harvest row are derived from them by
	# _load() with the figures in BASE["avocado"]. Filled in at the start of run():
	"blocks": {}, "dry_matter": {}, "fruit_counts": {}, "history": {}, "early_estimates": {}, "typed_forecasts": {},
	"bad_harvest": {},
	"dm_visits": 8,
	"size_offsets": {14: -0.5, 16: -0.2, 18: 0.2, 20: 0.5},
	# Delivered history windows: the late crop of the year before and this year's early crop, with a per-block
	# shift in days so the blocks do not all pick on the same Monday.
	"windows": {"late_2025": ("2025-09-01", "2025-10-20"), "early_2026": ("2026-05-11", "2026-06-20")},
	"window_shift_days": (0, 8),
	# Harvest logs for the early crop: picks per block, packed grade split, pickers.
	"harvest": {"picks": 8, "grade_1": 0.72, "grade_2": 0.20, "kg_per_picker_day": (470, 610),
				"fruit_weight_g": (205, 235), "dm_pct": (24.4, 26.8)},
	# Season budget (whole season): price per kg and each month's share of the season's target kg
	# (the target is a multiple of what the early crop delivered).
	"budget": {"price_per_kg": 105, "target_x_early": 2.3,
			   "months": [("May", 0.17), ("June", 0.21), ("August", 0.07), ("September", 0.17),
						  ("October", 0.24), ("November", 0.14)]},
}

from upande_production.production.demo import real_blocks  # noqa: E402
from upande_production.production.demo.config import DEMO as BASE  # noqa: E402


def _load():
	"""Derive the per-block figures from the real blocks and BASE["avocado"] (deterministic per block)."""
	cfg = BASE["avocado"]
	blocks = {b["code"]: b for b in real_blocks.avocado_blocks()}
	active = [b for b in blocks.values() if b["active"]]
	DEMO["blocks"] = {c: {"variety": b["variety"], "area_ha": b["area"], "planting_year": b["planting_year"],
		"total_trees": b["trees"], "live_trees": b["live"], "sick_trees": b["sick"], "to_infill": b["infill"],
		"bearing_trees": b["bearing"], "item": b["item"]} for c, b in blocks.items()}
	sampled = [b for b in active if b["code"] in cfg["sampled"]]
	DEMO["dry_matter"], DEMO["fruit_counts"] = {}, {}
	for b in sampled:
		r = _rng(f"load:{b['code']}")
		DEMO["dry_matter"][b["code"]] = (round(r.uniform(*cfg["dm_start"]), 1), round(r.uniform(*cfg["dm_gain"]), 2))
		fc = cfg["fruit_count"]
		DEMO["fruit_counts"][b["code"]] = (round(r.uniform(*fc["per_tree"])), round(r.uniform(*fc["weight_g"])), fc["drop_pct"])
	DEMO["history"], DEMO["early_estimates"], DEMO["typed_forecasts"] = {}, {}, {}
	w = DEMO["windows"]
	for b in active:
		r = _rng(f"history:{b['code']}")
		kpt = cfg["kg_per_tree"]
		shift = r.randint(*DEMO["window_shift_days"])
		bearing = b["bearing"]
		late_s, late_e = (str(add_days(getdate(d), shift)) for d in w["late_2025"])
		early_s, early_e = (str(add_days(getdate(d), shift)) for d in w["early_2026"])
		early_kg = round(bearing * r.uniform(*kpt["early_2026"]), -2)
		DEMO["history"][b["code"]] = {
			(2024, "Year"): (round(bearing * r.uniform(*kpt["year_2024"]), -2), None, None),
			(2025, "Late"): (round(bearing * r.uniform(*kpt["late_2025"]), -2), late_s, late_e),
			(2026, "Early"): (early_kg, early_s, early_e),
		}
		DEMO["early_estimates"][b["code"]] = round(early_kg * cfg["early_estimate_share"], -2)
		DEMO["typed_forecasts"][b["code"]] = round(early_kg * cfg["typed_forecast_share"] * r.uniform(0.95, 1.05), -2)
	first = next(iter(DEMO["history"]), None)
	DEMO["bad_harvest"] = {"block": list(DEMO["history"])[1] if len(DEMO["history"]) > 1 else first,
						   "days_ago": 150, "kg": 9000, "pickers": 6}


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
	vals = {k: v for k, v in spec.items() if k not in ("item", "area_ha")}
	doc.update({"farm": farm, "status": "Active", "trees_per_ha": BASE["avocado"]["trees_per_ha"], **vals})
	# the area is the survey's: it comes from the unit, never from here
	unit = real_blocks.avocado_unit(code)
	doc.area_ha = frappe.db.get_value("Production Unit", unit, "area_ha") if unit else spec["area_ha"]
	doc.save(ignore_permissions=True)


# Demo blocks an earlier version of this seed created (the demo's own A and B are retired units now).
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
	"""Each block's outline from its warehouse (the survey), as a Feature, with the centroid and the surveyed area."""
	done = 0
	for code in DEMO["blocks"]:
		unit = real_blocks.avocado_unit(code)
		if not unit:
			continue
		raw = frappe.db.get_value("Production Unit", unit, "geojson")
		feat = real_blocks.as_feature(raw)
		if not feat:
			continue
		lat, lon = real_blocks.centroid(feat)
		props = feat.get("properties") or {}
		frappe.db.set_value("Avocado Yield Block", code, {
			"geojson": json.dumps(feat, separators=(",", ":")), "centroid_lat": lat, "centroid_lon": lon,
			"mapped_area_m2": flt(props.get("area_m2")) or flt(frappe.db.get_value("Production Unit", unit, "area_ha")) * 10000})
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
	"""Eight weekly visits per sampled block ending a week ago, four fruit sizes each. Dates are relative to
	today, so the seed's own tests (source = avocado_seed) that no longer fall on a wanted date are dropped
	and the missing ones written; a second run on the same day changes nothing."""
	today = getdate(nowdate())
	n = DEMO["dm_visits"]
	wanted = {}
	for k, (block, (start, gain)) in enumerate(DEMO["dry_matter"].items()):
		py = DEMO["blocks"][block]["planting_year"]
		later = 4 if k % 2 else 0  # every other block was visited again a few days ago, so not all are due
		for i in range(n):
			date = str(add_days(today, -7 * (n - i) + later))
			for size in DEMO["size_offsets"]:
				wanted[(block, date, size)] = (_dm(start, gain, i, size), py)
	for t in frappe.get_all(MATURITY_DT, filters={"source": "avocado_seed"},
			fields=["name", "orchard_block", "test_date", "fruit_count_size"], limit_page_length=0):
		if (t.orchard_block, str(t.test_date), cint(t.fruit_count_size)) not in wanted:
			frappe.delete_doc(MATURITY_DT, t.name, force=True, ignore_permissions=True)
	made = 0
	for (block, date, size), (dm, py) in wanted.items():
		made += _maturity_test(block, date, size, dm, py)
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
		trees = DEMO["blocks"][block]["bearing_trees"]
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
	ref = f"avocado-seed-harvest-bad-{bad['block']}"
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
	early = sum(p[(season, "Early")][0] for p in DEMO["history"].values() if (season, "Early") in p)
	for month, share in b["months"]:
		doc.append("months", {"month": month, "budget_kg": round(early * b["target_x_early"] * share, -2)})
	doc.save(ignore_permissions=True)
	return made + (0 if name else 1)


# -- one source of truth: mirror into the generic Production Harvest / Forecast -----------

def _generic_item(code):
	return DEMO["blocks"][code]["item"] if code in DEMO["blocks"] else "Hass Avocado"

BUYER = "Kakuzi Export"
COVER = (0.70, 0.90)  # buyer commitments cover this share of the forecast week


def _plausible(h):
	from upande_production.api.avocado_model import load_model
	from upande_production.api.avocadolabour import is_plausible
	return is_plausible(h, load_model())


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
		unit = real_blocks.avocado_unit(h.orchard_block)
		if not h.harvest_date or not unit or not _plausible(h):
			continue
		g1, g2 = flt(h.grade_1_kg), flt(h.grade_2_kg)
		grade = "Class 1" if g1 >= g2 and g1 else ("Class 2" if g2 else "Class 1")
		item = _generic_item(h.orchard_block)
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
	stale = [n for n in frappe.get_all("Production Harvest", filters=unit_filter({"crop": "Avocado", "harvest_batch": ("is", "not set")}),
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
	for block in DEMO["history"]:
		unit = real_blocks.avocado_unit(block)
		if not unit:
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
	frappe.defaults.set_user_default("avocado_forecast_mode", "automatic", user="Administrator")


def seed_crew():
	"""The crew is the active members of the avocado harvest teams. The main seed makes one team of six;
	a second team on another block tops the crew up to DEMO["crew_available"] distinct active pickers."""
	from upande_production.api import avocado
	from upande_production.api.avocado_model import load_model

	crop = load_model()["crop"]
	have = avocado.harvest_crew({"crop": crop})
	need = int(DEMO["crew_available"] - have)
	active = [b["name"] for b in real_blocks.active_avocado()]
	second = frappe.db.get_value("Harvest Team", {"team_number": "A2"})
	if second:  # an earlier run's team that still points at a retired block
		if frappe.db.get_value("Production Unit", frappe.db.get_value("Harvest Team", second, "unit"), "status") == "Retired" and len(active) > 1:
			frappe.db.set_value("Harvest Team", second, "unit", active[1], update_modified=False)
		return 0
	if need <= 0:
		return 0
	unit = active[1] if len(active) > 1 else (active[0] if active else None)
	on_teams = set(frappe.get_all("Harvest Team Member", pluck="employee"))
	pickers = [e for e in frappe.get_all("Employee", filters={"designation": "Value Adder", "status": "Active"},
		pluck="name", order_by="first_name, last_name") if e not in on_teams][:need]
	leader = frappe.db.get_value("Harvest Team", {"team_number": "1"}, "team_leader")
	if not (leader and pickers and unit):
		return 0
	frappe.get_doc({"doctype": "Harvest Team", "team_number": "A2", "team_leader": leader, "farm": DEMO["farm"],
		"unit": unit, "harvestors": [{"employee": e} for e in pickers]}).insert(ignore_permissions=True)
	return len(pickers)


def run(commit=True):
	frappe.flags.in_seed = True
	_load()
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
	out["crew_added"] = seed_crew()
	if commit:
		frappe.db.commit()
	print(out)
	return out
