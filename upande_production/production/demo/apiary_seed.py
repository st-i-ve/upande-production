"""Idempotent demo data for the Apiary pages (hive inspections, honey harvest).

bench --site mutara.local execute upande_production.production.demo.apiary_seed.run

About 12 weeks of inspections every ~10 days per hive group (Hive Group North's varroa
climbs through the 3 per 100 threshold; Hive Group South has one queenless event that
requeens itself), and honey harvests in the flow months. Honey Harvest Log rows mirror
themselves into Production Harvest (crop Apiary, kg), so Overview, Forecast and Costs read
the same honey as the Honey Harvest page. The older generic demo harvests for Apiary
(seed.py) are removed so honey is not counted twice.

Every invented figure is in DEMO. Dates are relative to today so the data never goes stale.
"""

import random

import frappe
from frappe.utils import add_days, nowdate

DEMO = {
	"seed": 20261028,
	"inspection_every_days": 10,
	"inspection_weeks": 12,
	# unit -> inspection profile. mites: (first, last) per 100 bees, linear plus noise.
	# queenless: {inspection index: colonies queenright}; others are queenright = colonies.
	"groups": {
		"Hive Group North": {"colonies": 12, "mites": (0.8, 4.6), "queenless": {},
							 "brood": ["Solid"] * 6 + ["Patchy"] * 3, "temper": ["Calm"] * 5 + ["Nervous"] * 4,
							 "disease": {7: "Small hive beetle", 8: "Chalkbrood"}, "feeding": {0: 0, 1: 0}},
		"Hive Group South": {"colonies": 10, "mites": (0.6, 1.3), "queenless": {5: 7, 6: 8, 7: 10},
							 "brood": ["Solid"] * 4 + ["Patchy", "Patchy", "None", "Patchy", "Solid"],
							 "temper": ["Calm"] * 5 + ["Aggressive", "Nervous", "Calm", "Calm"],
							 "disease": {}, "feeding": {5: 4.0, 6: 4.0}},
	},
	# unit -> list of (days ago, supers, frames, kg, moisture %, grade, wax kg). The flow
	# months are the two rains: spring flow (Mar-Apr) and the autumn one (Sep-Oct).
	"harvests": {
		"Hive Group North": [(15, 8, 62, 118.0, 17.8, "A", 3.1), (47, 6, 48, 92.5, 18.6, "A", 2.4),
							 (70, 5, 40, 71.0, 19.4, "B", 1.9), (222, 9, 70, 131.0, 17.4, "A", 3.4),
							 (251, 7, 55, 104.5, 18.9, "A", 2.8)],
		"Hive Group South": [(20, 7, 54, 98.0, 17.5, "A", 2.6), (52, 5, 41, 74.0, 18.2, "A", 2.0),
							 (76, 4, 30, 51.5, 20.3, "C", 1.4), (216, 8, 62, 112.5, 17.9, "A", 3.0),
							 (247, 6, 47, 83.0, 19.1, "B", 2.2)],
	},
	"inspector": None,  # None picks the first active Employee
	# Production Crop limits (editable in Desk); only filled where the crop has none.
	"limits": {"mite_threshold": 3.0, "mite_watch": 2.0, "honey_moisture_limit": 20.0},
}

INSPECTION = "Hive Inspection Log"
HARVEST = "Honey Harvest Log"


def _unit(name):
	return frappe.db.get_value("Production Unit", {"unit_name": name, "crop": "Apiary"}, "name")


def _clear_demo_rows():
	"""Dates are relative to today (in the site time zone), so a key of unit + date matches
	nothing after midnight and a second run would add a second, shifted set. The demo
	groups hold only seeded rows, so the seed removes its own and re-inserts for today."""
	units = [u for u in map(_unit, DEMO["groups"]) if u]
	for dt in (INSPECTION, HARVEST):
		for n in frappe.get_all(dt, filters={"unit": ["in", units]}, pluck="name", limit_page_length=0):
			frappe.delete_doc(dt, n, force=True, ignore_permissions=True)


def ensure_limits():
	"""Mite threshold and watch, honey moisture limit on the Apiary crop; the default Bands (queen status,
	grade A share) are seeded with the rest of the Settings bands."""
	from upande_production.production.demo import bands_seed

	bands_seed.run(commit=False)
	crop = frappe.db.exists("Production Crop", "Apiary")
	if not crop:
		return {}
	have = frappe.db.get_value("Production Crop", crop, list(DEMO["limits"]), as_dict=True)
	todo = {k: v for k, v in DEMO["limits"].items() if not have.get(k)}
	if todo:
		frappe.db.set_value("Production Crop", crop, todo)
	return todo


def run(commit=True):
	frappe.flags.in_demo_seed = True
	ensure_limits()
	_clear_demo_rows()
	inspector = DEMO["inspector"] or frappe.db.get_value("Employee", {"status": "Active"}, "name")
	made = {"inspections": 0, "harvests": 0}
	steps = DEMO["inspection_weeks"] * 7 // DEMO["inspection_every_days"] + 1

	for name, g in DEMO["groups"].items():
		unit = _unit(name)
		if not unit:
			continue
		rng = random.Random(f"{DEMO['seed']}:{name}")
		for i in range(steps):
			days_ago = (steps - 1 - i) * DEMO["inspection_every_days"] + 2
			d = add_days(nowdate(), -days_ago)
			if frappe.db.exists(INSPECTION, {"unit": unit, "inspection_date": d}):
				continue
			lo, hi = g["mites"]
			mites = round(max(0.1, lo + (hi - lo) * i / (steps - 1) + rng.uniform(-0.25, 0.25)), 1)
			qr = g["queenless"].get(i, g["colonies"])
			queenless = qr < g["colonies"]
			doc = frappe.get_doc({
				"doctype": INSPECTION, "unit": unit, "inspection_date": d, "inspector": inspector,
				"colonies_inspected": g["colonies"], "colonies_queenright": qr,
				"queen_seen": 0 if queenless else int(rng.random() < 0.7),
				"eggs_seen": 0 if (queenless and qr < g["colonies"] * 0.75) else 1,
				"brood_pattern": g["brood"][i % len(g["brood"])], "temperament": g["temper"][i % len(g["temper"])],
				"varroa_per_100": mites, "disease_signs": g["disease"].get(i, "None"),
				"frames_brood": round(rng.uniform(4.5, 7.0) - (2 if queenless else 0), 1),
				"frames_honey": round(rng.uniform(2.0, 5.5), 1), "frames_stores": round(rng.uniform(1.5, 4.0), 1),
				"feeding_kg": g["feeding"].get(i, 0),
				"actions": ("Queenless colonies found; introduced mated queens." if queenless
								   else "Mite load above threshold; treatment planned." if mites > 3 else "Routine inspection."),
			})
			doc.insert(ignore_permissions=True)
			made["inspections"] += 1

	for name, rows in DEMO["harvests"].items():
		unit = _unit(name)
		if not unit:
			continue
		for days_ago, supers, frames, kg, moisture, grade, wax in rows:
			d = add_days(nowdate(), -days_ago)
			if frappe.db.exists(HARVEST, {"unit": unit, "harvest_date": d}):
				continue
			frappe.get_doc({
				"doctype": HARVEST, "unit": unit, "harvest_date": d, "supers_removed": supers,
				"frames_extracted": frames, "honey_kg": kg, "moisture_pct": moisture, "grade": grade,
				"wax_kg": wax, "notes": None,
			}).insert(ignore_permissions=True)
			made["harvests"] += 1

	# The generic demo harvests seed.py wrote for the honey cycles are replaced by the
	# logs above (one source of truth).
	linked = set(frappe.get_all(HARVEST, pluck="production_harvest", limit_page_length=0))
	for n in frappe.get_all("Production Harvest", filters={"crop": "Apiary", "grade": "Class 1"}, pluck="name"):
		if n not in linked:
			frappe.delete_doc("Production Harvest", n, force=True, ignore_permissions=True)

	if commit:
		frappe.db.commit()
	return made
