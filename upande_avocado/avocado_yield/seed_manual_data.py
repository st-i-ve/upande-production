# Demo seed data for the manual side of Avocado Production: a typed forecast per
# bearing block, and one month-by-month budget, both for the crop that is actually
# live right now — the late crop, still on the trees (see api/avocadoapi.py).
#
# The point of this data is to make the Automatic/Manual toggle on
# /avocado-production mean something in a demo: each block's manual figure is the
# calculated one nudged by a plausible field-judgement margin, not a random or
# unrelated number, so switching the toggle shows two real, comparable views
# rather than one sensible chart and one nonsense one.
#
# Idempotent: re-running updates the same rows (matched on the doctypes' own
# block+season+crop / season+crop uniqueness) instead of raising a duplicate error
# or piling up copies.
#
# Run:  bench --site <site> execute upande_avocado.avocado_yield.seed_manual_data.run

import random

import frappe
from frappe.utils import add_days, flt, nowdate

from upande_avocado.api.avocadoapi import get_late_forecast

FORECAST_DOCTYPE = "Avocado Production Forecast"
BUDGET_DOCTYPE = "Avocado Production Budget"

# Rough shape a late crop actually lands in: slow start, peak mid-crop, tailing off.
# Four months because that is what the estate's own late-crop windows run
# (see SEASON_CALIBRATION / the Sept 2025 harvest sheet in avocadoapi.py).
MONTH_SHARE = [("August", 0.12), ("September", 0.38), ("October", 0.34), ("November", 0.16)]


def _employees(n):
	rows = frappe.get_all("Employee", fields=["name"], limit_page_length=n, order_by="name asc")
	return [r.name for r in rows] or [None]


def run(season=2026, crop="Late", price_per_kg=95, seed=20260917):
	rnd = random.Random(seed)  # fixed seed: reruns land on the same numbers
	staff = _employees(5)

	forecast = get_late_forecast(price_per_kg=price_per_kg)
	rows = [r for r in forecast["rows"] if flt(r["expected_kg"]) > 0]
	if not rows:
		frappe.throw("No block has a calculated late-crop forecast to seed a manual one from yet.")

	made, updated = 0, 0
	for r in rows:
		# A field estimate a person actually made: the calculated figure, nudged
		# ±12% either way, rounded the way someone jotting it on a phone would.
		kg = round(flt(r["expected_kg"]) * rnd.uniform(0.88, 1.12) / 10) * 10
		who = rnd.choice(staff)
		entry_date = add_days(nowdate(), -rnd.randint(1, 12))
		note = rnd.choice([
			"walked the block, fruit sizing looks on track",
			"counted a sample row, slightly heavier than expected",
			"some drop near the fence line, adjusted down a touch",
			"consistent with last month's walk-through",
			"",
		])

		existing = frappe.db.exists(FORECAST_DOCTYPE, {
			"orchard_block": r["block"], "season": season, "crop": crop,
		})
		doc = frappe.get_doc(FORECAST_DOCTYPE, existing) if existing else frappe.new_doc(FORECAST_DOCTYPE)
		doc.update({
			"orchard_block": r["block"], "season": season, "crop": crop,
			"expected_kg": kg, "price_per_kg": price_per_kg,
			"entered_by": who, "entry_date": entry_date, "notes": note,
			"client_ref": doc.client_ref or f"seed-forecast-{season}-{crop}-{r['block']}".lower().replace(" ", "-"),
		})
		doc.save(ignore_permissions=True)
		made += 0 if existing else 1
		updated += 1 if existing else 0

	# One month-by-month budget for the season/crop: a round target a touch above
	# the calculated total, the way a board sets a season target — not the exact
	# calculated figure, which would make "budget vs forecast" meaningless to show.
	total = round(flt(forecast["total_kg"]) * 1.08, -3) or 500000
	existing_budget = frappe.db.exists(BUDGET_DOCTYPE, {"season": season, "crop": crop})
	budget = (frappe.get_doc(BUDGET_DOCTYPE, existing_budget) if existing_budget
			  else frappe.new_doc(BUDGET_DOCTYPE))
	budget.season = season
	budget.crop = crop
	budget.budget_price_per_kg = price_per_kg
	budget.set_by = staff[0]
	budget.entry_date = add_days(nowdate(), -20)
	budget.notes = f"Season target for the {crop.lower()} crop, agreed ahead of picking."
	budget.client_ref = budget.client_ref or f"seed-budget-{season}-{crop}".lower().replace(" ", "-")
	budget.set("months", [])
	for month, share in MONTH_SHARE:
		budget.append("months", {"month": month, "budget_kg": round(total * share, -2)})
	budget.save(ignore_permissions=True)

	frappe.db.commit()
	print(f"Forecast: {made} created, {updated} updated across {len(rows)} blocks "
		  f"({season} {crop}).")
	print(f"Budget: {'updated' if existing_budget else 'created'} {budget.name} — "
		  f"{budget.budget_kg:,.0f} kg across {len(budget.months)} months.")
