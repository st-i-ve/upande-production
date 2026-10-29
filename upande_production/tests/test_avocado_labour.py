# Self-check for the picking labour plan.
#
# Uses the estate's own recorded picks: 7,320 kg off 488 trees with 10 pickers,
# and 3,030 kg with 8 pickers. Those give a measured rate per block, which is the
# whole point — booking a crew on an assumed rate is how a block ripens past its
# window with nobody in it.
#
# Run: env/bin/python -m upande_production.tests.test_avocado_labour   (no site needed)

from upande_production.api.avocadolabour import (
	is_plausible, labour_plan, picker_rates, rate_for, summarise,
)
from upande_production.tests.avocado_model_fixture import MODEL, make_model

DEFAULT_KG_PER_PICKER_DAY = MODEL["default_kg_per_picker_day"]
KG_PER_CRATE = MODEL["avg_kg_per_crate"]

HARVESTS = [
	# 7,320 / 10 pickers = 732 kg a picker-day.
	dict(orchard_block="LB-BONDENI 2", harvest_date="2025-09-10", total_kg=7320.0,
		 pickers_count=10, bins_harvested=30),
	# 3,030 / 8 = 378.75.
	dict(orchard_block="LA9", harvest_date="2025-09-05", total_kg=3030.0,
		 pickers_count=8, bins_harvested=13),
	# Nonsense: one picker cannot take off 9 tonnes in a day. Must be excluded.
	dict(orchard_block="LA3", harvest_date="2025-09-06", total_kg=9000.0, pickers_count=1),
	# Missing picker count — nothing to learn, dropped quietly.
	dict(orchard_block="LA5", harvest_date="2025-09-07", total_kg=4000.0, pickers_count=0),
]


def main():
	rates = picker_rates(HARVESTS, MODEL)

	# 1. Measured per block, and the estate average for blocks never picked.
	assert abs(rates["LB-BONDENI 2"]["kg_per_picker_day"] - 732.0) < 0.01, rates["LB-BONDENI 2"]
	assert abs(rates["LA9"]["kg_per_picker_day"] - 378.75) < 0.01, rates["LA9"]
	assert rates["LB-BONDENI 2"]["basis"].startswith("measured over 1 pick")
	estate = (7320 + 3030) / 18
	assert abs(rates[""]["kg_per_picker_day"] - estate) < 0.01, rates[""]

	# 2. The impossible record is refused and reported, not averaged in.
	assert "LA3" not in rates, "a 9,000 kg picker-day must not set a rate"
	assert len(rates["_rejected"]) == 1
	assert rates["_rejected"][0]["block"] == "LA3"

	# 3. An unmeasured block falls back to the estate rate, then to the default.
	assert abs(rate_for(rates, "WESA 6", MODEL)[0] - estate) < 0.01
	assert abs(rate_for(picker_rates([], MODEL), "WESA 6", MODEL)[0] - DEFAULT_KG_PER_PICKER_DAY) < 0.01
	assert "nothing measured yet" in picker_rates([], MODEL)[""]["basis"]

	# 4. A week's headcount uses each block's OWN rate, not the estate average over
	#    the week's total — the difference is what gets a crew wrongly booked.
	weeks = ["2026-08-03", "2026-08-10"]
	block_kg = {
		"2026-08-03": {"LB-BONDENI 2": 7320.0, "LA9": 3787.5},
		"2026-08-10": {"LA9": 1893.75},
	}
	rows = labour_plan(weeks, block_kg, rates, MODEL, crew_available=6, days_per_week=5,
					   pay_per_day=500.0)
	w1, w2 = rows

	# 7,320 / 732 = 10 picker-days, 3,787.5 / 378.75 = 10 → 20 over 5 days = 4 pickers.
	assert abs(w1["picker_days"] - 20.0) < 0.01, w1
	assert abs(w1["pickers_needed"] - 4.0) < 0.01, w1
	assert w1["kg"] == 11108.0 and w1["crates"] == round(11108 / KG_PER_CRATE, 0)
	# Crew of 6 against 4 needed: two idle, shown as a negative shortfall.
	assert w1["shortfall"] == -2.0, w1
	assert w1["wage_cost"] == 10000.0 and w1["cost_per_kg"] == 0.9, w1
	assert w1["pct_kg_measured"] == 100.0
	assert w1["blocks"][0] == "LB-BONDENI 2", "heaviest block first"

	# Week two is 5 picker-days = 1 picker: the crop tails off and so does the crew.
	assert abs(w2["pickers_needed"] - 1.0) < 0.01, w2
	assert w2["shortfall"] == -5.0

	# 5. A short week must be flagged, because that is the only number that changes
	#    what a manager does on Monday.
	tight = labour_plan(weeks, block_kg, rates, MODEL, crew_available=3, days_per_week=5)
	assert tight[0]["shortfall"] == 1.0, tight[0]
	assert tight[0]["pct_of_crew"] == 133.0, tight[0]

	s = summarise(tight)
	assert s["peak_week"] == "2026-08-03" and s["peak_pickers"] == 4.0
	assert s["short_weeks"] == 1 and s["first_short_week"] == "2026-08-03"
	assert s["worst_shortfall"] == 1.0
	assert s["total_picker_days"] == 25.0

	# 6. Fewer picking days a week means more pickers for the same crop.
	three_day = labour_plan(weeks, block_kg, rates, MODEL, crew_available=3, days_per_week=3)
	assert three_day[0]["pickers_needed"] > tight[0]["pickers_needed"]

	# 7. A block with no measured rate is counted, and the week says how much of its
	#    kilograms rest on the estate average rather than on that block.
	mixed = labour_plan(["2026-08-03"], {"2026-08-03": {"LA9": 1000.0, "WESA 6": 1000.0}},
						rates, MODEL, crew_available=4)
	assert mixed[0]["pct_kg_measured"] == 50.0, mixed[0]

	assert summarise([])["weeks"] == 0

	# 8. Every constant is the crop's setting: change it and the plan changes.
	faster = make_model({"default_kg_per_picker_day": 900})
	assert rate_for(picker_rates([], faster), "WESA 6", faster)[0] == 900.0
	heavy = make_model({"avg_kg_per_crate": 36})
	assert labour_plan(weeks, block_kg, rates, heavy, crew_available=6)[0]["crates"] == round(11108 / 36, 0)
	# The days per week default is the crop's; an explicit figure still wins.
	assert labour_plan(weeks, block_kg, rates, MODEL, crew_available=3)[0]["pickers_needed"] == 4.0
	assert labour_plan(weeks, block_kg, rates, make_model({"harvest_days_per_week": 4}),
					   crew_available=3)[0]["pickers_needed"] == 5.0
	# The plausible-rate range is the crop's too: a tighter ceiling refuses the 732 kg record.
	tight_rate = make_model({"plausible_kg_per_picker_day_max": 700})
	assert "LB-BONDENI 2" not in picker_rates(HARVESTS, tight_rate)
	assert is_plausible(HARVESTS[0], MODEL) and not is_plausible(HARVESTS[0], tight_rate)

	print(f"test_avocado_labour: OK — estate rate {estate:.0f} kg/picker-day, "
		  f"peak {s['peak_pickers']:.0f} pickers in {s['peak_week']}, "
		  f"{len(rates['_rejected'])} record(s) refused")


if __name__ == "__main__":
	main()
