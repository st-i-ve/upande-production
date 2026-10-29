# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

# Avocado: what the orchard will actually deliver, and when.
#
# The avocado_production app already models the orchard well — 86 blocks with
# area, trees, bearing counts, planting year — and records every harvest with
# kg, trees picked, grade split, fruit weight and dry matter. What it does not do
# is join those two facts into a number anyone can act on. This does.
#
# The arithmetic is deliberately kept in pure functions that take plain rows, so
# it can be tested without a site (see tests/test_avocado_yield.py). The
# whitelisted wrappers do nothing but fetch and hand over.
#
# Two rules carried over from the coffee module, both learned the hard way:
#   1. A measured number always beats a typed one, and the basis is reported
#      next to every figure so a guess can never pass for a measurement.
#   2. Count BEARING trees, not planted trees. Half this estate was planted in
#      2024 and bears nothing; sizing a forecast on planted trees would promise
#      a crop that physically cannot arrive.
#   3. A finished season is the only honest check on the method. Once the bins are
#      weighed, the ratio of delivered to estimated is measured, not argued about,
#      and the forecast carries it (see calibration_seasons). Until a season has
#      both an estimate and a delivery the factor is 1.0 and says so.
#   4. This estate picks TWICE a year, and a delivered crop is history. The early
#      crop is weighed and sold while the late crop is still on the trees. They are
#      forecast apart and reported apart, because adding a forecast to a crop that
#      has already been delivered prints a season nobody will pick.

import frappe
import requests
from frappe.utils import flt, cint, getdate, nowdate

from upande_production.api import avocado_model
from upande_production.api.avocado_model import dm_min_for, variety_for

BLOCK_DOCTYPE = "Avocado Orchard Block"
HARVEST_DOCTYPE = "Avocado Harvest Log"
SAMPLE_DOCTYPE = "Avocado Fruit Sample"
COUNT_DOCTYPE = "Avocado Fruit Count"
# Fallback block master, owned by this module. The avocado_production app's
# orchard master is preferred wherever it is installed; this exists so the page
# works on a site that does not have that app (and so the estate's own history
# spreadsheets have somewhere to land).
LOCAL_BLOCK_DOCTYPE = "Avocado Yield Block"

# Every parameter of the model (export dry matter window, dry matter gain, how long a
# reading stays usable, picking weeks, the yield-by-age curve, biennial bearing, the
# late crop's share of a year) lives on Production Crop / Production Variety and is
# read by avocado_model.load_model(). The functions below take that `model` as a plain
# dict; there is no estate figure in this file.

# No fruit-drop deduction unless a count says otherwise. A block someone has actually
# walked and counted drop on carries that figure.
DEFAULT_DROP_PCT = 0.0

# Moving a harvest window on a year. 52 weeks, not a calendar year: it lands on the
# same weekday and within a day or two of the same point in the season, and a pick
# that started on a Monday last September should start on a Monday this September.
SEASON_SHIFT_DAYS = 364


def biennial_factor(year, variety):
	"""1.0 in an on year, the variety's off-year factor in an off year.

	`variety` is the model's variety dict (avocado_model.variety_for). A variety with no
	biennial setting has no biennial effect: the factor is always 1.0.
	"""
	off = (variety or {}).get("off_factor")
	if not off:
		return 1.0
	is_on = (cint(year) % 2 == 0) == bool(variety.get("on_years_even"))
	return 1.0 if is_on else flt(off)


def is_on_year(year, variety):
	"""True or False for a variety that alternates; None when it has no biennial setting."""
	if not (variety or {}).get("off_factor"):
		return None
	return biennial_factor(year, variety) == 1.0


def primary_variety(blocks, model):
	"""The model variety carrying the most bearing trees (name order breaks a tie)."""
	weight = {}
	for b in blocks:
		v = variety_for(model, b.get("variety"))
		if v:
			weight[v["name"]] = weight.get(v["name"], 0.0) + flt(b.get("bearing_trees"))
	if weight:
		name = sorted(weight, key=lambda n: (-weight[n], n))[0]
		return model["varieties"][name]
	return next(iter(model["varieties"].values()), None)


def _season_part(row):
	return str(row.get("season_part") or "Year")


# Which delivered parts a typed estimate for each crop is scored against.
_CROP_PARTS = {"Early": ("Early",), "Late": ("Late",), "Whole Season": ("Year", "Early", "Late")}


def calibration_seasons(history, forecasts, budgets, season):
	"""Seasons that have both an estimate and a delivery: rows of season / estimated_kg / actual_kg.

	Estimated is what a person typed (Avocado Production Forecast, one per block and crop;
	Avocado Production Budget for a closed season with no per-block forecast). Delivered is
	Avocado Yield History. A forecast is scored only on the blocks that have both an estimate
	and a delivery, so fruit still on the trees never counts as a miss. A whole-season figure
	is scored only once the season is over (year before `season`).
	"""
	delivered = {}
	for h in history:
		kg, y = flt(h.get("kg_harvested")), cint(h.get("year"))
		if kg > 0 and y > 0:
			blk = h.get("block_code") or h.get("block")
			per_block = delivered.setdefault((y, _season_part(h)), {})
			per_block[blk] = per_block.get(blk, 0.0) + kg
	rows, scored_years = [], set()
	by_key = {}
	for f in forecasts:
		if flt(f.get("expected_kg")) > 0:
			by_key.setdefault((cint(f.get("season")), f.get("crop")), {})[f.get("orchard_block")] = flt(f["expected_kg"])
	for (y, crop), est in sorted(by_key.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
		if crop == "Whole Season" and y >= cint(season):
			continue
		act = {}
		for part in _CROP_PARTS.get(crop, ()):
			for blk, kg in delivered.get((y, part), {}).items():
				act[blk] = act.get(blk, 0.0) + kg
		both = [b for b in est if act.get(b)]
		if not both:
			continue
		rows.append({"season": y, "crop": crop, "estimated_kg": sum(est[b] for b in both),
					 "actual_kg": sum(act[b] for b in both),
					 "blocks_estimated": len(est), "blocks_harvested": len(act)})
		scored_years.add(y)
	for bud in budgets:
		y, kg = cint(bud.get("season")), flt(bud.get("budget_kg"))
		if bud.get("crop") != "Whole Season" or y >= cint(season) or y in scored_years or kg <= 0:
			continue
		act = {}
		for (hy, _part), blks in delivered.items():
			if hy == y:
				for blk, v in blks.items():
					act[blk] = act.get(blk, 0.0) + v
		if act:
			rows.append({"season": y, "crop": "Whole Season", "estimated_kg": kg,
						 "actual_kg": sum(act.values()), "blocks_estimated": 0,
						 "blocks_harvested": len(act)})
	return rows


def season_calibration(seasons=None):
	"""Delivered kilograms over estimated kilograms, across the seasons we know.

	`seasons` is rows of season / estimated_kg / actual_kg (see calibration_seasons).
	None or an empty list means there is nothing to compare against, and then the factor
	is 1.0 and the basis says exactly that — a forecast must never quietly carry a
	correction nobody measured.
	"""
	rows = [r for r in (seasons or [])
			if flt(r.get("estimated_kg")) > 0 and flt(r.get("actual_kg")) > 0]
	if not rows:
		return {"factor": 1.0, "basis": "no delivered season yet", "seasons": [],
				"estimated_kg": 0.0, "actual_kg": 0.0, "blocks_estimated": 0,
				"blocks_harvested": 0, "has_data": False}

	est = sum(flt(r.get("estimated_kg")) for r in rows)
	act = sum(flt(r.get("actual_kg")) for r in rows)
	used = sorted({cint(r.get("season")) for r in rows})
	# Kilograms add up across seasons; block counts do not. The newest season's are
	# reported, because "51 of 55 blocks picked" is a fact about one harvest.
	latest = max(rows, key=lambda r: cint(r.get("season")))
	return {
		"factor": round(act / est, 3),
		"basis": f"{len(used)} delivered season{'' if len(used) == 1 else 's'} vs "
				 f"estimate ({', '.join(str(s) for s in used)})",
		"seasons": used,
		"estimated_kg": est,
		"actual_kg": act,
		"blocks_estimated": cint(latest.get("blocks_estimated")),
		"blocks_harvested": cint(latest.get("blocks_harvested")),
		"has_data": True,
	}


def _keep(drop_pct):
	"""Share of counted fruit that still reaches the bin after an expected drop %.

	Clamped at 90%: a block losing more than that has a theft or disease problem, not
	a forecasting one, and a typo must not be able to zero the crop.
	"""
	return 1.0 - min(max(flt(drop_pct), 0.0), 90.0) / 100.0


def undo_count_drop(est_kg_per_tree, drop_pct):
	"""Strip the drop % a fruit count already shaved off its own kg/tree estimate.

	Avocado Fruit Count multiplies its estimate down by the Expected Drop % typed on
	the record. Undone here so the deduction is decided in one place — the forecast's
	drop_pct — instead of a leftover default on an old count re-applying it invisibly.
	"""
	return flt(est_kg_per_tree) / _keep(drop_pct)


def dry_matter_from_moisture(value):
	"""Their maturity sheets record MOISTURE, not dry matter.

	The tests come back as a fraction (0.77) or a percentage (77) of moisture;
	dry matter is what the exporter needs, and it is simply the remainder. Handed
	a number that is already dry matter (say 24), it is returned unchanged — the
	two ranges do not overlap for any fruit anyone would pick.
	"""
	v = flt(value)
	if v <= 0:
		return 0.0
	if v <= 1.0:          # fraction of moisture, e.g. 0.77
		return round((1.0 - v) * 100, 1)
	if v >= 50:           # percentage of moisture, e.g. 77
		return round(100 - v, 1)
	return round(v, 1)    # already dry matter


def _age(planting_year, on_date=None):
	if not planting_year:
		return None
	return getdate(on_date or nowdate()).year - cint(planting_year)


def _band(curve, age):
	"""The (from, to) key of the band an age falls in on a variety's curve."""
	if age is None:
		return None
	for lo, hi, _ in curve:
		if lo <= age <= hi:
			return (lo, hi)
	return None


def yield_curve(harvests, blocks, model):
	"""{variety: [band rows]} — kg per bearing tree for each age band, measured where we have picked it.

	A harvest log carries the kg and the number of trees it came off, so kg/tree
	is a fact, not a model. Group those facts by the age the block was when it was
	picked, and the curve stops being an opinion for every band the estate has
	actually harvested.

	Harvest logs are per block and a block can carry several varieties, so the evidence
	pools across varieties by age band: a measured band replaces the typed figure of every
	variety that has that same band, once it covers `min_trees_to_override_curve` trees.
	A variety with no yield-by-age rows has no curve (and no rows here).
	"""
	by_block = {b["name"]: b for b in blocks}
	measured = {}
	for h in harvests:
		trees = flt(h.get("trees_harvested"))
		kg = flt(h.get("total_kg"))
		blk = by_block.get(h.get("orchard_block"))
		v = variety_for(model, blk.get("variety")) if blk else None
		if not (trees and kg and v and v["curve"]):
			continue
		age = _age(blk.get("planting_year"), h.get("harvest_date"))
		band = _band(v["curve"], age)
		if not band:
			continue
		m = measured.setdefault(band, {"kg": 0.0, "trees": 0.0, "harvests": 0})
		m["kg"] += kg
		m["trees"] += trees
		m["harvests"] += 1

	curves = {}
	for name, v in model["varieties"].items():
		if not v["curve"]:
			continue
		curve = []
		for lo, hi, typed in v["curve"]:
			m = measured.get((lo, hi))
			if m and m["trees"] >= model["min_trees_to_override_curve"]:
				curve.append({"from": lo, "to": hi, "kg_per_tree": m["kg"] / m["trees"],
							  "basis": "harvested", "harvests": m["harvests"],
							  "trees": m["trees"]})
			else:
				# Not "typed": this is the estate's own recorded history, just not from
				# a harvest log on this site.
				curve.append({"from": lo, "to": hi, "kg_per_tree": typed,
							  "basis": "estate history",
							  "harvests": m["harvests"] if m else 0,
							  "trees": m["trees"] if m else 0})
		curves[name] = curve
	return curves


def curve_for(curves, model, variety):
	"""(variety name, its curve rows) for a block's variety text; (None, []) when it has none."""
	v = variety_for(model, variety)
	if v and v["name"] in curves:
		return v["name"], curves[v["name"]]
	return (v["name"] if v else None), []


def kg_per_tree(curve, age):
	for row in curve:
		if row["from"] <= (age if age is not None else -1) <= row["to"]:
			return row["kg_per_tree"], row["basis"]
	return 0.0, "not bearing"


def grade_split(harvests):
	"""Share of picked kg that made Grade 1, from what was actually packed."""
	g1 = sum(flt(h.get("grade_1_kg")) for h in harvests)
	total = sum(flt(h.get("grade_1_kg")) + flt(h.get("grade_2_kg")) + flt(h.get("reject_kg"))
				for h in harvests)
	return (g1 / total) if total else None


def data_quality(blocks, model=None):
	"""Everything in the block master that would quietly corrupt a forecast.

	Reported rather than patched: these are the orchard's own records, and a
	forecast that silently invents the missing half is worse than one that says
	what it does not know.
	"""
	issues = []
	for b in blocks:
		blk = b["name"]
		live = flt(b.get("live_trees"))
		total = flt(b.get("total_trees"))
		bearing = flt(b.get("bearing_trees"))
		if total and not live:
			issues.append({"block": blk, "issue": "no live tree count",
						   "detail": f"{total:.0f} planted, live_trees is 0 — "
									 f"nothing can be sized off this block"})
		if bearing > live and live:
			issues.append({"block": blk, "issue": "bearing exceeds live",
						   "detail": f"{bearing:.0f} bearing vs {live:.0f} live"})
		if not b.get("variety"):
			issues.append({"block": blk, "issue": "no variety",
						   "detail": "cultivar not set, so no variety-level comparison"})
		if not b.get("planting_year"):
			issues.append({"block": blk, "issue": "no planting year",
						   "detail": "tree age unknown, so no yield curve applies"})
		if model is not None and b.get("variety"):
			v = variety_for(model, b.get("variety"))
			if not (v and v["curve"]):
				issues.append({"block": blk, "issue": "no yield curve",
							   "detail": f"variety {b.get('variety')} has no yield-by-age rows "
										 f"(Settings, Varieties), so it is sized at zero"})
		# Density is the avocado version of the coffee spacing trap: the default
		# 250/ha is only right at 8 x 5 m. Anything wider is being over-counted.
		implied = _implied_density(b.get("spacing"))
		if implied and abs(implied - flt(b.get("trees_per_ha"))) > 5:
			issues.append({"block": blk, "issue": "density does not match spacing",
						   "detail": f"{b.get('spacing')} implies {implied:.0f}/ha, "
									 f"block says {flt(b.get('trees_per_ha')):.0f}/ha"})
	return issues


def _implied_density(spacing):
	"""Trees per hectare implied by an "8m x 5m" style spacing string."""
	if not spacing:
		return None
	nums = []
	for part in str(spacing).lower().replace("x", " ").split():
		part = part.replace("m", "").strip()
		try:
			nums.append(float(part))
		except ValueError:
			continue
	if len(nums) < 2 or not (nums[0] and nums[1]):
		return None
	return 10000.0 / (nums[0] * nums[1])


def dm_projection(samples, model, on_date=None, minimums=None):
	"""When each block crosses the export minimum, from its own dry matter history.

	Two samples or more give the block's own rate of gain, which is the honest
	number: it varies with the season and with how hard the block is irrigated. One
	sample can only be projected at the estate's typical rate, and that is said out
	loud. Already-there blocks report zero weeks, not a date in the past.

	The export minimum is the model's (`minimums` gives a block its own variety's).
	"""
	gain_per_week = model["dm_gain_per_week"]
	stale_weeks = model["stale_sample_weeks"]
	minimums = minimums or {}
	by_block = {}
	for s in samples:
		blk = s.get("orchard_block")
		if not blk or not flt(s.get("avg_dry_matter_pct")):
			continue
		by_block.setdefault(blk, []).append(
			{"date": getdate(s.get("sample_date")), "dm": flt(s.get("avg_dry_matter_pct"))}
		)

	out = {}
	today = getdate(on_date or nowdate())
	for blk, rows in by_block.items():
		rows.sort(key=lambda r: r["date"])
		last = rows[-1]
		slope, slope_basis = gain_per_week, "estate rate"
		# Only the readings that belong to the same crop as the last one. Dry matter
		# does not climb in a straight line from February to August: February's fruit
		# was picked in May and what is hanging now set after it. A slope drawn across
		# that boundary is arithmetic on two different crops, and the horizon that
		# makes a reading stale is exactly what makes it the wrong crop.
		recent = [r for r in rows
				  if (last["date"] - r["date"]).days / 7.0 <= stale_weeks]
		if len(recent) >= 2:
			first = recent[0]
			weeks = (last["date"] - first["date"]).days / 7.0
			if weeks > 0 and last["dm"] > first["dm"]:
				slope = (last["dm"] - first["dm"]) / weeks
				slope_basis = f"measured over {weeks:.0f} weeks"

		minimum = flt(minimums.get(blk)) or model["dm_min"]
		short = minimum - last["dm"]
		age_weeks = (today - last["date"]).days / 7.0
		stale = age_weeks > stale_weeks
		if short <= 0:
			weeks_out = 0.0
		elif stale:
			# No date at all, on purpose: an old reading cannot say where today's
			# fruit is, and a plan built on one sends trucks to an empty block.
			weeks_out = None
		else:
			weeks_out = short / slope if slope > 0 else None

		out[blk] = {
			"block": blk,
			"sample_date": str(last["date"]),
			"dry_matter_pct": last["dm"],
			"samples": len(rows),
			"gain_per_week": round(slope, 2),
			"gain_basis": slope_basis,
			"weeks_to_minimum": None if weeks_out is None else round(weeks_out, 1),
			"sample_age_weeks": round(age_weeks, 1),
			"stale": stale,
			"needs": ("a fresh sample — this reading is "
					  f"{age_weeks:.0f} weeks old and describes fruit that has been picked")
					 if stale else None,
			"ready_date": None if weeks_out is None else str(
				frappe.utils.add_days(max(last["date"], today), int(round(weeks_out * 7)))
			),
			"ready": short <= 0,
			"minimum_pct": minimum,
		}
	return out


def _pick_weights(n):
	"""Triangular: light first pick, heaviest in the middle, tailing off."""
	mid = (n - 1) / 2.0
	return [max(1.0 - abs(i - mid) / (mid + 1.0), 0.15) for i in range(n)]


def weekly_spread(rows, projection, pick_weeks, on_date=None,
				  windows=None):
	"""Block kilograms laid out week by week, starting when the fruit is legal.

	A season total tells a packhouse nothing: it needs to know which week the bins
	arrive. Dry matter dates a pick properly — below the export minimum the fruit
	cannot legally leave, whatever the calendar says — so a live reading is used
	wherever there is one.

	Where there is not, and only there, the block falls back to the weeks it was
	actually picked in the same crop last season (`windows`). That is not a maturity
	measurement and it never becomes one: it arrives with its own basis string and
	`measured_on: "last season"`, so a page can print it differently from a date the
	lab gave. What it is not is a blank calendar for a crop that is coming anyway.

	A block with neither is still left OUT rather than dumped into week one.
	"""
	today = getdate(on_date or nowdate())
	monday = frappe.utils.add_days(today, -today.weekday())
	windows = windows or {}

	grid, unscheduled, scheduled, by_basis = {}, [], [], {}
	for r in rows:
		kg = flt(r.get("expected_kg"))
		if not kg:
			continue
		p = projection.get(r["block"])
		w = windows.get(r["block"])
		if p and p.get("weeks_to_minimum") is not None:
			start = frappe.utils.add_days(monday, int(round(flt(p["weeks_to_minimum"]) * 7)))
			span, measured_on = pick_weeks, "dry matter"
			basis = (f"dry matter {p['dry_matter_pct']}% on {p['sample_date']}, "
					 f"{p['weeks_to_minimum']} weeks to the export minimum")
		elif w:
			start, span = getdate(w["start"]), cint(w["weeks"]) or pick_weeks
			measured_on, basis = "last season", w["basis"]
		else:
			unscheduled.append({"block": r["block"], "expected_kg": kg,
								"reason": "no dry matter sample and no window from last "
										  "season, so no pick date"})
			continue
		start = getdate(max(getdate(start), monday))
		start = frappe.utils.add_days(start, -getdate(start).weekday())
		weights = _pick_weights(span)
		wsum = sum(weights)
		for i, weight in enumerate(weights):
			wk = str(frappe.utils.add_days(start, i * 7))
			grid.setdefault(wk, 0.0)
			grid[wk] += kg * weight / wsum
		scheduled.append({"block": r["block"], "expected_kg": kg, "start": str(start),
						  "weeks": span, "measured_on": measured_on, "basis": basis})
		by_basis[measured_on] = round(by_basis.get(measured_on, 0.0) + kg, 0)

	weeks = sorted(grid)
	return {
		"weeks": weeks,
		"kg": [round(grid[w], 0) for w in weeks],
		"scheduled_kg": round(sum(grid.values()), 0),
		"unscheduled": sorted(unscheduled, key=lambda u: -u["expected_kg"]),
		"unscheduled_kg": round(sum(u["expected_kg"] for u in unscheduled), 0),
		"pick_weeks": pick_weeks,
		"scheduled": sorted(scheduled, key=lambda s: (s["start"], -s["expected_kg"])),
		"kg_by_basis": by_basis,
		"blocks_by_basis": {b: sum(1 for s in scheduled if s["measured_on"] == b)
							for b in by_basis},
	}


def lost_potential(blocks, curves, model, price_per_kg=0.0, on_date=None):
	"""What the orchard is losing to sick trees and gaps, in kilograms and money.

	Sized at the kg/tree the block's own age band delivers, so it is comparable
	with the forecast rather than a separate opinion. This is the list to work
	down: on this estate it is worth more than any forecasting refinement.
	"""
	rows = []
	for b in blocks:
		age = _age(b.get("planting_year"), on_date)
		_vname, curve = curve_for(curves, model, b.get("variety"))
		per_tree, _ = kg_per_tree(curve, age)
		sick = flt(b.get("sick_trees"))
		gaps = flt(b.get("to_infill"))
		# Not-yet-bearing trees are not a loss, they are a schedule.
		if not per_tree or not (sick or gaps):
			continue
		lost_kg = (sick + gaps) * per_tree
		rows.append({
			"block": b["name"],
			"farm": b.get("farm"),
			"age": age,
			"sick_trees": sick,
			"gaps": gaps,
			"live_trees": flt(b.get("live_trees")),
			"pct_sick": round(sick / flt(b.get("live_trees")) * 100, 1)
						if flt(b.get("live_trees")) else None,
			"kg_per_tree": round(per_tree, 1),
			"lost_kg": round(lost_kg, 0),
			"lost_value": round(lost_kg * flt(price_per_kg), 0) if price_per_kg else None,
		})
	rows.sort(key=lambda r: -r["lost_kg"])
	total = sum(r["lost_kg"] for r in rows)
	return {"rows": rows, "lost_kg": round(total, 0),
			"lost_value": round(total * flt(price_per_kg), 0) if price_per_kg else None}


def estimate(blocks, harvests, model, counts=None, price_per_kg=0.0, on_date=None,
			 drop_pct=DEFAULT_DROP_PCT, seasons=None):
	"""Expected kg per block for a full season, and what it is worth.

	Sized on bearing trees times the kg/tree the estate itself has recorded for
	that age. Blocks with no bearing trees return zero and say why — they are the
	majority here, and pretending otherwise is how a forecast doubles.

	Then corrected by what the last closed season actually delivered against its
	estimate, because a method that ran 14% under once will run under again until
	something changes. `seasons` is that history (see calibration_seasons); none means
	no correction.
	"""
	curves = yield_curve(harvests, blocks, model)
	primary = primary_variety(blocks, model)
	curve = curves.get(primary["name"], []) if primary else []
	g1 = grade_split(harvests)
	counts = counts or {}
	season = getdate(on_date or nowdate()).year
	swing = biennial_factor(season, primary)
	cal = season_calibration(seasons)
	keep = _keep(drop_pct)

	rows, total_kg, total_trees, bearing_total = [], 0.0, 0.0, 0.0
	for b in blocks:
		age = _age(b.get("planting_year"), on_date)
		bvar = variety_for(model, b.get("variety"))
		_vname, bcurve = curve_for(curves, model, b.get("variety"))
		per_tree, basis = kg_per_tree(bcurve, age)
		if not bcurve:
			basis = f"no yield curve for {b.get('variety') or 'a block with no variety'}"
		# A count on the trees beats any curve, measured or typed: it is this
		# block, this season, with the fruit actually hanging on it.
		counted = counts.get(b["name"])
		if counted and flt(counted.get("est_kg_per_tree")):
			per_tree = flt(counted["est_kg_per_tree"])
			basis = f"counted {counted.get('count_date')}"
		bearing = flt(b.get("bearing_trees"))
		if str(b.get("status") or "Active") != "Active":
			per_tree, basis = 0.0, b.get("status").lower()
		# The curve is an on-year number; an off year physically delivers less.
		# A count on the trees already reflects this season, so it is not swung.
		if not (counted and flt(counted.get("est_kg_per_tree"))):
			per_tree = per_tree * biennial_factor(season, bvar)
		# Calibration applies to counted blocks too: the estate's under-estimate was
		# measured against the whole crop, and a count misses fruit hidden in the
		# canopy exactly like the curve misses it.
		per_tree = per_tree * cal["factor"] * keep
		kg = per_tree * bearing
		total_kg += kg
		total_trees += flt(b.get("live_trees"))
		bearing_total += bearing
		rows.append({
			"block": b["name"],
			"farm": b.get("farm"),
			"variety": b.get("variety"),
			"planting_year": b.get("planting_year"),
			"age": age,
			"area_ha": flt(b.get("area_ha")),
			"live_trees": flt(b.get("live_trees")),
			"bearing_trees": bearing,
			"pct_bearing": round(bearing / flt(b.get("live_trees")) * 100, 1)
						   if flt(b.get("live_trees")) else None,
			"kg_per_tree": round(per_tree, 1),
			"basis": basis,
			"curve_variety": _vname,
			"expected_kg": round(kg, 0),
			"expected_grade_1_kg": round(kg * g1, 0) if g1 else None,
			"value": round(kg * flt(price_per_kg), 0) if price_per_kg else None,
		})

	rows.sort(key=lambda r: -r["expected_kg"])
	return {
		"rows": rows,
		"curve": curve,
		"curves": curves,
		"grade_1_share": round(g1, 3) if g1 else None,
		"total_kg": round(total_kg, 0),
		"total_value": round(total_kg * flt(price_per_kg), 0) if price_per_kg else None,
		"live_trees": total_trees,
		"bearing_trees": bearing_total,
		"pct_bearing": round(bearing_total / total_trees * 100, 1) if total_trees else None,
		"blocks": len(rows),
		"season": season,
		"biennial_factor": swing,
		"calibration": cal,
		"drop_pct": flt(drop_pct),
		"issues": data_quality(blocks, model),
	}


# ── The late crop: the one still on the trees ────────────────────────────────


def previous_late_crop(history, season):
	"""{block: row} — the most recent LATE crop each block delivered before `season`.

	Only rows the importer could actually split apart are eligible. A season recorded
	as one number for the whole year is not a late crop and is not treated as one:
	using it here would forecast this August off fruit picked last May as well.
	"""
	out = {}
	for h in history:
		if _season_part(h) != "Late" or cint(h.get("year")) >= cint(season):
			continue
		if flt(h.get("kg_harvested")) <= 0:
			continue
		blk = h.get("block_code") or h.get("block")
		cur = out.get(blk)
		if cur is None or cint(h.get("year")) > cint(cur.get("year")):
			out[blk] = h
	return out


def delivered_this_season(history, season, harvests=None):
	"""What this season has ALREADY put over the weighbridge. History, not forecast.

	An early crop that is weighed and gone is not on the trees any more. A page that
	adds it to a forecast for the fruit still hanging is counting the same estate
	twice, and the number it prints is one no truck will ever deliver. So it is
	returned separately, on purpose, and the late crop forecast never includes it.

	Sources, in order: the yield history (per block), then the season's harvest logs.
	With neither, nothing: no delivered figure is ever supplied from code, and
	`recorded` is False so a page can say so.
	"""
	rows = [h for h in history
			if cint(h.get("year")) == cint(season)
			and _season_part(h) in ("Year", "Early")
			and flt(h.get("kg_harvested")) > 0]
	if rows:
		return {
			"kg": round(sum(flt(h["kg_harvested"]) for h in rows), 0),
			"blocks": len({h.get("block_code") or h.get("block") for h in rows}),
			"crop": "Early" if all(_season_part(h) == "Early" for h in rows) else "Year",
			"basis": f"{season} delivered kilograms from the yield history",
			"harvest_from": None, "harvest_to": None, "recorded": True,
		}
	logs = [h for h in (harvests or [])
			if h.get("harvest_date") and getdate(h["harvest_date"]).year == cint(season)
			and flt(h.get("total_kg")) > 0]
	if logs:
		dates = sorted(getdate(h["harvest_date"]) for h in logs)
		return {
			"kg": round(sum(flt(h["total_kg"]) for h in logs), 0),
			"blocks": len({h.get("orchard_block") for h in logs}),
			"crop": None,
			"basis": f"{season} harvest logs, {len(logs)} picks",
			"harvest_from": str(dates[0]), "harvest_to": str(dates[-1]), "recorded": True,
		}
	return {"kg": 0.0, "blocks": 0, "crop": None, "harvest_from": None, "harvest_to": None,
			"recorded": False, "basis": f"nothing delivered yet in {season}"}


def _count_age_weeks(counted, today):
	d = counted.get("count_date")
	return None if not d else (today - getdate(d)).days / 7.0


def late_crop_estimate(blocks, history, model, harvests=None, counts=None, price_per_kg=0.0,
					   on_date=None, drop_pct=DEFAULT_DROP_PCT, seasons=None):
	"""Expected kg per block for the LATE crop alone, from the best evidence there is.

	Three tiers, strongest first, and every block reports which one it got:

	  1. a fruit count made for THIS crop — the block, this season, the fruit that is
		 actually hanging. Nothing beats it, and nothing older than
		 the model's stale_sample_weeks qualifies: a January count is about May's fruit.
	  2. the block's own last late crop, swung onto this half of the biennial cycle.
		 Delivered kilograms off these exact trees in this exact crop.
	  3. the age curve, cut to the variety's late-crop share of a year. A last resort,
		 and only where the variety has a share set; without one the block is not sized.

	This is a SEPARATE crop from the early one. Its kilograms are not added to the
	early crop, which is delivered and weighed — see delivered_this_season.
	"""
	curves = yield_curve(harvests or [], blocks, model)
	primary = primary_variety(blocks, model)
	curve = curves.get(primary["name"], []) if primary else []
	g1 = grade_split(harvests or [])
	counts = counts or {}
	today = getdate(on_date or nowdate())
	season = today.year
	swing = biennial_factor(season, primary)
	cal = season_calibration(seasons)
	keep = _keep(drop_pct)
	previous = previous_late_crop(history, season)

	rows, total_kg, total_trees, bearing_total, prev_total = [], 0.0, 0.0, 0.0, 0.0
	evidence_split = {}
	for b in blocks:
		age = _age(b.get("planting_year"), on_date)
		bearing = flt(b.get("bearing_trees"))
		bvar = variety_for(model, b.get("variety"))
		bswing = biennial_factor(season, bvar)
		vname, bcurve = curve_for(curves, model, b.get("variety"))
		last = previous.get(b["name"])
		prev_kg = flt(last.get("kg_harvested")) if last else 0.0
		kg, basis, evidence = 0.0, "not bearing", "none"

		if str(b.get("status") or "Active") != "Active":
			basis = str(b.get("status")).lower()
		elif not bearing:
			# Whatever this block did last year, it is sized on the trees that bear
			# now. Half this estate was planted in 2024 and bears nothing.
			basis = "no bearing trees"
		else:
			counted = counts.get(b["name"])
			age_weeks = _count_age_weeks(counted, today) if counted else None
			if (counted and flt(counted.get("est_kg_per_tree"))
					and age_weeks is not None and age_weeks <= model["stale_sample_weeks"]):
				per_tree = flt(counted["est_kg_per_tree"]) * cal["factor"] * keep
				kg = per_tree * bearing
				basis = f"counted {counted.get('count_date')} — a count on this crop"
				evidence = "fruit count"
			elif prev_kg > 0:
				# Delivered kilograms need neither calibration nor a drop deduction:
				# the weighbridge already applied both. All that is missing is which
				# half of the biennial cycle the year sat in.
				lift = bswing / biennial_factor(cint(last.get("year")), bvar)
				kg = prev_kg * lift
				basis = (f"{cint(last.get('year'))} late crop {prev_kg:,.0f} kg, "
						 f"x{lift:.2f} for the on-year swing")
				evidence = "last late crop"
			elif bvar and bvar["late_share"] and bcurve:
				per_tree, _cb = kg_per_tree(bcurve, age)
				per_tree = per_tree * bswing * bvar["late_share"] * cal["factor"] * keep
				kg = per_tree * bearing
				basis = (f"age curve at {bvar['late_share']:.0%} late-crop share — no count "
						 f"and no late crop of its own")
				evidence = "age curve"
			else:
				basis = ("no count, no late crop of its own, and no yield curve or late-crop "
						 f"share set for {b.get('variety') or 'a block with no variety'}")

		total_kg += kg
		total_trees += flt(b.get("live_trees"))
		bearing_total += bearing
		prev_total += prev_kg
		evidence_split[evidence] = evidence_split.get(evidence, 0) + 1
		rows.append({
			"block": b["name"],
			"farm": b.get("farm"),
			"variety": b.get("variety"),
			"planting_year": b.get("planting_year"),
			"age": age,
			"area_ha": flt(b.get("area_ha")),
			"live_trees": flt(b.get("live_trees")),
			"bearing_trees": bearing,
			"pct_bearing": round(bearing / flt(b.get("live_trees")) * 100, 1)
						   if flt(b.get("live_trees")) else None,
			"kg_per_tree": round(kg / bearing, 1) if bearing else 0.0,
			"basis": basis,
			"evidence": evidence,
			"curve_variety": vname,
			"previous_late_kg": round(prev_kg, 0),
			"previous_late_season": cint(last.get("year")) if last else None,
			"expected_kg": round(kg, 0),
			"expected_grade_1_kg": round(kg * g1, 0) if g1 else None,
			"value": round(kg * flt(price_per_kg), 0) if price_per_kg else None,
		})

	rows.sort(key=lambda r: -r["expected_kg"])
	return {
		"rows": rows,
		"curve": curve,
		"curves": curves,
		"crop": "Late",
		"grade_1_share": round(g1, 3) if g1 else None,
		"total_kg": round(total_kg, 0),
		"total_value": round(total_kg * flt(price_per_kg), 0) if price_per_kg else None,
		"live_trees": total_trees,
		"bearing_trees": bearing_total,
		"pct_bearing": round(bearing_total / total_trees * 100, 1) if total_trees else None,
		"blocks": len(rows),
		"season": season,
		"biennial_factor": swing,
		"calibration": cal,
		"drop_pct": flt(drop_pct),
		"late_crop_share": (primary or {}).get("late_share"),
		"evidence_split": evidence_split,
		"previous_late_kg": round(prev_total, 0),
		"previous_late_blocks": len(previous),
		"issues": data_quality(blocks, model),
	}


def seasonal_windows(history, season, on_date=None, shift_days=SEASON_SHIFT_DAYS):
	"""{block: window} — where last season's late crop puts this season's pick.

	The only honest answer when there is no dry matter to go on. The dates are the
	estate's own delivery log, moved on a year, and nothing about them is a maturity
	measurement: `measured_on` says "last season" and the basis says so in words, so
	a page can never present one as a lab result.
	"""
	out = {}
	today = getdate(on_date or nowdate())
	for blk, h in previous_late_crop(history, season).items():
		if not (h.get("harvest_start") and h.get("harvest_end")):
			continue
		shift = (cint(season) - cint(h.get("year"))) * shift_days
		start = frappe.utils.add_days(getdate(h["harvest_start"]), shift)
		end = frappe.utils.add_days(getdate(h["harvest_end"]), shift)
		# A window that has already opened starts now, not in the past — the fruit
		# left on the trees is still there to pick.
		start = max(getdate(start), today)
		end = max(getdate(end), start)
		how = h.get("window_basis") or "the dates on the harvest sheet"
		out[blk] = {
			"block": blk,
			"start": str(start),
			"end": str(end),
			"weeks": max(int((getdate(end) - getdate(start)).days / 7) + 1, 1),
			"measured_on": "last season",
			"season": cint(h.get("year")),
			"basis": f"last season's window ({how}) — no dry matter yet",
		}
	return out


# ── Site-facing wrappers ─────────────────────────────────────────────────────

BLOCK_FIELDS = ["name", "block_code", "farm", "variety", "status", "area_ha", "spacing",
				"trees_per_ha", "total_trees", "live_trees", "sick_trees", "bearing_trees",
				"planting_year"]
HARVEST_FIELDS = ["name", "harvest_date", "orchard_block", "farm", "variety", "total_kg",
				  "trees_harvested", "grade_1_kg", "grade_2_kg", "reject_kg",
				  "avg_fruit_weight_g", "dry_matter_pct", "status"]


def _block_source():
	"""Whichever block master this site actually has."""
	if frappe.db.exists("DocType", BLOCK_DOCTYPE):
		return BLOCK_DOCTYPE
	if frappe.db.exists("DocType", LOCAL_BLOCK_DOCTYPE):
		return LOCAL_BLOCK_DOCTYPE
	frappe.throw("No avocado block master on this site. Install avocado_production, "
				 "or load blocks into Avocado Yield Block.")


def _read_blocks(extra=None, farm=None):
	fields = BLOCK_FIELDS + (extra or [])
	source = _block_source()
	if source == LOCAL_BLOCK_DOCTYPE:
		# The local master has no dedicated `to_infill` equivalent to worry about —
		# it carries the same fieldnames deliberately, so nothing downstream cares
		# which of the two answered.
		pass
	filters = {"farm": farm} if farm else None
	return frappe.get_all(source, fields=fields, filters=filters, limit_page_length=0), source


def _latest_counts():
	"""{block: latest fruit count} — the newest count per block wins."""
	rows = frappe.get_all(
		COUNT_DOCTYPE,
		fields=["orchard_block", "count_date", "fruit_per_tree", "est_kg_per_tree",
				"trees_counted", "weight_basis", "drop_pct"],
		order_by="count_date asc", limit_page_length=0,
	)
	return {r.orchard_block: {"count_date": str(r.count_date),
							  "fruit_per_tree": flt(r.fruit_per_tree),
							  "est_kg_per_tree": undo_count_drop(r.est_kg_per_tree, r.drop_pct),
							  "count_drop_pct": flt(r.drop_pct),
							  "trees_counted": r.trees_counted,
							  "weight_basis": r.weight_basis}
			for r in rows if r.orchard_block}


@frappe.whitelist()
def get_blocks():
	"""Every block, for a picker. Bearing trees included so a walker knows what
	they are standing in front of."""
	rows, _ = _read_blocks()
	return sorted(rows, key=lambda r: r["name"])


@frappe.whitelist()
def get_forecast(price_per_kg=0, drop_pct=DEFAULT_DROP_PCT):
	blocks, source = _read_blocks(["to_infill"])
	harvests = (frappe.get_all(HARVEST_DOCTYPE, fields=HARVEST_FIELDS, limit_page_length=0)
				if frappe.db.exists("DocType", HARVEST_DOCTYPE) else [])
	model = avocado_model.load_model()
	out = estimate(blocks, harvests, model, counts=_latest_counts(), price_per_kg=flt(price_per_kg),
				   drop_pct=flt(drop_pct), seasons=_calibration_seasons(_history()))
	out["block_source"] = source
	out["losses"] = lost_potential(blocks, out["curves"], model, price_per_kg=flt(price_per_kg))
	return out


@frappe.whitelist()
def get_maturity():
	"""Which blocks are legally pickable, from the latest dry matter reading.

	Dry matter is what dates an avocado harvest: below the export minimum the
	fruit cannot be shipped however big it is, and picking early is the single
	most expensive mistake available on this crop.
	"""
	model = avocado_model.load_model()
	rows = _samples(model)
	minimums = block_minimums(model)
	latest = {}
	for r in rows:  # later dates overwrite earlier ones
		if r.orchard_block:
			latest[r.orchard_block] = r

	out = []
	for blk, r in latest.items():
		dm = dry_matter_from_moisture(r.avg_dry_matter_pct)
		minimum = minimums.get(blk) or model["dm_min"]
		out.append({
			"block": blk,
			"sample_date": str(r.sample_date),
			"dry_matter_pct": dm,
			"min_dry_matter_pct": flt(r.min_dry_matter_pct),
			"avg_fruit_weight_g": flt(r.avg_fruit_weight_g),
			"ready": dm >= minimum,
			"minimum_pct": minimum,
			"shortfall_pct": round(minimum - dm, 1) if dm < minimum else 0,
			"declared": r.harvest_ready,
		})
	out.sort(key=lambda r: -r["dry_matter_pct"])
	return {"minimum_pct": model["dm_min"], "maximum_pct": model["dm_max"], "blocks": out,
			"sampled": len(out)}


def block_minimums(model, blocks=None):
	"""{block: export dry matter minimum}: the block's variety target, else the crop's."""
	rows = blocks if blocks is not None else _read_blocks()[0]
	return {b["name"]: dm_min_for(model, b.get("variety")) for b in rows}


def _samples(model=None):
	"""Dry-matter readings per block, from the best source this site has.

	Preferred: a lab sample taken on the block itself. Failing that, the estate's
	maturity tests — which are run per PLANTING AREA and per export fruit size, not
	per block, so every block in a cohort inherits its cohort's reading. That is
	weaker evidence and it is labelled as such all the way through, but it is the
	difference between a harvest calendar and a blank page: at week 11 the 2018
	planting read 20.2% dry matter against a 24% export floor, and no amount of
	block-level precision changes the fact that nothing was ready to pick.
	"""
	model = model or avocado_model.load_model()
	if frappe.db.exists("DocType", SAMPLE_DOCTYPE):
		rows = frappe.get_all(
			SAMPLE_DOCTYPE,
			fields=["orchard_block", "sample_date", "avg_dry_matter_pct", "min_dry_matter_pct",
					"avg_fruit_weight_g", "harvest_ready"],
			order_by="sample_date asc", limit_page_length=0,
		)
		if rows:
			return rows
	return _cohort_samples(model)


def _cohort_samples(model):
	"""Maturity tests spread over the blocks of their planting year.

	Every week of every test is returned, not just the latest, so the projection
	can measure the cohort's OWN rate of dry-matter gain instead of assuming the
	estate default. Two tests a fortnight apart are worth more than any constant.
	"""
	if not frappe.db.exists("DocType", "Avocado Maturity Test"):
		return []

	minimums = block_minimums(model)
	fields = ["planting_year", "week_number", "test_date", "dry_matter_pct"]
	if frappe.get_meta("Avocado Maturity Test").get_field("orchard_block"):
		fields.append("orchard_block")
	tests = frappe.get_all("Avocado Maturity Test", fields=fields,
						   order_by="week_number asc", limit_page_length=0)

	# A test naming its own block is a measurement of that block and goes straight
	# through. Only the rest are spread across their planting year.
	direct = []
	for t in tests:
		if t.get("orchard_block") and flt(t.dry_matter_pct) and t.test_date:
			direct.append(frappe._dict({
				"orchard_block": t.orchard_block, "sample_date": str(t.test_date),
				"avg_dry_matter_pct": flt(t.dry_matter_pct), "min_dry_matter_pct": 0,
				"avg_fruit_weight_g": 0, "measured_on": "block",
				"harvest_ready": "Yes - Above Minimum"
								 if flt(t.dry_matter_pct) >= (minimums.get(t.orchard_block) or model["dm_min"])
								 else "No - Below Minimum",
			}))
	# One visit dries several fruit sizes; they are looks at the same fruit, so a
	# block's reading for a date is their mean, not whichever size was saved last.
	merged = {}
	for d in direct:
		merged.setdefault((d["orchard_block"], d["sample_date"]), []).append(d)
	direct = []
	for (_blk, _date), group in sorted(merged.items(), key=lambda kv: kv[0][1]):
		dm = sum(g["avg_dry_matter_pct"] for g in group) / len(group)
		first = group[0]
		first["avg_dry_matter_pct"] = dm
		first["harvest_ready"] = ("Yes - Above Minimum" if dm >= (minimums.get(_blk) or model["dm_min"])
								  else "No - Below Minimum")
		direct.append(first)
	blocks_with_own = {d["orchard_block"] for d in direct}
	tests = [t for t in tests if not t.get("orchard_block")]
	# Average the fruit sizes: a cohort is at one stage of maturity, and the sizes
	# are three looks at it rather than three different crops.
	by_cohort = {}
	for t in tests:
		if not (t.planting_year and flt(t.dry_matter_pct) and t.test_date):
			continue
		key = (cint(t.planting_year), str(t.test_date))
		agg = by_cohort.setdefault(key, {"dm": 0.0, "n": 0})
		agg["dm"] += flt(t.dry_matter_pct)
		agg["n"] += 1

	blocks_by_year = {}
	source, _ = _block_source(), None
	for b in frappe.get_all(source, fields=["name", "planting_year"], limit_page_length=0):
		if b.planting_year:
			blocks_by_year.setdefault(cint(b.planting_year), []).append(b.name)

	out = list(direct)
	for (year, date), agg in sorted(by_cohort.items(), key=lambda kv: kv[0][1]):
		dm = agg["dm"] / agg["n"]
		for block in blocks_by_year.get(year, []):
			# A block that was tested itself does not inherit its cohort's figure.
			if block in blocks_with_own:
				continue
			out.append(frappe._dict({
				"orchard_block": block, "sample_date": date, "avg_dry_matter_pct": dm,
				"min_dry_matter_pct": 0, "avg_fruit_weight_g": 0,
				"harvest_ready": "Yes - Above Minimum" if dm >= (minimums.get(block) or model["dm_min"])
								 else "No - Below Minimum",
				# Carried so a page can never present a cohort figure as a block one.
				"measured_on": "cohort",
				"cohort": f"{year} planting, {agg['n']} fruit size(s)",
			}))
	return out


RIPENING_DOCTYPE = "Avocado Ripening Test"

# How many completed shelf trials it would take before "ripens in N days" could be
# turned into a pass/fail line beside the export minimum.
#
# Three is an ASSUMPTION and is labelled as one everywhere it surfaces. The estate has
# never published a ripening threshold, and one trial cannot say what a normal
# ripening time is here — it can only say what one shelf of fruit did. Below this the
# trials are reported next to dry matter and gate nothing at all.
MIN_RIPENING_TRIALS = 3


def ripening_agreement(trials, tests, minimum, on_date=None, min_trials=MIN_RIPENING_TRIALS):
	"""Shelf trials laid beside the dry matter measured on the same fruit.

	Two independent reads on one question. Dry matter says the fruit is legal to cut;
	days to ripen says it behaves like mature fruit, because a mature Hass softens off
	the tree in a week or two and an immature one sits there. Agreeing, they are the
	strongest cheap evidence this estate can produce. Disagreeing, somebody should
	walk the orchard before the trucks are booked.

	No verdict is returned until there are enough completed trials to know what a
	normal ripening time looks like on this estate (min_trials). Until then this pairs
	the numbers, says so in words, and decides nothing.
	"""
	done = [t for t in trials if flt(t.get("avg_days_to_ripen")) > 0]
	# What the dry matter was doing in the week the fruit was cut — the same fruit, or
	# as near as these two sheets get to it. Nearest earlier reading per planting.
	by_area = {}
	for t in tests:
		if not (t.get("test_date") and flt(t.get("dry_matter_pct"))):
			continue
		by_area.setdefault(t.get("planting_area") or "unassigned", []).append(t)

	rows = []
	for t in sorted(trials, key=lambda t: str(t.get("harvest_date")), reverse=True):
		cut = getdate(t.get("harvest_date"))
		alongside = []
		for area, ts in sorted(by_area.items()):
			near = [x for x in ts if getdate(x["test_date"]) <= cut] or ts
			pick = min(near, key=lambda x: abs((getdate(x["test_date"]) - cut).days))
			same = [x for x in ts if x["test_date"] == pick["test_date"]]
			dm = round(sum(flt(x["dry_matter_pct"]) for x in same) / len(same), 1)
			alongside.append({
				"planting_area": area,
				"planting_year": pick.get("planting_year"),
				"week_number": pick.get("week_number"),
				"sample_date": str(pick["test_date"]),
				"dry_matter_pct": dm,
				"sizes": len(same),
				"ready": dm >= minimum,
				"days_off": abs((getdate(pick["test_date"]) - cut).days),
			})
		rows.append({
			"size_class": t.get("size_class"),
			"harvest_date": str(cut),
			"fruit_harvested": cint(t.get("fruit_harvested")),
			"fruit_ripe": cint(t.get("fruit_ripe")),
			"avg_days_to_ripen": flt(t.get("avg_days_to_ripen")) or None,
			"complete": flt(t.get("avg_days_to_ripen")) > 0,
			"dry_matter_that_week": alongside,
		})

	avg = (sum(flt(t["avg_days_to_ripen"]) for t in done) / len(done)) if done else None
	return {
		"trials": rows,
		"completed": len(done),
		"avg_days_to_ripen": round(avg, 1) if avg else None,
		"by_size": {s: round(sum(flt(t["avg_days_to_ripen"]) for t in done
								 if t.get("size_class") == s)
							 / sum(1 for t in done if t.get("size_class") == s), 1)
					for s in {t.get("size_class") for t in done}},
		# The whole point of the honesty: there is no threshold here, and there is no
		# verdict either. A page prints both numbers and a human reads them.
		"threshold_days": None,
		"min_trials_for_a_verdict": min_trials,
		"verdict": None if len(done) < min_trials else "enough trials to compare against",
		"gates": "nothing — days to ripen is reported beside dry matter, never instead "
				 "of it, and no pick date moves because of it",
		"basis": (f"{len(done)} completed shelf trial{'' if len(done) == 1 else 's'} of "
				  f"{len(rows)} recorded"
				  + (f", averaging {avg:.0f} days off the tree" if avg else "")
				  + (f". {min_trials} are assumed to be the fewest that could say what a "
					 f"normal ripening time is here, so this corroborates and decides "
					 f"nothing" if len(done) < min_trials else "")),
	}


HISTORY_DOCTYPE = "Avocado Yield History"


def _history():
	"""Delivered kilograms per block per crop, as far as this site has them loaded."""
	if not frappe.db.exists("DocType", HISTORY_DOCTYPE):
		return []
	fields = ["block_code", "year", "kg_harvested", "trees"]
	meta = frappe.get_meta(HISTORY_DOCTYPE)
	# A site that has the doctype but not yet the migration still answers, with one
	# crop a year and no windows. Better than a page that throws.
	fields += [f for f in ("season_part", "harvest_start", "harvest_end", "window_basis")
			   if meta.get_field(f)]
	return frappe.get_all(HISTORY_DOCTYPE, fields=fields, limit_page_length=0)


def _calibration_seasons(history):
	"""Seasons with both a typed estimate and a delivery, read from the records (see calibration_seasons)."""
	forecasts = (frappe.get_all(MANUAL_FORECAST_DOCTYPE,
								fields=["orchard_block", "season", "crop", "expected_kg"],
								limit_page_length=0)
				 if frappe.db.exists("DocType", MANUAL_FORECAST_DOCTYPE) else [])
	budgets = (frappe.get_all(MANUAL_BUDGET_DOCTYPE, fields=["season", "crop", "budget_kg"],
							  limit_page_length=0)
			   if frappe.db.exists("DocType", MANUAL_BUDGET_DOCTYPE) else [])
	return calibration_seasons(history, forecasts, budgets, getdate(nowdate()).year)


def _harvest_rows(names=None):
	rows = (frappe.get_all(HARVEST_DOCTYPE, fields=HARVEST_FIELDS, limit_page_length=0)
			if frappe.db.exists("DocType", HARVEST_DOCTYPE) else [])
	return [h for h in rows if h.orchard_block in names] if names is not None else rows


@frappe.whitelist()
def get_late_forecast(price_per_kg=0, drop_pct=DEFAULT_DROP_PCT, farm=None):
	"""The crop still on the trees, per block, and which evidence sized each one."""
	blocks, source = _read_blocks(["to_infill"], farm=farm)
	names = {b["name"] for b in blocks}
	harvests = _harvest_rows(names if farm else None)
	history = _history()
	# Calibration compares the whole estate's estimates with its deliveries, whatever farm is shown.
	seasons = _calibration_seasons(history)
	if farm:
		history = [h for h in history if (h.get("block_code") or h.get("block")) in names]
	model = avocado_model.load_model()
	out = late_crop_estimate(blocks, history, model, harvests=harvests, counts=_latest_counts(),
							 price_per_kg=flt(price_per_kg), drop_pct=flt(drop_pct), seasons=seasons)
	out["block_source"] = source
	out["losses"] = lost_potential(blocks, out["curves"], model, price_per_kg=flt(price_per_kg))
	out["model"] = model
	return out


@frappe.whitelist()
def get_ripening():
	"""The shelf trials, beside the dry matter measured on the same weeks' fruit."""
	minimum = avocado_model.load_model()["dm_min"]
	if not frappe.db.exists("DocType", RIPENING_DOCTYPE):
		return ripening_agreement([], [], minimum)
	trials = frappe.get_all(
		RIPENING_DOCTYPE,
		fields=["size_class", "harvest_date", "last_observed", "fruit_harvested",
				"fruit_ripe", "avg_days_to_ripen"],
		order_by="harvest_date asc", limit_page_length=0,
	)
	tests = (frappe.get_all("Avocado Maturity Test",
							fields=["planting_area", "planting_year", "week_number",
									"test_date", "dry_matter_pct"], limit_page_length=0)
			 if frappe.db.exists("DocType", "Avocado Maturity Test") else [])
	return ripening_agreement(trials, tests, minimum)


@frappe.whitelist()
def get_schedule(price_per_kg=0, pick_weeks=None):
	"""Week-by-week kilograms for the late crop, dated off dry matter where there is
	any and off last season's own window where there is not."""
	f = get_late_forecast(price_per_kg=price_per_kg)
	model = f["model"]
	projection = dm_projection(_samples(model), model, minimums=block_minimums(model))
	return weekly_spread(f["rows"], projection,
						 pick_weeks=cint(pick_weeks) or model["default_pick_weeks"],
						 windows=seasonal_windows(_history(), f["season"]))


@frappe.whitelist()
def overview(price_per_kg=0, farm=None):
	"""One call for a page: the crop that is coming, when it lands, what is lost.

	The forecast here is the LATE crop, because that is the crop still on the trees.
	The early crop, once delivered, sits under `delivered`, never inside `total_kg`.
	Adding the two would print a season no truck will deliver. `season_total_kg` is the pair,
	added once, for a page that wants the year.
	"""
	f = get_late_forecast(price_per_kg=price_per_kg, farm=farm)
	names = {r["block"] for r in f["rows"]}
	f["maturity"] = get_maturity()
	if farm:
		f["maturity"]["blocks"] = [b for b in f["maturity"]["blocks"] if b["block"] in names]
		f["maturity"]["sampled"] = len(f["maturity"]["blocks"])
	# The second opinion, carried alongside and never folded in: it moves no kilogram
	# and no pick date. See ripening_agreement for why it decides nothing yet.
	f["ripening"] = get_ripening()
	model = f["model"]
	projection = dm_projection(_samples(model), model, minimums=block_minimums(model))
	if farm:
		projection = {k: v for k, v in projection.items() if k in names}
	f["projection"] = sorted(projection.values(),
							 key=lambda p: (p["weeks_to_minimum"] is None,
											p["weeks_to_minimum"] or 0))
	history = _history()
	if farm:
		history = [h for h in history if (h.get("block_code") or h.get("block")) in names]
	windows = seasonal_windows(history, f["season"])
	f["windows"] = sorted(windows.values(), key=lambda w: w["start"])
	f["schedule"] = weekly_spread(f["rows"], projection, model["default_pick_weeks"], windows=windows)
	f["delivered"] = delivered_this_season(history, f["season"],
										   _harvest_rows(names))
	f["season_total_kg"] = round(flt(f["total_kg"]) + flt(f["delivered"]["kg"]), 0)
	f["season_total_value"] = (round(flt(f["season_total_kg"]) * flt(price_per_kg), 0)
							   if flt(price_per_kg) else None)
	return f


# ── Manual forecast & budget ─────────────────────────────────────────────────
#
# Everything above this line is calculated: an age curve, a dry matter sample, a
# fruit count. This section is the opposite — a person's own figure, typed on the
# production page or on the phone in the field, and saved as-is. The production
# page toggles between the two; neither ever overwrites the other, and a manual
# figure is never blended into a calculated one.

MANUAL_FORECAST_DOCTYPE = "Avocado Production Forecast"
MANUAL_BUDGET_DOCTYPE = "Avocado Production Budget"
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
			   "August", "September", "October", "November", "December"]


def _manual_forecast_rows(season=None, crop=None):
	"""The newest manual entry per block, joined onto the block master so the page
	can draw the same bearing-tree bar it draws for the calculated rows — the only
	thing swapped is where expected_kg came from."""
	filters = {}
	if season:
		filters["season"] = cint(season)
	if crop:
		filters["crop"] = crop
	else:
		# An Early entry estimates the crop that is already delivered (it is what the
		# estimate-vs-delivered card scores), not the crop still coming.
		filters["crop"] = ["!=", "Early"]
	entries = frappe.get_all(
		MANUAL_FORECAST_DOCTYPE, filters=filters,
		fields=["name", "orchard_block", "season", "crop", "expected_kg",
				"price_per_kg", "entered_by", "entry_date", "notes"],
		order_by="entry_date desc", limit_page_length=0,
	)
	blocks, _ = _read_blocks()
	by_block = {b["name"]: b for b in blocks}
	seen, rows = set(), []
	for e in entries:
		if e.orchard_block in seen:
			continue  # one row per block: the newest entry for it wins
		seen.add(e.orchard_block)
		b = by_block.get(e.orchard_block, {})
		live = flt(b.get("live_trees"))
		bearing = flt(b.get("bearing_trees"))
		kg = flt(e.expected_kg)
		rows.append({
			"block": e.orchard_block,
			"farm": b.get("farm"),
			"variety": b.get("variety"),
			"planting_year": b.get("planting_year"),
			"age": _age(b.get("planting_year")),
			"live_trees": live,
			"bearing_trees": bearing,
			"pct_bearing": round(bearing / live * 100, 1) if live else None,
			"kg_per_tree": round(kg / bearing, 1) if bearing else 0.0,
			"basis": f"typed by {e.entered_by or 'a person'} on {e.entry_date}",
			"evidence": "manual",
			"expected_kg": round(kg, 0),
			"price_per_kg": flt(e.price_per_kg) if e.price_per_kg else None,
			"value": round(kg * flt(e.price_per_kg), 0) if e.price_per_kg else None,
			"notes": e.notes,
		})
	rows.sort(key=lambda r: -r["expected_kg"])
	return rows


@frappe.whitelist()
def get_manual_forecast(season=None, crop=None, price_per_kg=0):
	"""The estate's own typed forecast, block by block — the manual half of the
	automatic/manual toggle on the production page."""
	rows = _manual_forecast_rows(season, crop)
	total_kg = sum(r["expected_kg"] for r in rows)
	live = sum(r["live_trees"] for r in rows)
	bearing = sum(r["bearing_trees"] for r in rows)
	price = flt(price_per_kg)
	typed_value = sum(r["value"] or 0 for r in rows)
	return {
		"rows": rows,
		"blocks": len(rows),
		"total_kg": round(total_kg, 0),
		"total_value": round(total_kg * price, 0) if price else (round(typed_value, 0) or None),
		"live_trees": live,
		"bearing_trees": bearing,
		"pct_bearing": round(bearing / live * 100, 1) if live else None,
		"season": cint(season) or getdate(nowdate()).year,
		"crop": crop or "Whole Season",
		"entries": len(rows),
	}


@frappe.whitelist()
def get_manual_budget(season=None, crop=None):
	"""The season's typed target. There is no calculated equivalent on purpose — a
	budget is a decision a person makes, not something arithmetic can produce — so
	this reports unset rather than inventing a number."""
	filters = {}
	if season:
		filters["season"] = cint(season)
	if crop:
		filters["crop"] = crop
	rows = frappe.get_all(
		MANUAL_BUDGET_DOCTYPE, filters=filters,
		fields=["name", "season", "crop", "budget_kg", "budget_price_per_kg",
				"budget_value", "set_by", "entry_date", "notes"],
		order_by="entry_date desc", limit_page_length=0,
	)
	if not rows:
		return {"set": False, "season": cint(season) or getdate(nowdate()).year,
				"crop": crop or "Whole Season", "months": []}
	b = rows[0]  # the newest entry for this season/crop wins
	# frappe.get_all never returns child rows, so the months come off the full doc.
	months = frappe.get_all(
		"Avocado Production Budget Month", filters={"parent": b.name},
		fields=["month", "budget_kg", "budget_value"], order_by="idx asc",
		limit_page_length=0,
	)
	month_order = {m: i for i, m in enumerate(MONTH_NAMES)}
	months.sort(key=lambda m: month_order.get(m.month, 99))
	return {
		"set": True,
		"season": b.season,
		"crop": b.crop,
		"budget_kg": flt(b.budget_kg),
		"budget_price_per_kg": flt(b.budget_price_per_kg) or None,
		"budget_value": flt(b.budget_value) or None,
		"set_by": b.set_by,
		"entry_date": str(b.entry_date) if b.entry_date else None,
		"notes": b.notes,
		"months": [{"month": m.month, "budget_kg": flt(m.budget_kg),
					"budget_value": flt(m.budget_value) if m.budget_value else None}
				   for m in months],
	}


# ── Push notifications ───────────────────────────────────────────────────────
#
# Same shape as the Mona Shelve support channel (upande_harvest/support_api.py):
# device tokens live on User.custom_expo_push_tokens — one Expo token per line,
# capped at 5 so a person carrying several phones over the years doesn't grow the
# field forever — and a push is a best-effort side effect that must never break
# the write it is reporting on.

PUSH_URL = "https://exp.host/--/api/v2/push/send"


@frappe.whitelist()
def register_push_token(token):
	"""Called by Avocado Trail right after login so this device can be pushed."""
	if not token or not str(token).startswith("ExponentPushToken"):
		frappe.throw("Invalid push token")

	user = frappe.session.user
	existing_raw = frappe.db.get_value("User", user, "custom_expo_push_tokens") or ""
	tokens = [t.strip() for t in existing_raw.splitlines() if t.strip() and t.strip() != token]
	tokens.append(token)
	tokens = tokens[-5:]
	frappe.db.set_value("User", user, "custom_expo_push_tokens", "\n".join(tokens), update_modified=False)
	frappe.db.commit()
	return {"ok": 1}


def _push_to_users(users, title, body, data=None):
	"""Best-effort: gathers every token for these users and posts one batch to
	Expo. Never raises — a push failure must not roll back the write that
	triggered it."""
	try:
		tokens = []
		for u in set(users):
			raw = frappe.db.get_value("User", u, "custom_expo_push_tokens") or ""
			tokens += [t.strip() for t in raw.splitlines() if t.strip()]
		if not tokens:
			return
		messages = [{"to": t, "title": title, "body": body, "sound": "default",
					 "channelId": "avocado", "priority": "high", "data": data or {}}
					for t in tokens]
		requests.post(PUSH_URL, json=messages, timeout=5)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "avocado push failed")


@frappe.whitelist()
def send_test_push():
	"""So the app (or whoever wired it up) can confirm the round trip actually
	works, without waiting for a real fruit count to come in."""
	_push_to_users([frappe.session.user], "Avocado Trail",
					"Push notifications are wired up.", {"kind": "test"})
	return {"ok": 1}


def notify_new_fruit_count(doc, method=None):
	"""Avocado Fruit Count after_insert hook — lets Agriculture Managers know a
	field count landed, without them having to go looking for it."""
	managers = frappe.get_all("Has Role", filters={"role": "Agriculture Manager", "parenttype": "User"},
							  pluck="parent")
	managers = [m for m in managers if m != frappe.session.user]  # not to whoever just typed it
	if not managers:
		return
	_push_to_users(
		managers, f"Fruit count: {doc.orchard_block}",
		f"{flt(doc.fruit_per_tree):.0f} fruit/tree over {cint(doc.trees_counted)} trees, "
		f"est. {flt(doc.est_block_kg):,.0f} kg.",
		{"kind": "fruit_count", "name": doc.name, "block": doc.orchard_block},
	)
