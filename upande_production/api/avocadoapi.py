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
#      and the forecast carries it (see SEASON_CALIBRATION).
#   4. This estate picks TWICE a year, and a delivered crop is history. The 2026
#      early crop is 1,185.4 t, weighed and sold; the late crop is still on the
#      trees. They are forecast apart and reported apart, because adding a forecast
#      to a crop that has already been delivered prints a season nobody will pick.

import frappe
import requests
from frappe.utils import flt, cint, getdate, nowdate

BLOCK_DOCTYPE = "Avocado Orchard Block"
HARVEST_DOCTYPE = "Avocado Harvest Log"
SAMPLE_DOCTYPE = "Avocado Fruit Sample"
COUNT_DOCTYPE = "Avocado Fruit Count"
# Fallback block master, owned by this module. The avocado_production app's
# orchard master is preferred wherever it is installed; this exists so the page
# works on a site that does not have that app (and so the estate's own history
# spreadsheets have somewhere to land).
LOCAL_BLOCK_DOCTYPE = "Avocado Yield Block"

# Kenyan export minimum for Hass. Below this the fruit is not legally pickable
# for export, whatever it weighs — so it dates the harvest, not the size of it.
MIN_DRY_MATTER_PCT = 24.0

# Dry matter climbs as the fruit sits on the tree. Kenyan Hass runs roughly
# 0.5-1.0 points a week through maturation, so a block two points short is about
# three weeks off. Used only where a block has a single sample; with two or more
# the block's own slope is measured instead.
DEFAULT_DM_GAIN_PER_WEEK = 0.7

# A dry matter reading describes the fruit that was hanging when it was taken. The
# 2026 readings were 9 Feb to 9 Mar; that fruit was picked in May and June. Running
# such a reading forward at a weekly gain would date a pick in September for a crop
# that no longer exists, which is worse than saying nothing. Past this age a block
# is reported as needing a fresh sample instead of being given a date.
STALE_SAMPLE_WEEKS = 8

# Once a block is legal to pick it is not stripped in a day. Spread over this many
# weeks, heaviest in the middle, which is how the packhouse actually sees it.
DEFAULT_PICK_WEEKS = 6

# kg of fruit per PLANTED tree by tree age, measured on this estate.
#
# Source: "Master Yield Summary - edit July 2025", the 2018 planting (LK01-12,
# 22.83 ha, 5,708 trees) plus the 2022 and 2023 plantings, divided by planted
# trees at 250/ha:
#
#   age 2 (2020)  12.1     age 5 (2023)  63.1
#   age 3 (2021)   3.6 *   age 6 (2024)  97.1
#   age 4 (2022)  34.6     age 7 (2025)  56.6 *
#   (* off years — see BIENNIAL below)
#
# The younger plantings agree: the 2022 blocks gave 1.1-4.9 t/block at age 3 and
# the 2023 blocks 0.1-0.6 t at age 2. Bands are set from the ON-year figures and
# the off-year factor is applied separately, because averaging the two produces a
# number the orchard never actually delivers in any given year.
ESTATE_AGE_CURVE = [
	(0, 1, 0.0),
	(2, 2, 12.0),
	(3, 3, 12.0),
	(4, 4, 35.0),
	(5, 5, 63.0),
	(6, 6, 97.0),
	(7, 9, 90.0),
	(10, 99, 90.0),
]
DEFAULT_AGE_CURVE = ESTATE_AGE_CURVE

# Avocado alternates hard. This estate: 97.1 kg/tree in 2024 against 56.6 in
# 2025, and 12.1 in 2020 against 3.6 in 2021 — an off year runs 0.58 of an on
# year on the mature blocks. 2024 and 2026 are on years, 2025 was off.
BIENNIAL_OFF_FACTOR = 0.58
ON_YEARS_ARE_EVEN = True

# A harvest log only overrides the estate curve once it covers a real season's
# worth of trees. Four demo rows off 690 trees must not rewrite a curve built on
# 5,708 trees of history.
MIN_TREES_TO_OVERRIDE_CURVE = 1000

# No fruit-drop deduction by default. The estate's own 2026 estimate deducted
# nothing for drop and STILL came in 14% under what was delivered (1,037.7 t
# estimated, 1,185.4 t picked), so shaving 10% off this crop moves the forecast
# further from reality, not closer. The parameter stays because a block someone has
# actually walked and counted drop on deserves to carry that figure.
DEFAULT_DROP_PCT = 0.0

# Season calibration: the estate's own estimate against what the bins weighed.
#
# Source: the estate's Avocado Overview dashboard, first crop 2026 — 1,037.7 t
# estimated across 55 blocks, 1,185.4 t delivered off 51 blocks, i.e. 114.2%.
# One season is thin, but a measured 1.142 beats an assumed 1.0. Append a row per
# season as they close (or point this at a history doctype); the arithmetic below
# averages whatever it is given.
SEASON_CALIBRATION = [
	{"season": 2026, "estimated_kg": 1037700.0, "actual_kg": 1185400.0,
	 "blocks_estimated": 55, "blocks_harvested": 51,
	 # Which crop those kilograms are. This estate picks twice: the 2026 early crop
	 # ran 11 May to 20 June and is delivered, weighed and sold. It is history, and
	 # the late crop forecast must never be added on top of the same fruit.
	 "crop": "Early", "harvest_from": "2026-05-11", "harvest_to": "2026-06-20"},
]

# ── The late crop ────────────────────────────────────────────────────────────
#
# Two crops a year, and every number above was built for one of them at a time. The
# late crop is due now, August into September, and nobody has counted it: the
# estate's own Aug-2026 sheet has an empty Bearing Trees column for every block.

# The late crop's share of a delivered year, measured on this estate.
#
# 2025: 434,362 kg came off the late crop (the Sept 2025 harvest sheet, Actual
# column, 56 blocks) against 513,248 kg delivered across the whole year (the Master
# Yield Summary) — 84.6%. High, because the young plantings gave no early crop at
# all that season, so this is the estate at its most late-crop-heavy. It is used
# ONLY where a block has neither a count nor a late crop of its own to go on, and
# every block that uses it says so.
LATE_CROP_SHARE = 0.846

# A fruit count is evidence about the fruit that was hanging when it was made. The
# 2026 early-crop counts were made in January for fruit picked in May; carried into
# the late crop they would forecast a crop that is already sold. Same rule and the
# same number of weeks as a dry matter reading, for the same reason.
LATE_COUNT_MAX_AGE_WEEKS = STALE_SAMPLE_WEEKS

# Moving a harvest window on a year. 52 weeks, not a calendar year: it lands on the
# same weekday and within a day or two of the same point in the season, and a pick
# that started on a Monday last September should start on a Monday this September.
SEASON_SHIFT_DAYS = 364


def biennial_factor(year, on_years_even=ON_YEARS_ARE_EVEN):
	"""1.0 in an on year, BIENNIAL_OFF_FACTOR in an off year."""
	is_on = (cint(year) % 2 == 0) == bool(on_years_even)
	return 1.0 if is_on else BIENNIAL_OFF_FACTOR


def season_calibration(seasons=None):
	"""Delivered kilograms over estimated kilograms, across the seasons we know.

	`seasons` is rows of season / estimated_kg / actual_kg. None means the estate's
	own closed seasons (SEASON_CALIBRATION). An empty list means there is nothing to
	compare against, and then the factor is 1.0 and the basis says exactly that — a
	forecast must never quietly carry a correction nobody measured.
	"""
	rows = [r for r in (SEASON_CALIBRATION if seasons is None else seasons)
			if flt(r.get("estimated_kg")) > 0 and flt(r.get("actual_kg")) > 0]
	if not rows:
		return {"factor": 1.0, "basis": "no delivered season to compare against",
				"seasons": [], "estimated_kg": 0.0, "actual_kg": 0.0,
				"blocks_estimated": 0, "blocks_harvested": 0}

	est = sum(flt(r.get("estimated_kg")) for r in rows)
	act = sum(flt(r.get("actual_kg")) for r in rows)
	used = sorted(cint(r.get("season")) for r in rows)
	# Kilograms add up across seasons; block counts do not. The newest season's are
	# reported, because "51 of 55 blocks picked" is a fact about one harvest.
	latest = max(rows, key=lambda r: cint(r.get("season")))
	return {
		"factor": round(act / est, 3),
		"basis": f"{len(rows)} delivered season{'' if len(rows) == 1 else 's'} vs "
				 f"estimate ({', '.join(str(s) for s in used)})",
		"seasons": used,
		"estimated_kg": est,
		"actual_kg": act,
		"blocks_estimated": cint(latest.get("blocks_estimated")),
		"blocks_harvested": cint(latest.get("blocks_harvested")),
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


def _band(age):
	"""The curve band an age falls in, as a (from, to) key."""
	if age is None:
		return None
	for lo, hi, _ in DEFAULT_AGE_CURVE:
		if lo <= age <= hi:
			return (lo, hi)
	return None


def yield_curve(harvests, blocks):
	"""kg per bearing tree for each age band — measured where we have picked it.

	A harvest log carries the kg and the number of trees it came off, so kg/tree
	is a fact, not a model. Group those facts by the age the block was when it was
	picked, and the curve stops being an opinion for every band the estate has
	actually harvested.
	"""
	by_block = {b["name"]: b for b in blocks}
	measured = {}
	for h in harvests:
		trees = flt(h.get("trees_harvested"))
		kg = flt(h.get("total_kg"))
		blk = by_block.get(h.get("orchard_block"))
		if not (trees and kg and blk):
			continue
		age = _age(blk.get("planting_year"), h.get("harvest_date"))
		band = _band(age)
		if not band:
			continue
		m = measured.setdefault(band, {"kg": 0.0, "trees": 0.0, "harvests": 0})
		m["kg"] += kg
		m["trees"] += trees
		m["harvests"] += 1

	curve = []
	for lo, hi, typed in DEFAULT_AGE_CURVE:
		m = measured.get((lo, hi))
		if m and m["trees"] >= MIN_TREES_TO_OVERRIDE_CURVE:
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
	return curve


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


def data_quality(blocks):
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


def dm_projection(samples, on_date=None, gain_per_week=DEFAULT_DM_GAIN_PER_WEEK):
	"""When each block crosses the export minimum, from its own dry matter history.

	Two samples or more give the block's own rate of gain, which is the honest
	number: it varies with the season and with how hard the block is irrigated. One
	sample can only be projected at the estate's typical rate, and that is said out
	loud. Already-there blocks report zero weeks, not a date in the past.
	"""
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
				  if (last["date"] - r["date"]).days / 7.0 <= STALE_SAMPLE_WEEKS]
		if len(recent) >= 2:
			first = recent[0]
			weeks = (last["date"] - first["date"]).days / 7.0
			if weeks > 0 and last["dm"] > first["dm"]:
				slope = (last["dm"] - first["dm"]) / weeks
				slope_basis = f"measured over {weeks:.0f} weeks"

		short = MIN_DRY_MATTER_PCT - last["dm"]
		age_weeks = (today - last["date"]).days / 7.0
		stale = age_weeks > STALE_SAMPLE_WEEKS
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
		}
	return out


def _pick_weights(n):
	"""Triangular: light first pick, heaviest in the middle, tailing off."""
	mid = (n - 1) / 2.0
	return [max(1.0 - abs(i - mid) / (mid + 1.0), 0.15) for i in range(n)]


def weekly_spread(rows, projection, pick_weeks=DEFAULT_PICK_WEEKS, on_date=None,
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


def lost_potential(blocks, curve, price_per_kg=0.0, on_date=None):
	"""What the orchard is losing to sick trees and gaps, in kilograms and money.

	Sized at the kg/tree the block's own age band delivers, so it is comparable
	with the forecast rather than a separate opinion. This is the list to work
	down: on this estate it is worth more than any forecasting refinement.
	"""
	rows = []
	for b in blocks:
		age = _age(b.get("planting_year"), on_date)
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


def estimate(blocks, harvests, counts=None, price_per_kg=0.0, on_date=None,
			 drop_pct=DEFAULT_DROP_PCT, seasons=None):
	"""Expected kg per block for a full season, and what it is worth.

	Sized on bearing trees times the kg/tree the estate itself has recorded for
	that age. Blocks with no bearing trees return zero and say why — they are the
	majority here, and pretending otherwise is how a forecast doubles.

	Then corrected by what the last closed season actually delivered against its
	estimate, because a method that ran 14% under once will run under again until
	something changes. `seasons` overrides that history (see season_calibration).
	"""
	curve = yield_curve(harvests, blocks)
	g1 = grade_split(harvests)
	counts = counts or {}
	season = getdate(on_date or nowdate()).year
	swing = biennial_factor(season)
	cal = season_calibration(seasons)
	keep = _keep(drop_pct)

	rows, total_kg, total_trees, bearing_total = [], 0.0, 0.0, 0.0
	for b in blocks:
		age = _age(b.get("planting_year"), on_date)
		per_tree, basis = kg_per_tree(curve, age)
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
			per_tree = per_tree * swing
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
			"expected_kg": round(kg, 0),
			"expected_grade_1_kg": round(kg * g1, 0) if g1 else None,
			"value": round(kg * flt(price_per_kg), 0) if price_per_kg else None,
		})

	rows.sort(key=lambda r: -r["expected_kg"])
	return {
		"rows": rows,
		"curve": curve,
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
		"issues": data_quality(blocks),
	}


# ── The late crop: the one still on the trees ────────────────────────────────


def _season_part(row):
	return str(row.get("season_part") or "Year")


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


def delivered_this_season(history, season, seasons=None):
	"""What this season has ALREADY put over the weighbridge. History, not forecast.

	The 2026 early crop is 1,185.4 t, picked 11 May to 20 June, weighed and gone. A
	page that adds it to a forecast for the fruit still hanging is counting the same
	estate twice, and the number it prints is one no truck will ever deliver. So it
	is returned separately, on purpose, and the late crop forecast never includes it.

	Preferred source is the yield history, because that is per block. The closed
	season calibration is the fallback, and it is where the 2026 early crop lives
	until someone loads it block by block.
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
			"harvest_from": None, "harvest_to": None,
		}
	for r in (SEASON_CALIBRATION if seasons is None else seasons):
		if cint(r.get("season")) == cint(season) and flt(r.get("actual_kg")) > 0:
			return {
				"kg": round(flt(r["actual_kg"]), 0),
				"blocks": cint(r.get("blocks_harvested")),
				"crop": r.get("crop") or "Early",
				"basis": f"{season} {str(r.get('crop') or 'early').lower()} crop, "
						 f"delivered and weighed",
				"harvest_from": r.get("harvest_from"), "harvest_to": r.get("harvest_to"),
			}
	return {"kg": 0.0, "blocks": 0, "crop": None, "harvest_from": None, "harvest_to": None,
			"basis": f"nothing delivered yet in {season}"}


def _count_age_weeks(counted, today):
	d = counted.get("count_date")
	return None if not d else (today - getdate(d)).days / 7.0


def late_crop_estimate(blocks, history, harvests=None, counts=None, price_per_kg=0.0,
					   on_date=None, drop_pct=DEFAULT_DROP_PCT, seasons=None):
	"""Expected kg per block for the LATE crop alone, from the best evidence there is.

	Three tiers, strongest first, and every block reports which one it got:

	  1. a fruit count made for THIS crop — the block, this season, the fruit that is
		 actually hanging. Nothing beats it, and nothing older than
		 LATE_COUNT_MAX_AGE_WEEKS qualifies: a January count is about May's fruit.
	  2. the block's own last late crop, swung onto this half of the biennial cycle.
		 Delivered kilograms off these exact trees in this exact crop, and 2026 is an
		 on year against 2025's off one.
	  3. the age curve, cut to the late crop's share of a year. A last resort, and on
		 this estate a rare one.

	This is a SEPARATE crop from the early one. Its kilograms are not added to the
	2026 early crop, which is delivered and weighed — see delivered_this_season.
	"""
	curve = yield_curve(harvests or [], blocks)
	g1 = grade_split(harvests or [])
	counts = counts or {}
	today = getdate(on_date or nowdate())
	season = today.year
	swing = biennial_factor(season)
	cal = season_calibration(seasons)
	keep = _keep(drop_pct)
	previous = previous_late_crop(history, season)

	rows, total_kg, total_trees, bearing_total, prev_total = [], 0.0, 0.0, 0.0, 0.0
	evidence_split = {}
	for b in blocks:
		age = _age(b.get("planting_year"), on_date)
		bearing = flt(b.get("bearing_trees"))
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
					and age_weeks is not None and age_weeks <= LATE_COUNT_MAX_AGE_WEEKS):
				per_tree = flt(counted["est_kg_per_tree"]) * cal["factor"] * keep
				kg = per_tree * bearing
				basis = f"counted {counted.get('count_date')} — a count on this crop"
				evidence = "fruit count"
			elif prev_kg > 0:
				# Delivered kilograms need neither calibration nor a drop deduction:
				# the weighbridge already applied both. All that is missing is which
				# half of the biennial cycle the year sat in.
				lift = swing / biennial_factor(cint(last.get("year")))
				kg = prev_kg * lift
				basis = (f"{cint(last.get('year'))} late crop {prev_kg:,.0f} kg, "
						 f"x{lift:.2f} for the on-year swing")
				evidence = "last late crop"
			else:
				per_tree, _cb = kg_per_tree(curve, age)
				per_tree = per_tree * swing * LATE_CROP_SHARE * cal["factor"] * keep
				kg = per_tree * bearing
				basis = (f"age curve at {LATE_CROP_SHARE:.0%} late-crop share — no count "
						 f"and no late crop of its own")
				evidence = "age curve"

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
		"late_crop_share": LATE_CROP_SHARE,
		"evidence_split": evidence_split,
		"previous_late_kg": round(prev_total, 0),
		"previous_late_blocks": len(previous),
		"issues": data_quality(blocks),
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
	out = estimate(blocks, harvests, counts=_latest_counts(), price_per_kg=flt(price_per_kg),
				   drop_pct=flt(drop_pct))
	out["block_source"] = source
	out["losses"] = lost_potential(blocks, out["curve"], price_per_kg=flt(price_per_kg))
	return out


@frappe.whitelist()
def get_maturity():
	"""Which blocks are legally pickable, from the latest dry matter reading.

	Dry matter is what dates an avocado harvest: below the export minimum the
	fruit cannot be shipped however big it is, and picking early is the single
	most expensive mistake available on this crop.
	"""
	rows = _samples()
	latest = {}
	for r in rows:  # later dates overwrite earlier ones
		if r.orchard_block:
			latest[r.orchard_block] = r

	out = []
	for blk, r in latest.items():
		dm = dry_matter_from_moisture(r.avg_dry_matter_pct)
		out.append({
			"block": blk,
			"sample_date": str(r.sample_date),
			"dry_matter_pct": dm,
			"min_dry_matter_pct": flt(r.min_dry_matter_pct),
			"avg_fruit_weight_g": flt(r.avg_fruit_weight_g),
			"ready": dm >= MIN_DRY_MATTER_PCT,
			"shortfall_pct": round(MIN_DRY_MATTER_PCT - dm, 1) if dm < MIN_DRY_MATTER_PCT else 0,
			"declared": r.harvest_ready,
		})
	out.sort(key=lambda r: -r["dry_matter_pct"])
	return {"minimum_pct": MIN_DRY_MATTER_PCT, "blocks": out, "sampled": len(out)}


def _samples():
	"""Dry-matter readings per block, from the best source this site has.

	Preferred: a lab sample taken on the block itself. Failing that, the estate's
	maturity tests — which are run per PLANTING AREA and per export fruit size, not
	per block, so every block in a cohort inherits its cohort's reading. That is
	weaker evidence and it is labelled as such all the way through, but it is the
	difference between a harvest calendar and a blank page: at week 11 the 2018
	planting read 20.2% dry matter against a 24% export floor, and no amount of
	block-level precision changes the fact that nothing was ready to pick.
	"""
	if frappe.db.exists("DocType", SAMPLE_DOCTYPE):
		rows = frappe.get_all(
			SAMPLE_DOCTYPE,
			fields=["orchard_block", "sample_date", "avg_dry_matter_pct", "min_dry_matter_pct",
					"avg_fruit_weight_g", "harvest_ready"],
			order_by="sample_date asc", limit_page_length=0,
		)
		if rows:
			return rows
	return _cohort_samples()


def _cohort_samples():
	"""Maturity tests spread over the blocks of their planting year.

	Every week of every test is returned, not just the latest, so the projection
	can measure the cohort's OWN rate of dry-matter gain instead of assuming the
	estate default. Two tests a fortnight apart are worth more than any constant.
	"""
	if not frappe.db.exists("DocType", "Avocado Maturity Test"):
		return []

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
				"harvest_ready": "Yes - Above Minimum" if flt(t.dry_matter_pct) >= MIN_DRY_MATTER_PCT
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
		first["harvest_ready"] = ("Yes - Above Minimum" if dm >= MIN_DRY_MATTER_PCT
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
				"harvest_ready": "Yes - Above Minimum" if dm >= MIN_DRY_MATTER_PCT else "No - Below Minimum",
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


def ripening_agreement(trials, tests, on_date=None, min_trials=MIN_RIPENING_TRIALS):
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
				"ready": dm >= MIN_DRY_MATTER_PCT,
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


@frappe.whitelist()
def get_late_forecast(price_per_kg=0, drop_pct=DEFAULT_DROP_PCT, farm=None):
	"""The crop still on the trees, per block, and which evidence sized each one."""
	blocks, source = _read_blocks(["to_infill"], farm=farm)
	names = {b["name"] for b in blocks}
	harvests = (frappe.get_all(HARVEST_DOCTYPE, fields=HARVEST_FIELDS, limit_page_length=0)
				if frappe.db.exists("DocType", HARVEST_DOCTYPE) else [])
	if farm:
		harvests = [h for h in harvests if h.orchard_block in names]
	history = _history()
	if farm:
		history = [h for h in history if (h.get("block_code") or h.get("block")) in names]
	out = late_crop_estimate(blocks, history, harvests=harvests, counts=_latest_counts(),
							 price_per_kg=flt(price_per_kg), drop_pct=flt(drop_pct))
	out["block_source"] = source
	out["losses"] = lost_potential(blocks, out["curve"], price_per_kg=flt(price_per_kg))
	return out


@frappe.whitelist()
def get_ripening():
	"""The shelf trials, beside the dry matter measured on the same weeks' fruit."""
	if not frappe.db.exists("DocType", RIPENING_DOCTYPE):
		return ripening_agreement([], [])
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
	return ripening_agreement(trials, tests)


@frappe.whitelist()
def get_schedule(price_per_kg=0, pick_weeks=DEFAULT_PICK_WEEKS):
	"""Week-by-week kilograms for the late crop, dated off dry matter where there is
	any and off last season's own window where there is not."""
	f = get_late_forecast(price_per_kg=price_per_kg)
	projection = dm_projection(_samples())
	return weekly_spread(f["rows"], projection,
						 pick_weeks=cint(pick_weeks) or DEFAULT_PICK_WEEKS,
						 windows=seasonal_windows(_history(), f["season"]))


@frappe.whitelist()
def overview(price_per_kg=0, farm=None):
	"""One call for a page: the crop that is coming, when it lands, what is lost.

	The forecast here is the LATE crop, because that is the crop still on the trees.
	The 2026 early crop is delivered — 1,185.4 t weighed off 51 blocks between 11 May
	and 20 June — and it sits under `delivered`, never inside `total_kg`. Adding the
	two would print a season no truck will deliver. `season_total_kg` is the pair,
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
	projection = dm_projection(_samples())
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
	f["schedule"] = weekly_spread(f["rows"], projection, windows=windows)
	f["delivered"] = delivered_this_season(history, f["season"])
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
