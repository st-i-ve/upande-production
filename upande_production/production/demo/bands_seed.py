"""Default KPI bands (Production Settings > Bands). Idempotent: a band set that already has rows is
left alone, so a manager's edits survive a re-run.

bench --site mutara.local execute upande_production.production.demo.bands_seed.run

Rows are (label, metric, from, up to, severity); `up to` 0 means no upper limit.
"""

import frappe

BANDS = {
	"Forecast error": [
		("Within 10%", "percent off forecast", 0, 10, "Good"),
		("Within 25%", "percent off forecast", 10, 25, "Watch"),
		("Beyond 25%", "percent off forecast", 25, 0, "Critical"),
	],
	"Estimate accuracy": [
		("Needs review", "percent of delivered", 0, 90, "Watch"),
		("Accurate", "percent of delivered", 90, 0, "Good"),
	],
	"Irrigation % of target": [
		("Under 50% of target", "percent of period target", 0, 50, "Critical"),
		("50-90%", "percent of period target", 50, 90, "Watch"),
		("On target (90-125%)", "percent of period target", 90, 125, "Good"),
		("Over 125%", "percent of period target", 125, 0, "Watch"),
	],
	"Fish survival": [
		("Low", "percent of fingerlings", 0, 90, "Critical"),
		("On track", "percent of fingerlings", 90, 0, "Good"),
	],
	"Queen status": [
		("queenless", "percent of colonies queenright", 0, 80, "Critical"),
		("weak", "percent of colonies queenright", 80, 95, "Watch"),
		("queenright", "percent of colonies queenright", 95, 0, "Good"),
	],
	"Grade A share": [
		("Low", "percent of honey by weight", 0, 60, "Watch"),
		("Healthy", "percent of honey by weight", 60, 0, "Good"),
	],
}


def run(commit=True):
	doc = frappe.get_doc("Production Settings")
	have = {r.band_set for r in doc.bands}
	added = []
	for band_set, rows in BANDS.items():
		if band_set in have:
			continue
		for label, metric, lo, hi, sev in rows:
			doc.append("bands", {"band_set": band_set, "label": label, "metric": metric, "min": lo, "max": hi, "severity": sev})
		added.append(band_set)
	if added:
		doc.flags.ignore_permissions = True
		doc.save()
		if commit:
			frappe.db.commit()
	return added
