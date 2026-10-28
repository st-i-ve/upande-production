"""Idempotent demo data for the Fruits & Vegetables field logs (Mutara).

bench --site mutara.local execute upande_production.production.demo.fv_seed.run

Fills Pivot Irrigation Run (about six weeks, 2-3 runs a week per pivot, one tower
misalignment on Pivot 3) and Harvest Grading Log (one per existing Production Harvest
row on a pivot block, so graded kg plus rejects equals the harvested kg). Every
invented figure is in FV below. Rows carry the marker in FV["marker"] in their notes;
a re-run deletes those rows and writes them again, nothing else is touched.
"""

import random
from datetime import datetime, timedelta

import frappe
from frappe.utils import add_days, getdate, nowdate

from upande_production.production.logic.stages import product_item

FV = {
	"seed": 20261029,
	"marker": "[fv-seed]",
	"weeks": 6,
	"pivots": ["Pivot 1", "Pivot 2", "Pivot 3", "Pivot 4"],
	"runs_per_week": (2, 3),
	"run_hours": (9, 20),
	"depth_mm": (9.5, 14.0),
	"full_circle_share": 0.8,
	"start_hours": (5, 21),
	"water_sources": ["Borehole 2", "Ewaso Dam", "Borehole 2", "River intake"],
	"percent_timers": [60, 70, 80, 100],
	"operators": ["HR-EMP-00300", "HR-EMP-00301", "HR-EMP-00302"],
	# (pivot, weeks back from the current week, fault, depth factor, hours factor)
	"faults": [
		("Pivot 3", 2, "Tower misalignment", 0.35, 0.4),
		("Pivot 2", 4, "Pressure drop", 0.6, 0.7),
		("Pivot 4", 1, "Power", 0.5, 0.5),
	],
	"fault_notes": {
		"Tower misalignment": "Tower 7 out of line, pivot stopped on the alarm. Realigned the next morning.",
		"Pressure drop": "Pump pressure fell below 2.2 bar, run cut short.",
		"Power": "Grid outage mid-run.",
	},
	# item -> grade split shares (sum to 1) and reject range (share of received kg)
	"grades": {
		"Potatoes": {"Class 1": 0.58, "Class 2": 0.2, "Ware": 0.12, "Seed": 0.06, "Chats": 0.04},
		"Cabbage": {"Class 1": 0.72, "Class 2": 0.2, "Ware": 0.08},
		"Onion": {"Class 1": 0.66, "Class 2": 0.22, "Chats": 0.12},
		"Passion Fruit": {"Class 1": 0.7, "Class 2": 0.2, "Ware": 0.1},
	},
	"reject_share": (0.02, 0.07),
	"reject_reasons": {
		"Potatoes": ["Greening", "Mechanical damage", "Rot", "Undersize"],
		"Cabbage": ["Pest damage", "Rot", "Mechanical damage"],
		"Onion": ["Rot", "Undersize", "Mechanical damage"],
		"Passion Fruit": ["Undersize", "Pest damage", "Rot"],
	},
	"kg_per_crate": {"Potatoes": 50, "Cabbage": 30, "Onion": 25, "Passion Fruit": 4},
	"graders": ["HR-EMP-00303", "HR-EMP-00304"],
}


def _clear():
	for dt in ("Pivot Irrigation Run", "Harvest Grading Log"):
		for n in frappe.get_all(dt, filters={"notes": ("like", f"%{FV['marker']}%")}, pluck="name"):
			frappe.delete_doc(dt, n, force=True, ignore_permissions=True)


def _seed_irrigation(rng):
	today = getdate(nowdate())
	week0 = add_days(today, -today.weekday() - 7 * (FV["weeks"] - 1))
	faults = {(p, FV["weeks"] - 1 - back): (f, d, h) for p, back, f, d, h in FV["faults"]}
	made = 0
	for pivot in FV["pivots"]:
		if not frappe.db.exists("Production Unit", pivot):
			continue
		slices = sorted(frappe.get_all("Production Unit", filters={"parent_production_unit": pivot}, pluck="name"))
		for w in range(FV["weeks"]):
			n = rng.randint(*FV["runs_per_week"])
			days = sorted(rng.sample(range(7), n))
			fault = faults.get((pivot, w))
			for i, d in enumerate(days):
				day = add_days(week0, w * 7 + d)
				if getdate(day) > today:
					continue
				start = datetime.combine(getdate(day), datetime.min.time()) + timedelta(hours=rng.randint(*FV["start_hours"]))
				hours = rng.randint(*FV["run_hours"])
				depth = round(rng.uniform(*FV["depth_mm"]), 1)
				flt_name, notes = "None", FV["marker"]
				if fault and i == 0:
					flt_name, df, hf = fault
					depth, hours = round(depth * df, 1), max(2, round(hours * hf))
					notes = f"{FV['fault_notes'][flt_name]} {FV['marker']}"
				end = start + timedelta(hours=hours)
				if end > datetime.now():
					end = min(end, datetime.now() - timedelta(minutes=5))
					if end <= start:
						continue
				covered = slices if rng.random() < FV["full_circle_share"] or len(slices) < 3 else sorted(rng.sample(slices, 2))
				if fault and i == 0:
					covered = slices[:2]
				frappe.get_doc({
					"doctype": "Pivot Irrigation Run", "unit": pivot, "start_time": start, "end_time": end,
					"depth_mm": depth, "direction": rng.choice(["Forward", "Reverse"]),
					"percent_timer": rng.choice(FV["percent_timers"]), "water_source": rng.choice(FV["water_sources"]),
					"operator": rng.choice(FV["operators"]), "fault": flt_name, "notes": notes,
					"slices": [{"slice": s} for s in covered],
				}).insert(ignore_permissions=True)
				made += 1
	return made


def _seed_grading(rng):
	harvests = frappe.get_all(
		"Production Harvest", filters={"unit": ("like", "P_-B_")},
		fields=["unit", "cycle", "item", "harvest_date", "qty"], order_by="harvest_date asc, unit asc",
	)
	harvests = [h for h in harvests if product_item(h.item) in FV["grades"]]  # varieties grade like their product
	made = 0
	for h in harvests:
		recv = round(float(h.qty), 1)
		rejects = round(recv * rng.uniform(*FV["reject_share"]), 1)
		graded = round(recv - rejects, 1)
		prod = product_item(h.item)
		split = FV["grades"][prod]
		names = list(split)
		kgs, running = [], 0.0
		for i, g in enumerate(names):
			kg = round(graded - running, 1) if i == len(names) - 1 else round(graded * split[g] * rng.uniform(0.93, 1.07), 1)
			kg = max(kg, 0.0)
			kgs.append(kg)
			running += kg
		per_crate = FV["kg_per_crate"][prod]
		frappe.get_doc({
			"doctype": "Harvest Grading Log", "unit": h.unit, "cycle": h.cycle, "item": h.item,
			"grading_date": h.harvest_date, "received_kg": recv, "received_crates": round(recv / per_crate),
			"graded_by": rng.choice(FV["graders"]), "rejects_kg": rejects,
			"reject_reason": rng.choice(FV["reject_reasons"][prod]), "notes": FV["marker"],
			"lines": [{"grade": g, "kg": kg, "crates": round(kg / per_crate, 1)} for g, kg in zip(names, kgs)],
		}).insert(ignore_permissions=True)
		made += 1
	return made


def run():
	rng = random.Random(FV["seed"])
	_clear()
	out = {"irrigation_runs": _seed_irrigation(rng), "grading_logs": _seed_grading(rng)}
	frappe.db.commit()
	print(f"fv seed: {out}")
	return out
