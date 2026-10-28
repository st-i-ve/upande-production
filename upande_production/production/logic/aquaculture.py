"""Fish farming rules: safe water bands, batch (pond stocking) maths and doctype validation.

The maths is pure (plain lists in, dicts out) so it can be tested without a database; the
API in `api/aquaculture.py` loads the rows and calls it. A "batch" is a Pond Stocking: fish
have no crop cycles.
"""

import math
from datetime import date, timedelta

import frappe
from frappe.utils import cint, flt, get_datetime, getdate

CROP_KEY = "aquaculture"
CROP_NAME = "Aquaculture"

# Safe bands for tilapia. Each is inclusive; ammonia and nitrite must stay BELOW their limit.
BANDS = {
	"do_min": 4.0,        # dissolved oxygen, mg/L
	"ph_min": 6.5,
	"ph_max": 8.5,
	"temp_min": 25.0,     # deg C
	"temp_max": 30.0,
	"ammonia_max": 0.5,   # mg/L
	"nitrite_max": 0.3,   # mg/L
}

CAUSES = ["Low DO", "Disease", "Predation", "Handling", "Unknown"]


# -- water quality -------------------------------------------------------------


def reading_flags(r: dict, bands: dict | None = None) -> list[dict]:
	"""Every measurement of a reading that is outside its band: [{metric, value, message}]."""
	b = bands or BANDS
	out = []

	def add(metric, value, msg):
		out.append({"metric": metric, "value": value, "message": msg})

	do, ph, t = r.get("dissolved_oxygen_mg_l"), r.get("ph"), r.get("temperature_c")
	nh3, no2 = r.get("ammonia_mg_l"), r.get("nitrite_mg_l")
	if do is not None and do < b["do_min"]:
		add("do", do, f"Dissolved oxygen {do:g} mg/L is under {b['do_min']:g}")
	if ph is not None and not (b["ph_min"] <= ph <= b["ph_max"]):
		add("ph", ph, f"pH {ph:g} is outside {b['ph_min']:g} to {b['ph_max']:g}")
	if t is not None and not (b["temp_min"] <= t <= b["temp_max"]):
		add("temp", t, f"Temperature {t:g} C is outside {b['temp_min']:g} to {b['temp_max']:g}")
	if nh3 is not None and nh3 >= b["ammonia_max"]:
		add("ammonia", nh3, f"Ammonia {nh3:g} mg/L is at or over {b['ammonia_max']:g}")
	if no2 is not None and no2 >= b["nitrite_max"]:
		add("nitrite", no2, f"Nitrite {no2:g} mg/L is at or over {b['nitrite_max']:g}")
	return out


def measured_values(row: dict, fields: list[str]) -> dict:
	"""A stored reading with the measurements that were not taken as None (the DB keeps blank as 0)."""
	taken = set((row.get("measured") or "").split(","))
	return {k: (row.get(k) if k in taken else None) for k in fields}


# -- batch maths ---------------------------------------------------------------


def _d(v):
	return getdate(v) if v else None


def state_at(batch: dict, as_of) -> dict:
	"""A batch as it stood on `as_of`.

	batch keys: stocked, w0_g, start, deaths [(date, n)], samples [(date, avg_g)],
	feeds [(date, kg)], harvested (count), harvest_date, harvest_kg.
	"""
	as_of = _d(as_of)
	stocked = cint(batch["stocked"])
	dead = sum(cint(n) for d, n in batch.get("deaths", []) if _d(d) <= as_of)
	hd = _d(batch.get("harvest_date"))
	harvested = cint(batch.get("harvested") or 0) if (hd and hd <= as_of) else 0
	live = max(stocked - dead - harvested, 0)
	w0 = flt(batch["w0_g"])
	pts = sorted((_d(d), flt(w)) for d, w in batch.get("samples", []) if _d(d) <= as_of)
	avg_w = pts[-1][1] if pts else w0
	biomass = live * avg_w / 1000.0
	feed = sum(flt(k) for d, k in batch.get("feeds", []) if _d(d) <= as_of)
	h_kg = flt(batch.get("harvest_kg") or 0) if (hd and hd <= as_of) else 0.0
	return {
		"live": live, "dead": dead, "harvested": harvested, "avg_weight_g": avg_w,
		"biomass_kg": biomass, "feed_kg": feed, "harvest_kg": h_kg,
		"survival_pct": survival_pct(stocked, dead),
		"fcr": fcr(feed, biomass + h_kg, stocked * w0 / 1000.0),
	}


def survival_pct(stocked, dead) -> float | None:
	"""Share of the fingerlings stocked that did not die (harvested fish are not losses)."""
	if not stocked:
		return None
	return round(max(stocked - dead, 0) / stocked * 100.0, 1)


def fcr(feed_kg, biomass_kg_now, biomass_kg_start) -> float | None:
	"""Feed conversion ratio: kg of feed per kg of weight gained. None until there is a gain."""
	gain = flt(biomass_kg_now) - flt(biomass_kg_start)
	if gain <= 0 or flt(feed_kg) <= 0:
		return None
	return round(flt(feed_kg) / gain, 2)


def growth_curve(batch: dict) -> list[dict]:
	"""[{date, days, avg_weight_g}] from stocking through every sampling."""
	start = _d(batch["start"])
	pts = [(start, flt(batch["w0_g"]))]
	pts += sorted((_d(d), flt(w)) for d, w in batch.get("samples", []) if _d(d) >= start)
	return [{"date": str(d), "days": (d - start).days, "avg_weight_g": round(w, 1)} for d, w in pts]


def growth_rate_g_day(curve: list[dict], window: int = 4) -> float | None:
	"""Recent gain in g/day over the last `window` points of the curve."""
	pts = curve[-window:]
	if len(pts) < 2:
		return None
	days = pts[-1]["days"] - pts[0]["days"]
	if days <= 0:
		return None
	return round((pts[-1]["avg_weight_g"] - pts[0]["avg_weight_g"]) / days, 2)


def projection(latest_g, rate, as_of, target_g=None, target_date=None) -> dict:
	"""When the batch reaches the target weight, and what it weighs on the target date."""
	as_of = _d(as_of)
	out = {"projected_harvest_date": None, "projected_weight_g": None, "on_track": None, "days_to_target": None}
	if not rate or rate <= 0:
		return out
	if target_date:
		td = _d(target_date)
		out["projected_weight_g"] = round(latest_g + rate * max((td - as_of).days, 0), 1)
	if target_g:
		days = 0 if latest_g >= target_g else math.ceil((target_g - latest_g) / rate)
		out["days_to_target"] = days
		out["projected_harvest_date"] = str(as_of + timedelta(days=days))
		if target_date:
			out["on_track"] = (as_of + timedelta(days=days)) <= _d(target_date) + timedelta(days=7)
	return out


def batch_metrics(batch: dict, as_of) -> dict:
	"""Everything the batch card shows, from one batch dict (see `state_at`)."""
	as_of = _d(as_of)
	end = _d(batch.get("harvest_date")) if batch.get("closed") and batch.get("harvest_date") else as_of
	end = min(end, as_of)
	s = state_at(batch, as_of)
	curve = growth_curve(batch)
	rate = growth_rate_g_day(curve)
	closed = bool(batch.get("closed"))
	proj = (
		{"projected_harvest_date": None, "projected_weight_g": None, "on_track": None, "days_to_target": None}
		if closed
		else projection(s["avg_weight_g"], rate, as_of, batch.get("target_g"), batch.get("target_date"))
	)
	return {
		**s,
		"days_in_water": max((end - _d(batch["start"])).days, 0),
		"growth_curve": curve,
		"growth_g_day": rate,
		**proj,
	}


# -- validation -----------------------------------------------------------------


def _need_pond(doc):
	crop = frappe.db.get_value("Production Unit", doc.pond, "crop")
	if crop != CROP_NAME:
		frappe.throw(f"{doc.pond} is not an aquaculture pond.")


def _link_stocking(doc, date_field):
	"""Default `stocking` to the pond's growing batch on that date; check it belongs to the pond."""
	if doc.stocking:
		pond = frappe.db.get_value("Pond Stocking", doc.stocking, "pond")
		if pond != doc.pond:
			frappe.throw(f"{doc.stocking} is a stocking of {pond}, not {doc.pond}.")
		return
	d = getdate(doc.get(date_field))
	rows = frappe.get_all(
		"Pond Stocking",
		filters={"pond": doc.pond, "stocking_date": ("<=", d)},
		fields=["name", "status", "harvest_date"],
		order_by="stocking_date desc, creation desc",
		limit_page_length=5,
	)
	for r in rows:
		if r.status == "Growing" or (r.harvest_date and getdate(r.harvest_date) >= d):
			doc.stocking = r.name
			return


def validate_pond_stocking(doc):
	_need_pond(doc)
	if cint(doc.fingerlings_count) <= 0:
		frappe.throw("Fingerlings count must be more than zero.")
	if flt(doc.avg_weight_g) <= 0:
		frappe.throw("Average weight at stocking must be more than zero.")
	if doc.target_harvest_date and getdate(doc.target_harvest_date) < getdate(doc.stocking_date):
		frappe.throw("Target harvest date cannot be before the stocking date.")
	if doc.target_harvest_weight_g and flt(doc.target_harvest_weight_g) <= flt(doc.avg_weight_g):
		frappe.throw("Target harvest weight must be above the weight at stocking.")
	if cint(doc.harvested_count) < 0 or cint(doc.harvested_count) > cint(doc.fingerlings_count):
		frappe.throw("Harvested count cannot be negative or more than were stocked.")


def validate_water_quality_reading(doc):
	_need_pond(doc)
	vals = {
		"dissolved_oxygen_mg_l": doc.dissolved_oxygen_mg_l, "ph": doc.ph, "temperature_c": doc.temperature_c,
		"ammonia_mg_l": doc.ammonia_mg_l, "nitrite_mg_l": doc.nitrite_mg_l, "secchi_cm": doc.secchi_cm,
	}
	if all(v in (None, "") for v in vals.values()):
		frappe.throw("Record at least one water measurement.")
	for k, v in vals.items():
		if v not in (None, "") and flt(v) < 0:
			frappe.throw(f"{k.replace('_', ' ')} cannot be negative.")
	if doc.ph not in (None, "") and flt(doc.ph) > 14:
		frappe.throw("pH must be between 0 and 14.")
	if get_datetime(doc.reading_datetime) > get_datetime(frappe.utils.now_datetime()) + timedelta(minutes=5):
		frappe.throw("Reading time cannot be in the future.")
	if not doc.reader:
		doc.reader = frappe.session.user
	taken = {k: (flt(v) if v not in (None, "") else None) for k, v in vals.items()}
	doc.measured = ",".join(k for k, v in taken.items() if v is not None)  # blank floats are stored as 0
	flags = reading_flags(taken)
	doc.out_of_band = 1 if flags else 0
	doc.flag_notes = "; ".join(f["message"] for f in flags)


def validate_pond_feeding_log(doc):
	_need_pond(doc)
	if flt(doc.kg_fed) <= 0:
		frappe.throw("Kg fed must be more than zero.")
	_link_stocking(doc, "feed_date")
	times = [t.strip() for t in (doc.feeding_times or "").replace(";", ",").split(",") if t.strip()]
	doc.times_fed = len(times)
	if not doc.recorded_by:
		doc.recorded_by = frappe.session.user


def validate_fish_mortality_log(doc):
	_need_pond(doc)
	if cint(doc.dead_count) <= 0:
		frappe.throw("Mortality count must be more than zero.")
	_link_stocking(doc, "mortality_date")
	if not doc.recorded_by:
		doc.recorded_by = frappe.session.user


def validate_fish_sampling_log(doc):
	_need_pond(doc)
	if cint(doc.sample_size) <= 0:
		frappe.throw("Sample size must be more than zero.")
	if flt(doc.avg_weight_g) <= 0:
		frappe.throw("Average weight must be more than zero.")
	_link_stocking(doc, "sample_date")
	if not doc.recorded_by:
		doc.recorded_by = frappe.session.user
