# Self-check for the avocado yield arithmetic.
#
# Uses real rows from the estate: the two harvests actually recorded, and a
# representative slice of the 86 orchard blocks (an old bearing block, the young
# 2022 block that was harvested, a 2023 block part-way into bearing, a 2024 block
# bearing nothing, and the Saboti blocks whose tree counts are missing).
#
# Run: env/bin/python -m upande_production.tests.test_avocado_yield
#      (no site needed — the arithmetic takes plain rows, and the spreadsheet parse is
#       run against a miniature of the estate's own sheet written into a temp dir)

import os
import tempfile
from datetime import date

from upande_production.api.avocadoapi import (
	DEFAULT_DROP_PCT, MIN_RIPENING_TRIALS, biennial_factor, calibration_seasons,
	data_quality, delivered_this_season, dm_projection, dry_matter_from_moisture, estimate,
	grade_split, is_on_year, kg_per_tree, late_crop_estimate, lost_potential,
	previous_late_crop, ripening_agreement, season_calibration, seasonal_windows,
	undo_count_drop, weekly_spread, yield_curve, _implied_density,
)
from upande_production.tests.avocado_model_fixture import CAL_SEASONS, MODEL

HASS = MODEL["varieties"]["Hass"]
BIENNIAL_OFF_FACTOR = HASS["off_factor"]
LATE_CROP_SHARE = HASS["late_share"]
STALE_SAMPLE_WEEKS = MODEL["stale_sample_weeks"]
PICK_WEEKS = MODEL["default_pick_weeks"]

TODAY = "2026-08-05"

# What a closed season measured (the fixture's estimate against its delivery). Every
# expected_kg below carries it, because the forecast does.
CAL = season_calibration(CAL_SEASONS)["factor"]

BLOCKS = [
	# name, farm, variety, status, area, spacing, /ha, total, live, sick, bearing, year
	dict(name="LA9", farm="Lokitela", variety="Hass", status="Active", area_ha=2.2,
		 spacing=None, trees_per_ha=250, total_trees=550, live_trees=507, sick_trees=96,
		 bearing_trees=202.0, planting_year=2018),
	dict(name="LB-BONDENI 2", farm="Lokitela", variety="Hass", status="Active", area_ha=2.52,
		 spacing=None, trees_per_ha=250, total_trees=630, live_trees=594, sick_trees=0,
		 bearing_trees=488.0, planting_year=2022),
	dict(name="LC-MIMA 1", farm="Lokitela", variety="Hass", status="Active", area_ha=4.16,
		 spacing=None, trees_per_ha=250, total_trees=1040, live_trees=1017, sick_trees=0,
		 bearing_trees=240.0, planting_year=2023),
	dict(name="LD-AIRSTRIP 1", farm="Lokitela", variety="Hass", status="Active", area_ha=3.4,
		 spacing=None, trees_per_ha=250, total_trees=850, live_trees=842, sick_trees=0,
		 bearing_trees=0.0, planting_year=2024),
	dict(name="SB4", farm="Saboti", variety="Golden Hass", status="Active", area_ha=17.08,
		 spacing="5m x 8m", trees_per_ha=250, total_trees=4270, live_trees=0, sick_trees=0,
		 bearing_trees=0.0, planting_year=2024),
	dict(name="SB5", farm="Saboti", variety="Golden Hass", status="Active", area_ha=11.852,
		 spacing="8m x 7m", trees_per_ha=250, total_trees=2963, live_trees=0, sick_trees=0,
		 bearing_trees=0.0, planting_year=2025),
]

HARVESTS = [
	dict(name="AHL-2026-0003", harvest_date="2025-09-05", orchard_block="LA9",
		 total_kg=3030.0, trees_harvested=202, grade_1_kg=2575.0, grade_2_kg=364.0,
		 reject_kg=91.0, avg_fruit_weight_g=230.0, dry_matter_pct=25.2),
	dict(name="AHL-2026-0004", harvest_date="2025-09-10", orchard_block="LB-BONDENI 2",
		 total_kg=7320.0, trees_harvested=488, grade_1_kg=6222.0, grade_2_kg=878.0,
		 reject_kg=220.0, avg_fruit_weight_g=215.0, dry_matter_pct=23.5),
]

# Delivered kilograms, in the shape the importer writes them: the year split into the
# two crops this estate actually picks wherever the late one is known block by block,
# and left whole where it is not. LA9 and LB-BONDENI 2 carry the Sept 2025 late crop
# and the dates it left the block; LC-MIMA 1 carries nothing, which is what makes it
# the block that has to fall back to the age curve.
HISTORY = [
	dict(block_code="LA9", year=2025, season_part="Early", kg_harvested=3510.0),
	dict(block_code="LA9", year=2025, season_part="Late", kg_harvested=3030.0, trees=202,
		 harvest_start="2025-09-01", harvest_end="2025-09-13",
		 window_basis="its own dates in the delivery log"),
	dict(block_code="LA9", year=2024, season_part="Year", kg_harvested=9100.0),
	# A whole-year row is NOT a late crop, and this one is bigger than the late crop
	# beside it: if the preference order ever reads it, the forecast jumps and the
	# basis string still claims to be quoting a late crop.
	dict(block_code="LB-BONDENI 2", year=2024, season_part="Year", kg_harvested=6890.0),
	dict(block_code="LB-BONDENI 2", year=2025, season_part="Late", kg_harvested=4564.9,
		 trees=488, harvest_start="2025-09-15", harvest_end="2025-09-18",
		 window_basis="the 2022 Planting window — this block was not named in the "
					  "delivery log"),
]

# The lift an on year gives last season's late crop: 2026 is on, 2025 was off.
LIFT = biennial_factor(2026, HASS) / biennial_factor(2025, HASS)


def main():
	# 1. The curve is measured where the estate has picked, typed elsewhere.
	curves = yield_curve(HARVESTS, BLOCKS, MODEL)
	curve = curves["Hass"]
	by_band = {(r["from"], r["to"]): r for r in curve}

	# Two demo harvest rows (488 and 202 trees) must NOT rewrite a curve built on
	# 5,708 trees of recorded history — that is what the tree threshold is for.
	b3 = by_band[(3, 3)]
	assert b3["basis"] == "estate history", b3
	assert abs(b3["kg_per_tree"] - 12.0) < 0.01, b3
	b7 = by_band[(7, 9)]
	assert b7["basis"] == "estate history", b7

	# A real season does override it.
	big = yield_curve(HARVESTS + [dict(harvest_date="2025-09-20", orchard_block="LA9",
									   total_kg=90000.0, trees_harvested=1500)], BLOCKS, MODEL)
	b7big = {(r["from"], r["to"]): r for r in big["Hass"]}[(7, 9)]
	assert b7big["basis"] == "harvested", b7big
	assert abs(b7big["kg_per_tree"] - (90000 + 3030) / 1702) < 0.1, b7big

	# The estate's own measured shape: age 6 is the peak, age 0-1 nothing.
	assert abs(by_band[(6, 6)]["kg_per_tree"] - 97.0) < 0.01
	assert by_band[(0, 1)]["kg_per_tree"] == 0.0

	# 2. Grade 1 share comes from what was packed, not a target.
	g1 = grade_split(HARVESTS)
	assert abs(g1 - (2575 + 6222) / (3030 + 7320)) < 1e-9, g1
	assert 0.84 < g1 < 0.86, g1

	# 3. Age drives the curve; a first crop really does arrive at age 2 here
	#    (68.9 t off the 2018 planting in 2020). Nothing before that.
	assert kg_per_tree(curve, 2)[0] == 12.0
	assert kg_per_tree(curve, 1)[0] == 0.0
	assert kg_per_tree(curve, None)[0] == 0.0

	# 4. Whole-estate estimate.
	est = estimate(BLOCKS, HARVESTS, MODEL, seasons=CAL_SEASONS, price_per_kg=95.0, on_date=TODAY)
	rows = {r["block"]: r for r in est["rows"]}

	# 2026 is an on year, so the curve is not discounted.
	assert est["season"] == 2026 and est["biennial_factor"] == 1.0

	# LB-BONDENI 2 is 4 now: 35 kg/tree off the estate's own 2022 season.
	assert rows["LB-BONDENI 2"]["age"] == 4
	assert rows["LB-BONDENI 2"]["basis"] == "estate history"
	assert rows["LB-BONDENI 2"]["expected_kg"] == round(35.0 * CAL * 488, 0)

	# LA9 is 8: the mature band.
	assert rows["LA9"]["age"] == 8
	assert rows["LA9"]["expected_kg"] == round(90.0 * CAL * 202, 0)

	# An off year physically delivers less, and the total has to fall with it.
	off = estimate(BLOCKS, HARVESTS, MODEL, seasons=CAL_SEASONS, price_per_kg=95.0, on_date="2027-08-05")
	assert off["biennial_factor"] == BIENNIAL_OFF_FACTOR
	off_rows = {r["block"]: r for r in off["rows"]}
	assert off_rows["LA9"]["expected_kg"] == round(90.0 * BIENNIAL_OFF_FACTOR * CAL * 202, 0), \
		off_rows["LA9"]
	assert biennial_factor(2024, HASS) == 1.0 and biennial_factor(2025, HASS) == BIENNIAL_OFF_FACTOR

	# Their maturity sheets record MOISTURE. 0.77 moisture is 23% dry matter, one
	# point short of export — reading it as 0.77% dry matter would call a green
	# fruit ripe.
	assert dry_matter_from_moisture(0.77) == 23.0
	assert dry_matter_from_moisture(77) == 23.0
	assert dry_matter_from_moisture(24) == 24.0
	assert dry_matter_from_moisture(0.86) == 14.0
	assert dry_matter_from_moisture(None) == 0.0

	# The 2024 plantings bear nothing and must contribute nothing.
	assert rows["LD-AIRSTRIP 1"]["expected_kg"] == 0
	assert rows["SB4"]["expected_kg"] == 0

	# Value follows the same kg, and Grade 1 is split off it.
	assert rows["LA9"]["value"] == round(90.0 * CAL * 202 * 95.0, 0)
	assert rows["LA9"]["expected_grade_1_kg"] == round(90.0 * CAL * 202 * g1, 0)

	# 5. A count on the trees overrides the curve for that block, and says so.
	counted = estimate(BLOCKS, HARVESTS, MODEL, seasons=CAL_SEASONS, counts={
		"LA9": {"est_kg_per_tree": 28.4, "count_date": "2026-08-01"},
	}, price_per_kg=95.0, on_date=TODAY)
	la9 = {r["block"]: r for r in counted["rows"]}["LA9"]
	assert la9["basis"] == "counted 2026-08-01", la9
	assert la9["expected_kg"] == round(28.4 * CAL * 202, 0), la9
	# A count on a block bearing nothing still forecasts nothing.
	sb4 = {r["block"]: r for r in counted["rows"]}["SB4"]
	assert sb4["expected_kg"] == 0

	# 6. Data quality: the gaps that would otherwise be invented silently.
	issues = {(i["block"], i["issue"]) for i in data_quality(BLOCKS)}
	assert ("SB4", "no live tree count") in issues
	assert ("SB5", "density does not match spacing") in issues   # 8x7 is 178/ha, not 250
	assert ("LA9", "no variety") in {(i["block"], i["issue"])
									 for i in data_quality([dict(BLOCKS[0], variety=None)])}
	# A block whose variety has no yield-by-age rows is said to be sized at zero.
	assert ("SB4", "no yield curve") in {(i["block"], i["issue"]) for i in data_quality(BLOCKS, MODEL)}
	assert ("SB4", "density does not match spacing") not in issues  # 5x8 IS 250/ha

	assert abs(_implied_density("8m x 7m") - 178.57) < 0.1
	assert abs(_implied_density("8m x 5m") - 250.0) < 0.1
	assert _implied_density(None) is None

	# 7. Dry matter projection: two samples give the block's own rate of gain.
	samples = [
		# LA9 climbing 1.0 point a week, already past 24% -> pickable now.
		dict(orchard_block="LA9", sample_date="2026-07-15", avg_dry_matter_pct=23.2),
		dict(orchard_block="LA9", sample_date="2026-07-29", avg_dry_matter_pct=25.2),
		# LB-BONDENI 2 has one sample only, 2.1 points short -> estate rate, 3 weeks.
		dict(orchard_block="LB-BONDENI 2", sample_date="2026-08-01", avg_dry_matter_pct=21.9),
	]
	proj = dm_projection(samples, MODEL, on_date=TODAY)
	assert proj["LA9"]["ready"] is True
	assert proj["LA9"]["weeks_to_minimum"] == 0.0
	assert abs(proj["LA9"]["gain_per_week"] - 1.0) < 0.01, proj["LA9"]
	assert proj["LA9"]["gain_basis"].startswith("measured"), proj["LA9"]

	b2 = proj["LB-BONDENI 2"]
	assert b2["ready"] is False
	assert b2["gain_basis"] == "estate rate"
	assert abs(b2["weeks_to_minimum"] - 2.1 / 0.7) < 0.05, b2   # 3.0 weeks

	# 7b. A reading older than a couple of months describes fruit that has already
	#     been picked. It must produce no pick date at all — the 2026 readings were
	#     taken in February and that crop came off in May.
	old = dm_projection([
		dict(orchard_block="LA9", sample_date="2026-02-09", avg_dry_matter_pct=19.4),
		dict(orchard_block="LA9", sample_date="2026-03-09", avg_dry_matter_pct=21.8),
	], MODEL, on_date="2026-08-05")["LA9"]
	assert old["stale"] is True, old
	assert old["weeks_to_minimum"] is None, old
	assert old["ready_date"] is None, old
	assert old["sample_age_weeks"] > 20, old
	assert "fresh sample" in old["needs"], old
	# A block already over the line stays pickable even on an old reading: the
	# fruit was ripe then and cannot have gone backwards.
	ripe_old = dm_projection([
		dict(orchard_block="LK06", sample_date="2026-02-09", avg_dry_matter_pct=25.0),
	], MODEL, on_date="2026-08-05")["LK06"]
	assert ripe_old["ready"] is True and ripe_old["weeks_to_minimum"] == 0.0, ripe_old
	# A recent reading is unaffected.
	assert proj["LB-BONDENI 2"]["stale"] is False, proj["LB-BONDENI 2"]

	# 8. The weekly spread starts when the fruit is legal, and refuses to invent a
	#    date for a block nobody has sampled.
	sched = weekly_spread(est["rows"], proj, PICK_WEEKS, on_date=TODAY)
	assert len(sched["weeks"]) >= 6, sched["weeks"]
	assert abs(sched["scheduled_kg"] - (rows["LA9"]["expected_kg"]
									   + rows["LB-BONDENI 2"]["expected_kg"])) < 2, sched
	# LC-MIMA 1 has fruit forecast but no sample: unscheduled, and named.
	unsched = {u["block"] for u in sched["unscheduled"]}
	assert "LC-MIMA 1" in unsched, sched["unscheduled"]
	assert sched["unscheduled_kg"] == rows["LC-MIMA 1"]["expected_kg"]
	# LA9 is pickable now, so its first week is this week's Monday, not later.
	assert sched["weeks"][0] == "2026-08-03", sched["weeks"][:3]

	# 9. Lost potential: sick trees priced at what that age band actually gives.
	loss = lost_potential(BLOCKS, curves, MODEL, price_per_kg=95.0, on_date=TODAY)
	la9_loss = {r["block"]: r for r in loss["rows"]}["LA9"]
	assert la9_loss["sick_trees"] == 96
	assert la9_loss["lost_kg"] == round(96 * 90.0, 0), la9_loss
	assert la9_loss["lost_value"] == round(96 * 90.0 * 95.0, 0)
	assert la9_loss["pct_sick"] == round(96 / 507 * 100, 1)
	# A block bearing nothing yet is a schedule, not a loss.
	assert "LD-AIRSTRIP 1" not in {r["block"] for r in loss["rows"]}

	# 10. Season calibration: a season estimated at 1,037.7 t and delivered at 1,185.4 t
	#     means the method runs 14.2% under and the forecast has to say so.
	cal = season_calibration(CAL_SEASONS)
	assert cal["factor"] == 1.142, cal
	assert cal["seasons"] == [2026], cal
	assert cal["estimated_kg"] == 1037700.0 and cal["actual_kg"] == 1185400.0, cal
	assert "2026" in cal["basis"] and "1 delivered season" in cal["basis"], cal
	# 51 blocks picked against 55 estimated: four blocks nobody harvested.
	assert cal["blocks_estimated"] == 55 and cal["blocks_harvested"] == 51, cal

	# With nothing delivered there is nothing to calibrate on, and it must say that
	# rather than invent a factor.
	none_yet = season_calibration([])
	assert none_yet["factor"] == 1.0, none_yet
	assert none_yet["seasons"] == [] and "no delivered season" in none_yet["basis"], none_yet
	assert none_yet["has_data"] is False and cal["has_data"] is True
	assert season_calibration()["factor"] == 1.0, "no seasons given means no correction"
	assert season_calibration([dict(season=2027, estimated_kg=0, actual_kg=0)])["factor"] == 1.0

	# Several seasons are pooled, not averaged block-by-block: 200 estimated against
	# 240 delivered is 1.2 however it is split across the years.
	multi = season_calibration([
		dict(season=2025, estimated_kg=100000, actual_kg=110000),
		dict(season=2026, estimated_kg=100000, actual_kg=130000),
	])
	assert multi["factor"] == 1.2 and multi["seasons"] == [2025, 2026], multi
	assert "2 delivered seasons" in multi["basis"], multi

	# The factor reaches the payload and every block in it.
	assert est["calibration"] == cal, est["calibration"]
	raw = estimate(BLOCKS, HARVESTS, MODEL, price_per_kg=95.0, on_date=TODAY, seasons=[])
	assert raw["calibration"]["factor"] == 1.0
	assert abs(est["total_kg"] - raw["total_kg"] * CAL) < 2, (est["total_kg"], raw["total_kg"])
	assert est["total_kg"] > raw["total_kg"], "calibration must not be silently dropped"

	# 11. No fruit-drop deduction by default: the estate's own no-deduction estimate
	#     still came in 14% under, so shaving 10% off would be wrong twice over.
	assert DEFAULT_DROP_PCT == 0.0
	assert est["drop_pct"] == 0.0
	assert rows["LA9"]["kg_per_tree"] == round(90.0 * CAL, 1), rows["LA9"]

	# The parameter survives for a block where drop was actually measured.
	dropped = estimate(BLOCKS, HARVESTS, MODEL, seasons=CAL_SEASONS, price_per_kg=95.0, on_date=TODAY, drop_pct=10)
	assert dropped["drop_pct"] == 10.0
	d_la9 = {r["block"]: r for r in dropped["rows"]}["LA9"]
	assert d_la9["expected_kg"] == round(90.0 * CAL * 0.9 * 202, 0), d_la9

	# A count doc shaves its own Expected Drop % off before we ever see it; the
	# forecast puts that back so the deduction is decided in exactly one place.
	assert abs(undo_count_drop(198.0, 10) - 220.0) < 1e-9
	assert undo_count_drop(220.0, 0) == 220.0
	# Clamped at 90%, so it is never a divide by zero however wild the typed figure.
	assert abs(undo_count_drop(22.0, 100) - 220.0) < 1e-9

	# 12. The LATE crop, which is the one still on the trees on 5 August. Three tiers
	#     of evidence, strongest first, and every block has to say which it got.
	late = late_crop_estimate(BLOCKS, HISTORY, MODEL, seasons=CAL_SEASONS, harvests=HARVESTS,
							  price_per_kg=95.0, on_date=TODAY)
	lrows = {r["block"]: r for r in late["rows"]}
	assert late["crop"] == "Late" and late["season"] == 2026

	# (b) LA9 has no count, so its own 2025 late crop, swung onto the on year.
	la9l = lrows["LA9"]
	assert la9l["evidence"] == "last late crop", la9l
	assert la9l["expected_kg"] == round(3030.0 * LIFT, 0), la9l
	assert la9l["expected_kg"] > 3030.0, "an on year has to lift last year's late crop"
	assert "2025 late crop" in la9l["basis"] and "on-year swing" in la9l["basis"], la9l
	# Delivered kilograms are already calibrated and already have their drop taken:
	# the weighbridge did both. Applying either again would inflate a measured fact.
	assert CAL > 1.0 and la9l["expected_kg"] != round(3030.0 * LIFT * CAL, 0), la9l

	# The whole-year row next door must not be mistaken for a late crop.
	assert lrows["LB-BONDENI 2"]["expected_kg"] == round(4564.9 * LIFT, 0), lrows["LB-BONDENI 2"]
	assert lrows["LB-BONDENI 2"]["previous_late_season"] == 2025
	assert set(previous_late_crop(HISTORY, 2026)) == {"LA9", "LB-BONDENI 2"}
	assert previous_late_crop(HISTORY, 2026)["LA9"]["kg_harvested"] == 3030.0
	# ...and neither must a late crop from the season being forecast.
	assert previous_late_crop(HISTORY + [dict(block_code="LA9", year=2026,
											  season_part="Late", kg_harvested=99999.0)],
							  2026)["LA9"]["kg_harvested"] == 3030.0

	# (c) LC-MIMA 1 has no count and no late crop of its own: the age curve, cut to
	#     the late crop's measured share of a year. Last resort, and it says so.
	mima = lrows["LC-MIMA 1"]
	assert mima["evidence"] == "age curve", mima
	assert mima["expected_kg"] == round(12.0 * LATE_CROP_SHARE * CAL * 240, 0), mima
	assert "late-crop share" in mima["basis"], mima
	assert mima["previous_late_kg"] == 0
	# The curve is a whole YEAR's kilograms per tree. Handed to one crop uncut it
	# would forecast this August the fruit of last May as well.
	assert mima["kg_per_tree"] < 12.0 * CAL, mima
	assert {r["block"]: r for r in estimate(BLOCKS, HARVESTS, MODEL, seasons=CAL_SEASONS,
											on_date=TODAY)["rows"]
			}["LC-MIMA 1"]["expected_kg"] > mima["expected_kg"], "a crop is not a year"

	# A whole-year row and an early crop are not late crops, whatever year they sit
	# in. Read either as one and a block inherits a number off fruit already sold.
	contaminated = HISTORY + [
		dict(block_code="LA9", year=2025, season_part="Early", kg_harvested=99999.0),
		dict(block_code="LC-MIMA 1", year=2025, season_part="Year", kg_harvested=99999.0),
	]
	assert previous_late_crop(contaminated, 2026)["LA9"]["kg_harvested"] == 3030.0
	assert "LC-MIMA 1" not in previous_late_crop(contaminated, 2026)
	crows = {r["block"]: r for r in late_crop_estimate(
		BLOCKS, contaminated, MODEL, seasons=CAL_SEASONS, harvests=HARVESTS, on_date=TODAY)["rows"]}
	assert crows["LC-MIMA 1"]["evidence"] == "age curve", crows["LC-MIMA 1"]
	assert crows["LA9"]["expected_kg"] == la9l["expected_kg"], crows["LA9"]

	# Blocks that bear nothing forecast nothing, in the late crop as in the early one.
	assert lrows["LD-AIRSTRIP 1"]["expected_kg"] == 0
	assert lrows["SB4"]["expected_kg"] == 0 and lrows["SB4"]["evidence"] == "none"
	assert lrows["SB4"]["basis"] == "no bearing trees"

	# (a) A count made on THIS crop beats both, and beats them on the block that had
	#     the strongest history to override.
	fresh = late_crop_estimate(BLOCKS, HISTORY, MODEL, seasons=CAL_SEASONS, harvests=HARVESTS,
							   price_per_kg=95.0, on_date=TODAY, counts={
								   "LA9": {"est_kg_per_tree": 28.4, "count_date": "2026-08-01"}})
	f_la9 = {r["block"]: r for r in fresh["rows"]}["LA9"]
	assert f_la9["evidence"] == "fruit count", f_la9
	assert f_la9["expected_kg"] == round(28.4 * CAL * 202, 0), f_la9
	assert "a count on this crop" in f_la9["basis"], f_la9

	# A count made in January is about fruit picked in May. It is not evidence for
	# August, and the block falls back to its own late crop rather than using it.
	stale_count = late_crop_estimate(BLOCKS, HISTORY, MODEL, seasons=CAL_SEASONS, harvests=HARVESTS,
									 on_date=TODAY, counts={"LA9": {"est_kg_per_tree": 28.4,
													 "count_date": "2026-01-15"}})
	s_la9 = {r["block"]: r for r in stale_count["rows"]}["LA9"]
	assert s_la9["evidence"] == "last late crop", s_la9
	assert s_la9["expected_kg"] == la9l["expected_kg"], s_la9

	assert late["evidence_split"] == {"last late crop": 2, "age curve": 1, "none": 3}, \
		late["evidence_split"]

	# An off year cuts it back: 2027 sits on the same half of the cycle as 2025, so
	# last season's late crop carries straight across with no lift at all.
	late27 = late_crop_estimate(BLOCKS, HISTORY, MODEL, seasons=CAL_SEASONS, harvests=HARVESTS,
								on_date="2027-08-05")
	assert {r["block"]: r for r in late27["rows"]}["LA9"]["expected_kg"] == 3030.0
	assert late27["total_kg"] < late["total_kg"], "an off year cannot match an on year"

	# 13. A delivered crop is history. It is never inside the forecast, and adding it
	#     to one is how an estate total counts the same fruit twice.
	#     With nothing recorded there is no delivered figure at all: none comes from code.
	delivered = delivered_this_season([], 2026)
	assert delivered["kg"] == 0.0 and delivered["recorded"] is False, delivered
	assert delivered["crop"] is None and "nothing delivered yet" in delivered["basis"], delivered
	# The season's harvest logs stand in where there is no yield history.
	logged = delivered_this_season([], 2026, [
		dict(harvest_date="2026-05-11", total_kg=1000.0, orchard_block="LA9"),
		dict(harvest_date="2026-06-20", total_kg=500.0, orchard_block="LB-BONDENI 2"),
		dict(harvest_date="2025-06-20", total_kg=9999.0, orchard_block="LA9")])
	assert logged["kg"] == 1500.0 and logged["blocks"] == 2 and logged["recorded"] is True, logged
	assert logged["harvest_from"] == "2026-05-11" and logged["harvest_to"] == "2026-06-20", logged
	# Put the delivered early crop into the history and the LATE forecast must not
	# move by a single kilogram — it is a different crop off the same trees.
	with_early = HISTORY + [dict(block_code="LA9", year=2026, season_part="Early",
								 kg_harvested=9000.0)]
	assert late_crop_estimate(BLOCKS, with_early, MODEL, seasons=CAL_SEASONS, harvests=HARVESTS,
							  on_date=TODAY)["total_kg"] == late["total_kg"]
	# ...and once the history is loaded per block the delivered figure comes from it.
	d2 = delivered_this_season(with_early, 2026)
	assert d2["kg"] == 9000.0 and d2["blocks"] == 1 and "yield history" in d2["basis"], d2
	assert d2["recorded"] is True
	assert delivered_this_season([], 2099)["kg"] == 0.0

	# 14. Dating a crop with no dry matter to date it by.
	#     The stale rule is NOT weakened: a February reading still yields no pick date.
	stale = dm_projection([
		dict(orchard_block="LA9", sample_date="2026-02-09", avg_dry_matter_pct=19.4),
		dict(orchard_block="LA9", sample_date="2026-03-09", avg_dry_matter_pct=21.8),
	], MODEL, on_date=TODAY)
	assert stale["LA9"]["stale"] is True and stale["LA9"]["weeks_to_minimum"] is None
	assert stale["LA9"]["ready_date"] is None

	windows = seasonal_windows(HISTORY, 2026, on_date=TODAY)
	assert set(windows) == {"LA9", "LB-BONDENI 2"}, windows
	# 1 Sept 2025 plus 52 weeks is 31 Aug 2026 — the same weekday, the same point in
	# the season. A calendar year would drift the weekday and start mid-week.
	assert windows["LA9"]["start"] == "2026-08-31", windows["LA9"]
	assert windows["LA9"]["end"] == "2026-09-12", windows["LA9"]
	assert windows["LA9"]["weeks"] == 2, windows["LA9"]
	assert windows["LA9"]["measured_on"] == "last season"
	assert "last season's window" in windows["LA9"]["basis"]
	assert "no dry matter yet" in windows["LA9"]["basis"]
	assert "delivery log" in windows["LA9"]["basis"], windows["LA9"]

	# With a stale reading and nothing else, the old behaviour was a blank calendar.
	# Now the window carries it — and the schedule still says it is not a measurement.
	blank = weekly_spread(late["rows"], stale, PICK_WEEKS, on_date=TODAY)
	assert blank["weeks"] == [] and blank["scheduled_kg"] == 0, blank

	sched = weekly_spread(late["rows"], stale, PICK_WEEKS, on_date=TODAY, windows=windows)
	assert sched["weeks"], "the seasonal fallback has to produce weeks"
	assert sched["weeks"][0] == "2026-08-31", sched["weeks"]
	assert sched["kg_by_basis"] == {"last season": lrows["LA9"]["expected_kg"]
									+ lrows["LB-BONDENI 2"]["expected_kg"]}, sched["kg_by_basis"]
	assert sched["blocks_by_basis"] == {"last season": 2}, sched["blocks_by_basis"]
	assert all(s["measured_on"] == "last season" for s in sched["scheduled"])
	assert all("no dry matter yet" in s["basis"] for s in sched["scheduled"])
	# LC-MIMA 1 has fruit forecast, no sample and no window: still unscheduled, still
	# named. A block nobody can date must not be quietly dropped into week one.
	assert {u["block"] for u in sched["unscheduled"]} == {"LC-MIMA 1"}, sched["unscheduled"]
	assert sched["unscheduled_kg"] == mima["expected_kg"]

	# A live reading outranks the window, and the schedule labels the two apart.
	mixed = weekly_spread(late["rows"], dm_projection([
		dict(orchard_block="LB-BONDENI 2", sample_date="2026-08-01",
			 avg_dry_matter_pct=23.3),
	], MODEL, on_date=TODAY), PICK_WEEKS, on_date=TODAY, windows=windows)
	by_block = {s["block"]: s for s in mixed["scheduled"]}
	assert by_block["LB-BONDENI 2"]["measured_on"] == "dry matter", by_block
	assert "dry matter 23.3%" in by_block["LB-BONDENI 2"]["basis"], by_block
	assert by_block["LA9"]["measured_on"] == "last season", by_block
	assert set(mixed["blocks_by_basis"]) == {"dry matter", "last season"}

	# 15. Reading the estate's dry matter summary, on a miniature of the real sheet.
	summary()

	# 16. The model is the records: change a setting and the output changes.
	model_follows_settings(est, late)

	print(f"test_avocado_yield: OK — curve {[round(r['kg_per_tree'], 1) for r in curve]}, "
		  f"grade 1 {g1:.1%}, estate {est['total_kg']:,.0f} kg from "
		  f"{est['bearing_trees']:,.0f} bearing trees "
		  f"({raw['total_kg']:,.0f} kg before calibration x{CAL}, drop {est['drop_pct']:.0f}%), "
		  f"{len(est['issues'])} data issues; late crop {late['total_kg']:,.0f} kg on "
		  f"{late['evidence_split']}, {len(sched['weeks'])} weeks scheduled off "
		  f"{sched['blocks_by_basis']}, {delivered['kg']:,.0f} kg already delivered and "
		  f"kept out of it")


def model_follows_settings(est, late):
	from upande_production.tests.avocado_model_fixture import HASS as HASS_ROWS, make_model

	rows = {r["block"]: r for r in est["rows"]}
	FUERTE = dict(HASS_ROWS, name="Fuerte", biennial_off_factor=None, on_years=None,
				  late_crop_share_pct=None, dry_matter_target_pct=21,
				  yield_by_age=[{"age_years": 0, "kg_per_plant": 0.0}, {"age_years": 2, "kg_per_plant": 50.0}])

	# Yield by age is the variety's: a block of another variety is sized on its own rows.
	two = make_model(varieties=[dict(HASS_ROWS), FUERTE])
	blocks = [dict(BLOCKS[0], name="F1", variety="Fuerte"), dict(BLOCKS[0], name="H1", variety="Hass"),
			  dict(BLOCKS[0], name="M1", variety="Fuerte, Hass")]
	got = {r["block"]: r for r in estimate(blocks, [], two, on_date=TODAY)["rows"]}
	assert got["F1"]["kg_per_tree"] == 50.0 and got["H1"]["kg_per_tree"] == 90.0, got
	assert got["M1"]["kg_per_tree"] == 50.0, "a mixed block takes the first variety listed that has a curve"
	# A variety with no biennial setting has no biennial effect, in an on or an off year.
	assert biennial_factor(2025, two["varieties"]["Fuerte"]) == 1.0
	assert is_on_year(2025, two["varieties"]["Fuerte"]) is None and is_on_year(2025, HASS) is False
	# An off factor without saying which years are on says nothing.
	assert make_model(varieties=[dict(HASS_ROWS, on_years=None)])["varieties"]["Hass"]["off_factor"] is None
	off = estimate(blocks, [], two, on_date="2027-08-05")["rows"]
	off = {r["block"]: r for r in off}
	assert off["F1"]["kg_per_tree"] == 50.0 and off["H1"]["kg_per_tree"] == round(90.0 * HASS["off_factor"], 1)
	# Another off factor moves the off-year figure.
	flat = make_model(varieties=[dict(HASS_ROWS, biennial_off_factor=0.8)])
	assert {r["block"]: r for r in estimate(blocks[1:2], [], flat, on_date="2027-08-05")["rows"]
			}["H1"]["kg_per_tree"] == 72.0
	# A variety with no curve is sized at zero and says why; it is also a data gap.
	nocurve = estimate([dict(BLOCKS[0], variety="Pinkerton")], [], two, on_date=TODAY)["rows"][0]
	assert nocurve["expected_kg"] == 0 and "no yield curve" in nocurve["basis"], nocurve
	assert any(i["issue"] == "no yield curve" for i in data_quality([dict(BLOCKS[0], variety="Pinkerton")], two))

	# The tree threshold is the crop's: a small harvest overrides the typed figure once allowed to.
	small = [dict(harvest_date="2025-09-20", orchard_block="LA9", total_kg=20200.0, trees_harvested=202)]
	assert yield_curve(small, BLOCKS, MODEL)["Hass"][6]["basis"] == "estate history"
	eager = make_model({"min_trees_to_override_curve": 100})
	band = yield_curve(small, BLOCKS, eager)["Hass"][6]
	assert band["basis"] == "harvested" and abs(band["kg_per_tree"] - 100.0) < 0.01, band

	# The late crop's share: the season named Late wins, then the variety's own figure; neither, no sizing.
	nocount = [dict(BLOCKS[2], name="LC", variety="Hass")]
	def late_of(variety_rows):
		m = make_model(varieties=variety_rows)
		return late_crop_estimate(nocount, [], m, on_date=TODAY)["rows"][0]
	by_fallback = late_of([dict(HASS_ROWS)])
	assert by_fallback["expected_kg"] == round(12.0 * 0.846 * 240, 0), by_fallback
	named = late_of([dict(HASS_ROWS, flowering_seasons=[
		{"season_name": "Early", "crop_share_pct": 60}, {"season_name": "Late crop", "crop_share_pct": 40}])])
	assert named["expected_kg"] == round(12.0 * 0.40 * 240, 0), named
	unset = late_of([dict(HASS_ROWS, late_crop_share_pct=None)])
	assert unset["expected_kg"] == 0 and "late-crop share" in unset["basis"], unset

	# Dry matter: gain, stale weeks and the export minimum are the crop's / the variety's.
	one = [dict(orchard_block="LA9", sample_date="2026-07-22", avg_dry_matter_pct=22.6)]
	base = dm_projection(one, MODEL, on_date=TODAY)["LA9"]
	assert base["weeks_to_minimum"] == 2.0 and base["minimum_pct"] == 24.0, base   # 1.4 at 0.7 a week
	quick = dm_projection(one, make_model({"dm_gain_per_week": 1.4}), on_date=TODAY)["LA9"]
	assert quick["weeks_to_minimum"] == 1.0, quick
	short_memory = dm_projection(one, make_model({"stale_sample_weeks": 1}), on_date=TODAY)["LA9"]
	assert short_memory["stale"] is True and short_memory["weeks_to_minimum"] is None, short_memory
	lower = dm_projection(one, MODEL, on_date=TODAY, minimums={"LA9": 22.0})["LA9"]
	assert lower["ready"] is True and lower["minimum_pct"] == 22.0, lower
	assert two["varieties"]["Fuerte"]["dm_min"] == 21 and two["varieties"]["Hass"]["dm_min"] == 24
	# A late-crop count is only evidence while it is younger than the stale weeks.
	counts = {"LA9": {"est_kg_per_tree": 28.4, "count_date": "2026-07-22"}}
	assert late_crop_estimate(BLOCKS, HISTORY, MODEL, harvests=HARVESTS, on_date=TODAY, counts=counts
							  )["rows"][0]["evidence"] in ("fruit count", "last late crop")
	fast_stale = make_model({"stale_sample_weeks": 1})
	assert {r["block"]: r for r in late_crop_estimate(
		BLOCKS, HISTORY, fast_stale, harvests=HARVESTS, on_date=TODAY, counts=counts)["rows"]
		}["LA9"]["evidence"] == "last late crop"

	# The picking weeks are the crop's.
	assert weekly_spread(est["rows"], {}, 3, on_date=TODAY, windows={
		"LA9": {"start": "2026-08-10", "weeks": 3, "basis": "w"}})["pick_weeks"] == 3

	# 17. Calibration comes from records: estimates vs deliveries, seasons that have both.
	hist = [dict(block_code="A", year=2026, season_part="Early", kg_harvested=78400.0),
			dict(block_code="B", year=2026, season_part="Early", kg_harvested=59300.0),
			dict(block_code="B", year=2025, season_part="Year", kg_harvested=1000.0),
			dict(block_code="C", year=2026, season_part="Early", kg_harvested=500.0)]
	fc = [dict(orchard_block="A", season=2026, crop="Early", expected_kg=70000.0),
		  dict(orchard_block="B", season=2026, crop="Early", expected_kg=64000.0),
		  # estimated, not picked yet: fruit on the trees is not a miss
		  dict(orchard_block="D", season=2026, crop="Early", expected_kg=50000.0),
		  # a whole-season figure for the current season is not scored against half a season
		  dict(orchard_block="A", season=2026, crop="Whole Season", expected_kg=150000.0),
		  # a late estimate with no late delivery is not a season either
		  dict(orchard_block="A", season=2026, crop="Late", expected_kg=79000.0)]
	seasons = calibration_seasons(hist, fc, [], 2026)
	assert len(seasons) == 1, seasons
	assert seasons[0]["estimated_kg"] == 134000.0 and seasons[0]["actual_kg"] == 137700.0, seasons
	assert seasons[0]["blocks_estimated"] == 3 and seasons[0]["blocks_harvested"] == 3, seasons
	assert season_calibration(seasons)["factor"] == round(137700 / 134000, 3)
	# A closed season with only a budget is scored by the budget against the year's deliveries.
	budgeted = calibration_seasons(hist, [], [dict(season=2025, crop="Whole Season", budget_kg=800.0),
											  dict(season=2026, crop="Whole Season", budget_kg=9e6)], 2026)
	assert [(r["season"], r["estimated_kg"], r["actual_kg"]) for r in budgeted] == [(2025, 800.0, 1000.0)], budgeted
	# Nothing recorded, nothing to correct: the factor is exactly 1.
	assert calibration_seasons([], [], [], 2026) == []
	assert season_calibration(calibration_seasons([], fc, [], 2026))["factor"] == 1.0


def _write_summary(folder):
	"""A miniature of the estate's dry matter summary, with every trap the real one has.

	One planting section, the 1.00 placeholder the sheet parks in unsampled weeks, the
	Min/Max reference lines that draw the export band, the SECOND set of week columns
	that mirror the moisture as dry matter, and the "Average All Lokitela" block at the
	foot which is the mean of the sections above it.
	"""
	import openpyxl
	from upande_production.avocado_yield.import_history import SUMMARY, SUMMARY_SHEET

	wb = openpyxl.Workbook()
	ws = wb.active
	ws.title = SUMMARY_SHEET
	weeks = ["Wk.7", "Wk.8", "Wk.31", "Wk.32", "Wk.33"]
	for row in [
		["LOKITELA AVOCADO MATURITY TESTING."],
		[None] * 3 + ["Moiture %"] + [None] * 4 + ["Dry Matter %"],
		["Wk. no'", "Fruit Mass", None] + weeks + weeks,
		# The section heading carries the planting year, and the reference lines sit
		# on it and on the row below — neither is a reading.
		["23Ha  - 2018", None, "Min"] + [0.76] * 5 + [0.24] * 5,
		[None, None, "Max"] + [0.66] * 5 + [0.34] * 5,
		#                       wk7    8     31     32    33 | the same cells mirrored
		[14, 275, 317, 0.81, 1, 0.756, 0.766, 1, 0.19, 0, 0.244, 0.234, 0],
		[20, 196, 216, 1, 1, 1, 0.74, 1, 0, 0, 0, 0.26, 0],
		[None] * 3,
		# Everything below here is the mean of the sections above it.
		["Average All Lokitela "],
		[14, 275, 317, 0.81, 1, 0.756, 0.766, 1, 0.19, 0, 0.244, 0.234, 0],
	]:
		ws.append(row)
	path = os.path.join(folder, SUMMARY)
	wb.save(path)
	return path


def summary():
	"""The dry matter summary parse, and the pick dates it does or does not produce."""
	from upande_production.avocado_yield.import_history import (
		MAX_MOISTURE, MIN_MOISTURE, _plausible_moisture, read_summary_maturity,
	)

	with tempfile.TemporaryDirectory() as folder:
		_write_summary(folder)
		refused = []
		rows = read_summary_maturity(folder, refused=refused)

	# Four readings and no more. Row 14 gave three, row 20 gave one.
	assert len(rows) == 4, rows
	assert all(r["planting_area"] == "23 Ha" for r in rows), rows
	assert all(r["planting_year"] == 2018 for r in rows), rows
	got = {(r["week_number"], r["fruit_count_size"]): r["moisture_pct"] for r in rows}
	assert got == {(7, 14): 0.81, (31, 14): 0.756, (32, 14): 0.766, (32, 20): 0.74}, got
	assert rows[0]["fruit_min_g"] == 275 and rows[0]["fruit_max_g"] == 317

	# The mirror. The same weeks appear twice across the header — moisture on the
	# left, its own dry-matter complement on the right — and reading past the repeat
	# would double every planting on the estate, half of it inverted.
	assert len(got) == len(rows), "a week was read twice"
	assert all(MIN_MOISTURE <= m <= MAX_MOISTURE for m in got.values()), got
	assert 0.19 not in got.values() and 0.234 not in got.values(), "the mirror got in"
	# Ten week columns, only five of them moisture. Scanning all ten is the regression
	# to watch for, and it shows up here long before it shows up in a pick date.
	assert len(refused) == 6, (f"{len(refused)} cells scanned where 6 were offered — "
							   f"the dry-matter mirror is being read as moisture")

	# The 1.00 placeholder. An avocado that was all water would be juice, and the
	# sheet writes one into every week nobody has sampled yet.
	assert refused, "nothing was refused — the placeholder filter is not running"
	assert {v for _a, _w, _c, v in refused} == {1}, refused
	assert all(r["moisture_pct"] != 1 for r in rows)

	# ...and the average section at the foot, which is the other four sections added
	# up. Import it and every planting is counted twice over.
	assert sum(1 for r in rows if r["week_number"] == 7) == 1, "Average All Lokitela got in"

	# What is and is not a moisture reading, one cell at a time.
	assert _plausible_moisture(0.77) == 0.77
	assert _plausible_moisture(77) == 0.77          # typed as a percentage
	assert _plausible_moisture(1) is None           # the formula artifact
	assert _plausible_moisture(1.0) is None
	assert _plausible_moisture(0.23) is None        # dry matter, off the mirror
	assert _plausible_moisture(0.5) is None
	assert _plausible_moisture(None) is None
	assert _plausible_moisture(True) is None        # a tick box, not a test

	# Week to date: the sheet records a week and never a day, so a test is dated to
	# the Monday of its ISO week. Week 33 of 2026 is the week of 10 August, and week
	# 7 is 9 February — which is the date on every reading that went stale.
	assert date.fromisocalendar(2026, 33, 1).isoformat() == "2026-08-10"
	assert date.fromisocalendar(2026, 32, 1).isoformat() == "2026-08-03"
	assert date.fromisocalendar(2026, 7, 1).isoformat() == "2026-02-09"

	# And the point of the whole import: a fresh reading dates a pick, a stale one
	# refuses to. Same block, same dry matter, 25 weeks apart.
	blk = [dict(name="LK01", farm="Lokitela", status="Active", area_ha=2.0, live_trees=500,
				bearing_trees=400.0, planting_year=2018, trees_per_ha=250, variety="Hass")]
	rows_kg = estimate(blk, [], MODEL, on_date="2026-08-10")["rows"]

	def pick(week, dm=23.4):
		p = dm_projection([dict(orchard_block="LK01", avg_dry_matter_pct=dm,
								sample_date=date.fromisocalendar(2026, week, 1).isoformat())],
						  MODEL, on_date="2026-08-10")
		return p["LK01"], weekly_spread(rows_kg, p, PICK_WEEKS, on_date="2026-08-10")

	fresh, fresh_sched = pick(32)
	assert fresh["stale"] is False, fresh
	assert fresh["weeks_to_minimum"] is not None and fresh["ready_date"], fresh
	assert fresh_sched["weeks"], "a week-old reading has to produce a pick date"
	assert fresh_sched["unscheduled"] == [], fresh_sched

	stale, stale_sched = pick(7)
	assert stale["stale"] is True, stale
	assert stale["weeks_to_minimum"] is None and stale["ready_date"] is None, stale
	assert stale["sample_age_weeks"] > STALE_SAMPLE_WEEKS
	assert "fresh sample" in stale["needs"]
	assert stale_sched["weeks"] == [], "a February reading must not date an August pick"
	assert {u["block"] for u in stale_sched["unscheduled"]} == {"LK01"}

	# A slope is only a slope within one crop. February's fruit was picked in May and
	# what is hanging now set after it; a line drawn between them is arithmetic across
	# two crops, and it flattens the rate to a fifth of what this crop is doing.
	mixed = dm_projection([
		dict(orchard_block="LK01", sample_date="2026-02-09", avg_dry_matter_pct=18.0),
		dict(orchard_block="LK01", sample_date="2026-07-27", avg_dry_matter_pct=23.3),
		dict(orchard_block="LK01", sample_date="2026-08-03", avg_dry_matter_pct=23.5),
	], MODEL, on_date="2026-08-10")["LK01"]
	assert mixed["samples"] == 3, mixed
	assert abs(mixed["gain_per_week"] - 0.2) < 0.01, mixed   # 23.5 - 23.3 over one week
	assert mixed["gain_basis"] == "measured over 1 weeks", mixed

	# 16. Days to ripen, the second opinion. It corroborates and it decides nothing:
	#     one shelf of fruit cannot say what a normal ripening time is on this estate,
	#     and no threshold is invented to make it look like it can.
	trials = [
		dict(size_class="Big Size", harvest_date="2026-07-20", fruit_harvested=4,
			 fruit_ripe=2, avg_days_to_ripen=16.0),
		# Still on the shelf: no average yet, and a 0 in that cell is not one.
		dict(size_class="Big Size", harvest_date="2026-08-05", fruit_harvested=2,
			 fruit_ripe=2, avg_days_to_ripen=0),
	]
	tests = [
		dict(planting_area="23 Ha", planting_year=2018, week_number=32,
			 test_date="2026-08-03", dry_matter_pct=24.4),
		dict(planting_area="23 Ha", planting_year=2018, week_number=7,
			 test_date="2026-02-09", dry_matter_pct=18.5),
	]
	rip = ripening_agreement(trials, tests, MODEL["dm_min"])
	assert rip["completed"] == 1, rip
	assert rip["avg_days_to_ripen"] == 16.0, rip
	assert rip["threshold_days"] is None, "a ripeness threshold was invented"
	assert rip["verdict"] is None, rip
	assert rip["min_trials_for_a_verdict"] == MIN_RIPENING_TRIALS
	assert "nothing" in rip["gates"], rip["gates"]
	assert "assumed" in rip["basis"], rip["basis"]
	# The trial from 20 July is paired with the dry matter nearest that week, not the
	# newest reading on file: the fruit on the shelf came off the tree that day.
	july = next(t for t in rip["trials"] if t["harvest_date"] == "2026-07-20")
	assert july["complete"] is True
	assert july["dry_matter_that_week"][0]["sample_date"] == "2026-02-09", july
	assert july["dry_matter_that_week"][0]["ready"] is False, july
	aug = next(t for t in rip["trials"] if t["harvest_date"] == "2026-08-05")
	assert aug["complete"] is False and aug["avg_days_to_ripen"] is None, aug
	assert aug["dry_matter_that_week"][0]["sample_date"] == "2026-08-03", aug
	# Enough trials and it will say so — but it still returns no threshold.
	many = ripening_agreement(trials + [dict(t, harvest_date="2026-07-27") for t in trials
										for _ in range(1)], tests, MODEL["dm_min"])
	assert many["completed"] == 2 and many["verdict"] is None, many
	loaded = ripening_agreement(
		[dict(trials[0], harvest_date=f"2026-07-0{i}") for i in range(1, 5)], tests, MODEL["dm_min"])
	assert loaded["completed"] == 4 and loaded["verdict"], loaded
	assert loaded["threshold_days"] is None, "still no threshold, however many trials"


if __name__ == "__main__":
	main()
