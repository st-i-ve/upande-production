# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

# Turning a forecast into a labour plan.
#
# A tonnage forecast on its own changes nobody's Monday. What a farm manager
# actually decides is how many pickers go to which block in which week, and
# whether the crew on the books can take the crop off in time. That is this
# module: kilograms per week become picker-days, picker-days become a headcount
# against the crew that exists, and the weeks where those two disagree are the
# only weeks worth a meeting.
#
# The picking RATE is measured, never assumed. A harvest log records the kilograms
# and the number of pickers who took them off, so kg per picker-day is a fact
# about that block. It is a property of the BLOCK, not the person: a heavy block
# with big fruit fills a bin quickly and a thin, tall, gappy block does not, and
# ranking people on it just ranks the blocks they were sent to.
#
# The arithmetic is pure functions over plain rows so it can be tested without a
# site — see tests/test_avocado_labour.py.

import frappe
from frappe.utils import cint, flt

HARVEST_DOCTYPE = "Avocado Harvest Log"

# Kilograms in a picking crate, the unit the estate counts in.
KG_PER_CRATE = 18.0

# What one picker takes off in a day when we have never measured this block.
# Deliberately conservative: over-estimating the rate under-books the crew, and a
# block that ripens past its window loses fruit on the ground.
DEFAULT_KG_PER_PICKER_DAY = 450.0

# A harvest log is one dated event, so kilograms divided by pickers is one
# picker-day. Outside this range the record is not a day's picking — a mis-keyed
# picker count, or several days rolled into one row — and it must not quietly set
# the plan for a whole season.
PLAUSIBLE_RATE = (150.0, 1200.0)

DEFAULT_PICKING_DAYS_PER_WEEK = 5


def picker_rates(harvests):
	"""{block: {kg_per_picker_day, basis, events}} plus an "" estate fallback.

	Rows whose implied rate is not physically a day's work are excluded and
	counted, so a bad record shows up as a data problem instead of silently
	halving next season's crew.
	"""
	per_block, rejected = {}, []
	for h in harvests:
		kg = flt(h.get("total_kg"))
		pickers = flt(h.get("pickers_count"))
		block = h.get("orchard_block")
		if not (kg and pickers and block):
			continue
		rate = kg / pickers
		if not (PLAUSIBLE_RATE[0] <= rate <= PLAUSIBLE_RATE[1]):
			rejected.append({"block": block, "date": str(h.get("harvest_date") or ""),
							 "implied_rate": round(rate, 1),
							 "why": "not one day's picking for one picker"})
			continue
		agg = per_block.setdefault(block, {"kg": 0.0, "picker_days": 0.0, "events": 0})
		agg["kg"] += kg
		agg["picker_days"] += pickers
		agg["events"] += 1

	rates = {}
	for block, agg in per_block.items():
		rates[block] = {
			"kg_per_picker_day": agg["kg"] / agg["picker_days"],
			"basis": f"measured over {agg['events']} pick{'' if agg['events'] == 1 else 's'}",
			"events": agg["events"],
		}

	# Estate rate for blocks nobody has picked yet: every measured kilogram over
	# every measured picker-day, which is the estate's own average and not a guess.
	total_kg = sum(a["kg"] for a in per_block.values())
	total_days = sum(a["picker_days"] for a in per_block.values())
	rates[""] = (
		{"kg_per_picker_day": total_kg / total_days,
		 "basis": f"estate average over {len(per_block)} block(s)",
		 "events": sum(a["events"] for a in per_block.values())}
		if total_days else
		{"kg_per_picker_day": DEFAULT_KG_PER_PICKER_DAY,
		 "basis": "estate default, nothing measured yet", "events": 0}
	)
	rates["_rejected"] = rejected
	return rates


def rate_for(rates, block):
	"""The block's own measured rate, else the estate's."""
	row = rates.get(block) or rates.get("", {})
	return flt(row.get("kg_per_picker_day")) or DEFAULT_KG_PER_PICKER_DAY, row.get("basis", "")


def labour_plan(weeks, block_kg, rates, crew_available=0,
				days_per_week=DEFAULT_PICKING_DAYS_PER_WEEK, pay_per_day=0.0):
	"""Per week: kilograms, crates, picker-days, headcount, and the gap.

	`block_kg` is {week: {block: kg}} — kept per block because the rate differs by
	block, so a week's headcount is the sum of each block's own requirement rather
	than the total kilograms over an estate-wide average.
	"""
	days = max(cint(days_per_week) or DEFAULT_PICKING_DAYS_PER_WEEK, 1)
	rows = []
	for week in weeks:
		by_block = block_kg.get(week, {})
		kg = sum(flt(v) for v in by_block.values())
		picker_days = 0.0
		measured_kg, unmeasured_kg = 0.0, 0.0
		for block, block_total in by_block.items():
			rate, basis = rate_for(rates, block)
			picker_days += flt(block_total) / rate
			if rates.get(block):
				measured_kg += flt(block_total)
			else:
				unmeasured_kg += flt(block_total)

		needed = picker_days / days
		crew = flt(crew_available)
		rows.append({
			"week": week,
			"kg": round(kg, 0),
			"crates": round(kg / KG_PER_CRATE, 0),
			"picker_days": round(picker_days, 1),
			"pickers_needed": round(needed, 1),
			"crew_available": crew,
			# Positive means people to find, negative means people standing idle.
			# Both cost money, and the manager needs to see which it is at a glance.
			"shortfall": round(needed - crew, 1) if crew else None,
			"pct_of_crew": round(needed / crew * 100, 0) if crew else None,
			"wage_cost": round(picker_days * flt(pay_per_day), 0) if pay_per_day else None,
			"cost_per_kg": round(picker_days * flt(pay_per_day) / kg, 2)
						   if pay_per_day and kg else None,
			"blocks": sorted(by_block, key=lambda b: -flt(by_block[b])),
			"pct_kg_measured": round(measured_kg / kg * 100, 0) if kg else None,
		})
	return rows


def summarise(rows):
	"""The three things a manager wants off this page without reading the table."""
	if not rows:
		return {"weeks": 0}
	peak = max(rows, key=lambda r: r["pickers_needed"])
	short = [r for r in rows if r.get("shortfall") and r["shortfall"] > 0]
	idle = [r for r in rows if r.get("shortfall") is not None and r["shortfall"] < 0]
	return {
		"weeks": len(rows),
		"total_kg": round(sum(r["kg"] for r in rows), 0),
		"total_crates": round(sum(r["crates"] for r in rows), 0),
		"total_picker_days": round(sum(r["picker_days"] for r in rows), 1),
		"peak_week": peak["week"],
		"peak_pickers": peak["pickers_needed"],
		"short_weeks": len(short),
		"worst_shortfall": max((r["shortfall"] for r in short), default=0),
		"first_short_week": short[0]["week"] if short else None,
		"idle_weeks": len(idle),
		"wage_cost": round(sum(r["wage_cost"] or 0 for r in rows), 0)
					 if any(r["wage_cost"] for r in rows) else None,
	}


# ── Site-facing ──────────────────────────────────────────────────────────────


@frappe.whitelist()
def get_labour_plan(crew_available=0, days_per_week=DEFAULT_PICKING_DAYS_PER_WEEK,
					pay_per_day=0, price_per_kg=0):
	"""The picking plan, built on the forecast the outlook page already shows."""
	from upande_production.api import avocadoapi

	forecast = avocadoapi.get_forecast(price_per_kg=price_per_kg)
	projection = avocadoapi.dm_projection(avocadoapi._samples())
	# Where dry matter is too old to date a pick, the forecast falls back to the
	# window that crop was actually picked in last season. The plan has to use the
	# same windows or a crew gets booked for weeks the calendar does not have.
	windows = avocadoapi.seasonal_windows(avocadoapi._history(), forecast.get("season"))
	schedule = avocadoapi.weekly_spread(forecast["rows"], projection, windows=windows)

	# weekly_spread totals the estate per week; the plan needs it per block, so the
	# same spread is rebuilt one block at a time. Same function, so the two pages
	# can never disagree about which week a block lands in.
	block_kg = {}
	for row in forecast["rows"]:
		one = avocadoapi.weekly_spread([row], projection, windows=windows)
		for week, kg in zip(one["weeks"], one["kg"]):
			block_kg.setdefault(week, {})[row["block"]] = kg

	harvests = (frappe.get_all(HARVEST_DOCTYPE,
							   fields=["orchard_block", "harvest_date", "total_kg",
									   "pickers_count", "bins_harvested"],
							   limit_page_length=0)
				if frappe.db.exists("DocType", HARVEST_DOCTYPE) else [])
	rates = picker_rates(harvests)

	rows = labour_plan(schedule["weeks"], block_kg, rates,
					   crew_available=flt(crew_available), days_per_week=days_per_week,
					   pay_per_day=flt(pay_per_day))
	return {
		"rows": rows,
		"summary": summarise(rows),
		"rates": {k: v for k, v in rates.items() if k != "_rejected"},
		"rejected_records": rates.get("_rejected", []),
		"kg_per_crate": KG_PER_CRATE,
		"days_per_week": cint(days_per_week) or DEFAULT_PICKING_DAYS_PER_WEEK,
		# Fruit with no pick date cannot be staffed. Named, not hidden, because it
		# is the manager's cue to go and sample those blocks.
		"unscheduled": schedule.get("unscheduled", []),
		"unscheduled_kg": schedule.get("unscheduled_kg", 0),
	}
