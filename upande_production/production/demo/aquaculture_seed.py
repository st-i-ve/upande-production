"""Idempotent demo data for the aquaculture pages (Mutara ponds).

bench --site mutara.local execute upande_production.production.demo.aquaculture_seed.run

One stocking per pond at different ages, daily feeding for the life of each batch, weekly
sampling, twice-daily water readings for four weeks, a low-oxygen night with a mortality
spike in one pond, and one pond harvested (into Production Harvest, crop Aquaculture, kg, so
Overview and Costs agree). Dates are relative to today. Every figure is in DEMO.

Each run removes what an earlier run made (marked with MARK) and rebuilds it, so the data is
always current. It never touches crop cycles.
"""

import random

import frappe
from frappe.utils import add_days, flt, get_datetime, getdate, now_datetime, nowdate

MARK = "Demo data"

DEMO = {
	"seed": 20261028,
	"crop": "Aquaculture",
	"price_per_kg": 320,
	"water_days": 28,
	"readings_per_day": [("06:00", "morning"), ("15:00", "afternoon")],
	"sample_size": 30,
	"fcr": 1.5,                        # feed per kg gained, with noise
	"growth": {"k": 0.5, "exp": 1.3},  # weight_g = w0 + k * days ** exp
	# pond -> batch. age_days: days since stocking. harvested_days_ago: final harvest.
	"ponds": {
		"Pond 1": {"species": "Tilapia", "age_days": 70, "count": 8000, "w0": 5.0, "target_g": 450, "target_days": 210,
				   "source": "Kenya Fish Hatcheries, Sagana", "k": 0.50},
		"Pond 2": {"species": "Tilapia", "age_days": 45, "count": 6000, "w0": 4.5, "target_g": 450, "target_days": 200,
				   "source": "Kenya Fish Hatcheries, Sagana", "k": 0.52},
		"Pond 3": {"species": "Tilapia", "age_days": 176, "count": 5000, "w0": 6.0, "target_g": 450, "target_days": 170,
				   "source": "Lake Basin Hatchery, Kisumu", "k": 0.46, "harvested_days_ago": 6},
		"Pond 4": {"species": "Tilapia", "age_days": 90, "count": 7000, "w0": 5.0, "target_g": 450, "target_days": 190,
				   "source": "Lake Basin Hatchery, Kisumu", "k": 0.48},
	},
	"feed_types": [(0, "Starter Crumble"), (25, "Grower Pellet 2mm"), (70, "Grower Pellet 4mm"), (120, "Finisher Pellet 6mm")],
	"feeding_times": "06:30, 12:30, 17:00",
	"daily_mortality": {"chance": 0.5, "min": 2, "max": 9, "causes": ["Unknown", "Disease", "Predation", "Handling"]},
	# A low-oxygen night: days ago, morning DO, fish lost that day and the two after.
	"low_do": {"pond": "Pond 4", "days_ago": 5, "do": 2.4, "dead": [240, 70, 25]},
	# A few mild out-of-band readings so the alert list is not empty: pond, days ago, field, value.
	"nudges": [("Pond 2", 9, "ammonia_mg_l", 0.62), ("Pond 1", 3, "temperature_c", 24.2)],
}


def _rng(key):
	return random.Random(f"{DEMO['seed']}:{key}")


def _insert(vals):
	doc = frappe.get_doc(vals)
	doc.insert(ignore_permissions=True)
	return doc


def _weight(cfg, d):
	g = DEMO["growth"]
	return cfg["w0"] + cfg["k"] * (d ** g["exp"])


def _ensure_unit(name):
	if frappe.db.exists("Production Unit", name):
		return
	farm = frappe.db.exists("Farm", "Mutara") and "Mutara" or None
	_insert({"doctype": "Production Unit", "unit_name": name, "crop": DEMO["crop"], "unit_type": "Pond",
			 "farm": farm, "status": "Active"})


def _clear():
	"""Remove an earlier run's records (marked) so this run rebuilds them."""
	stockings = frappe.get_all("Pond Stocking", filters={"notes": MARK}, pluck="name", limit_page_length=0)
	if stockings:
		for dt in ("Pond Feeding Log", "Fish Mortality Log", "Fish Sampling Log"):
			frappe.db.delete(dt, {"stocking": ("in", stockings)})
		frappe.db.delete("Pond Stocking", {"name": ("in", stockings)})
	frappe.db.delete("Water Quality Reading", {"notes": ("like", f"{MARK}%")})
	# Fish harvest lives in Production Harvest; the seed owns every Aquaculture row (no crop cycles feed it).
	frappe.db.delete("Production Harvest", {"crop": DEMO["crop"]})


def _stock(pond, cfg, today):
	start = add_days(today, -cfg["age_days"])
	harvest_ago = cfg.get("harvested_days_ago")
	return _insert({
		"doctype": "Pond Stocking", "pond": pond, "species": cfg["species"], "stocking_date": start,
		"fingerlings_count": cfg["count"], "avg_weight_g": cfg["w0"], "source": cfg["source"],
		"target_harvest_weight_g": cfg["target_g"], "target_harvest_date": add_days(start, cfg["target_days"]),
		"status": "Growing", "notes": MARK,
	})


def _feed_type(d):
	name = DEMO["feed_types"][0][1]
	for from_day, n in DEMO["feed_types"]:
		if d >= from_day:
			name = n
	return name


def _life(pond, cfg, st, today):
	"""Feeding, mortality and sampling for one batch; returns (live fish, last day, deaths by day)."""
	r = _rng(pond)
	age = cfg["age_days"]
	last = age - cfg.get("harvested_days_ago", 0)       # last day the fish were in the water
	low = DEMO["low_do"]
	dm = DEMO["daily_mortality"]
	live, made = cfg["count"], {"feed": 0, "dead": 0, "sample": 0}
	spike = {}
	if low["pond"] == pond:
		for i, n in enumerate(low["dead"]):
			spike[age - low["days_ago"] + i] = n
	for d in range(1, last + 1):
		day = add_days(st.stocking_date, d)
		dw = max(_weight(cfg, d) - _weight(cfg, d - 1), 0.05)
		kg = round(DEMO["fcr"] * live * dw / 1000.0 * r.uniform(0.92, 1.08), 1)
		if kg > 0:
			_insert({"doctype": "Pond Feeding Log", "pond": pond, "stocking": st.name, "feed_date": day,
					 "feed_type": _feed_type(d), "kg_fed": kg, "feeding_times": DEMO["feeding_times"]})
			made["feed"] += 1
		n, cause = 0, None
		if d in spike:
			n, cause = spike[d], "Low DO"
		elif r.random() < dm["chance"]:
			n, cause = r.randint(dm["min"], dm["max"]), r.choice(dm["causes"])
		if n:
			n = min(n, live - 1)
			_insert({"doctype": "Fish Mortality Log", "pond": pond, "stocking": st.name, "mortality_date": day,
					 "dead_count": n, "cause": cause,
					 "notes": "Overnight oxygen crash, aerators were off" if cause == "Low DO" else None})
			live -= n
			made["dead"] += 1
		if d % 7 == 0 or d == last:
			_insert({"doctype": "Fish Sampling Log", "pond": pond, "stocking": st.name, "sample_date": day,
					 "sample_size": DEMO["sample_size"], "avg_weight_g": round(_weight(cfg, d) * r.uniform(0.97, 1.03), 1)})
			made["sample"] += 1
	return live, last, made


def _water(pond, cfg, today):
	r = _rng(f"water:{pond}")
	low = DEMO["low_do"]
	end_ago = cfg.get("harvested_days_ago", 0)
	n = 0
	for ago in range(DEMO["water_days"] - 1, end_ago - 1, -1):
		if ago >= cfg["age_days"]:
			continue
		day = add_days(today, -ago)
		for hhmm, part in DEMO["readings_per_day"]:
			am = part == "morning"
			if get_datetime(f"{day} {hhmm}:00") > now_datetime():
				continue
			v = {
				"dissolved_oxygen_mg_l": round(r.uniform(4.8, 6.0) if am else r.uniform(6.2, 8.0), 1),
				"ph": round(r.uniform(7.1, 7.8) if am else r.uniform(7.6, 8.3), 1),
				"temperature_c": round(r.uniform(25.6, 27.0) if am else r.uniform(27.8, 29.6), 1),
				"ammonia_mg_l": round(r.uniform(0.08, 0.28), 2),
				"nitrite_mg_l": round(r.uniform(0.04, 0.14), 2),
				"secchi_cm": round(r.uniform(26, 40)),
			}
			note = MARK
			if low["pond"] == pond and ago == low["days_ago"] and am:
				v["dissolved_oxygen_mg_l"], note = low["do"], f"{MARK}: oxygen crash, aerators were off"
			if low["pond"] == pond and ago == low["days_ago"] - 1 and am:
				v["dissolved_oxygen_mg_l"], note = 3.6, f"{MARK}: still low after the crash"
			for p, a, field, val in DEMO["nudges"]:
				if p == pond and a == ago and (am or field == "temperature_c" and False):
					v[field] = val
			_insert({"doctype": "Water Quality Reading", "pond": pond, "reading_datetime": f"{day} {hhmm}:00",
					 "notes": note, **v})
			n += 1
	return n


def _harvest(pond, cfg, st, live, today):
	when = add_days(today, -cfg["harvested_days_ago"])
	w = _weight(cfg, cfg["age_days"] - cfg["harvested_days_ago"])
	kg = round(live * w / 1000.0, 1)
	item = cfg["species"] if frappe.db.exists("Item", cfg["species"]) else None
	_insert({"doctype": "Production Harvest", "harvest_date": when, "unit": pond, "crop": DEMO["crop"], "item": item,
			 "qty": kg, "uom": "Kg", "grade": "Class 1", "price_per_uom": DEMO["price_per_kg"]})
	st.harvested_count = live
	st.harvest_date = when
	st.status = "Harvested"
	st.save(ignore_permissions=True)
	return kg


def run(commit=True):
	frappe.flags.in_seed = True
	today = getdate(nowdate())
	_clear()
	out = {"stockings": 0, "feeding": 0, "mortality": 0, "sampling": 0, "water": 0, "harvest_kg": 0}
	for pond, cfg in DEMO["ponds"].items():
		_ensure_unit(pond)
		st = _stock(pond, cfg, today)
		live, last, made = _life(pond, cfg, st, today)
		out["stockings"] += 1
		out["feeding"] += made["feed"]
		out["mortality"] += made["dead"]
		out["sampling"] += made["sample"]
		out["water"] += _water(pond, cfg, today)
		if cfg.get("harvested_days_ago"):
			out["harvest_kg"] += _harvest(pond, cfg, st, live, today)
	if commit:
		frappe.db.commit()
	print(out)
	return out
