"""JSON endpoints for the aquaculture pages in the React app.

One endpoint per page (`pond_batches`, `water_quality`, `feeding_mortality`) plus the
write actions behind each record dialog. A fish "batch" is a Pond Stocking: fish have no
crop cycles. The maths (survival, FCR, growth, safe bands) lives in
`production/logic/aquaculture.py`; this module selects, joins and shapes.

Units are in the field names: `_kg`, `_g`, `_mg_l`, `_c`, `_cm`, `_pct`. Every endpoint
returns data or `{"error": msg}` (see api/envelope.py).
"""

import frappe
from frappe.utils import add_days, cint, flt, get_datetime, getdate, now_datetime, nowdate

from upande_production.api.envelope import as_dict, run
from upande_production.production.logic import aquaculture as logic
from upande_production.production.logic import bands as band_logic

CROP = logic.CROP_NAME
WEEKS = 8


# -- helpers -----------------------------------------------------------------


def _need(doctype, ptype="read"):
	frappe.has_permission(doctype, ptype, throw=True)


def _num(v):
	if v is None or v == "":
		return None
	try:
		return float(v)
	except (TypeError, ValueError):
		return None


def _pond_units(unit=None):
	filters = {"crop": CROP, "status": "Active"}
	if unit:
		filters["name"] = unit
	return frappe.get_all("Production Unit", filters=filters, fields=["name", "unit_name", "farm"],
						  order_by="unit_name asc", limit_page_length=0)


def _range(from_date, to_date, days=14):
	end = getdate(to_date) if to_date else getdate(nowdate())
	start = getdate(from_date) if from_date else add_days(end, -(days - 1))
	if start > end:
		frappe.throw("The start date is after the end date.")
	return start, end


def _week_ends(today, n=WEEKS):
	return [add_days(today, -7 * k) for k in range(n - 1, -1, -1)]


def _series(points):
	return [{"week": str(d), "date": str(d), "value": v} for d, v in points]


def _stocking_dicts(rows):
	"""Load deaths, samples, feeds and harvest kg for these Pond Stocking rows -> batch dicts."""
	names = [r.name for r in rows]
	if not names:
		return []
	deaths, samples, feeds = {}, {}, {}
	for r in frappe.get_all("Fish Mortality Log", filters={"stocking": ("in", names)},
							fields=["stocking", "mortality_date", "dead_count"], limit_page_length=0):
		deaths.setdefault(r.stocking, []).append((r.mortality_date, r.dead_count))
	for r in frappe.get_all("Fish Sampling Log", filters={"stocking": ("in", names)},
							fields=["stocking", "sample_date", "avg_weight_g"], limit_page_length=0):
		samples.setdefault(r.stocking, []).append((r.sample_date, r.avg_weight_g))
	for r in frappe.get_all("Pond Feeding Log", filters={"stocking": ("in", names)},
							fields=["stocking", "feed_date", "kg_fed"], limit_page_length=0):
		feeds.setdefault(r.stocking, []).append((r.feed_date, r.kg_fed))
	out = []
	for r in rows:
		closed = r.status in ("Harvested", "Closed")
		hk = 0.0
		if r.harvest_date or closed:
			hf = {"unit": r.pond, "crop": CROP, "harvest_date": (">=", r.stocking_date)}
			if r.harvest_date:
				hf["harvest_date"] = ("between", [r.stocking_date, r.harvest_date])
			hk = sum(flt(x) for x in frappe.get_all("Production Harvest", filters=hf, pluck="qty", limit_page_length=0))
		out.append({
			"name": r.name, "pond": r.pond, "species": r.species, "status": r.status,
			"stocked": cint(r.fingerlings_count), "w0_g": flt(r.avg_weight_g), "start": r.stocking_date,
			"deaths": deaths.get(r.name, []), "samples": samples.get(r.name, []), "feeds": feeds.get(r.name, []),
			"harvested": cint(r.harvested_count), "harvest_date": r.harvest_date, "harvest_kg": hk,
			"closed": closed, "target_g": flt(r.target_harvest_weight_g) or None,
			"target_date": r.target_harvest_date, "source": r.source,
		})
	return out


def _pooled(batches, today):
	"""Estate figures for a set of batch dicts as of one date."""
	st = [logic.state_at(b, today) for b in batches]
	stocked = sum(b["stocked"] for b in batches)
	dead = sum(s["dead"] for s in st)
	feed = sum(s["feed_kg"] for s in st)
	now_bio = sum(s["biomass_kg"] + s["harvest_kg"] for s in st)
	start_bio = sum(b["stocked"] * b["w0_g"] / 1000.0 for b in batches)
	return {
		"live": sum(s["live"] for s in st),
		"biomass_kg": round(sum(s["biomass_kg"] for s in st), 1),
		"feed_kg": round(feed, 1),
		"fcr": logic.fcr(feed, now_bio, start_bio),
		"survival_pct": logic.survival_pct(stocked, dead),
	}


# -- pond batches ---------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
@run
def pond_batches(status=None, unit=None):
	"""Every Pond Stocking with its live count, survival, growth, biomass, feed, FCR and projection."""
	_need("Pond Stocking")
	today = getdate(nowdate())
	filters = {}
	if status:
		filters["status"] = status
	if unit:
		filters["pond"] = unit
	rows = frappe.get_all(
		"Pond Stocking", filters=filters, order_by="stocking_date desc, creation desc", limit_page_length=0,
		fields=["name", "pond", "species", "status", "stocking_date", "fingerlings_count", "avg_weight_g", "source",
				"target_harvest_weight_g", "target_harvest_date", "harvest_date", "harvested_count", "notes"],
	)
	dicts = _stocking_dicts(rows)
	by_unit = {u.name: u for u in _pond_units()}
	week_ago = add_days(today, -7)
	batches = []
	for r, b in zip(rows, dicts):
		m = logic.batch_metrics(b, today)
		feed_7d = sum(flt(k) for d, k in b["feeds"] if getdate(d) > week_ago)
		dead_7d = sum(cint(n) for d, n in b["deaths"] if getdate(d) > week_ago)
		last = max((getdate(d) for d, _ in b["samples"]), default=None)
		batches.append({
			"name": r.name, "pond": r.pond, "pond_name": by_unit[r.pond].unit_name if r.pond in by_unit else r.pond,
			"species": r.species, "status": r.status, "source": r.source, "notes": r.notes,
			"stocking_date": str(r.stocking_date), "stocked": b["stocked"], "stocking_weight_g": b["w0_g"],
			"target_weight_g": b["target_g"], "target_date": str(r.target_harvest_date) if r.target_harvest_date else None,
			"harvest_date": str(r.harvest_date) if r.harvest_date else None,
			"feed_7d_kg": round(feed_7d, 1), "dead_7d": dead_7d,
			"last_sampled": str(last) if last else None,
			"sample_age_days": (today - last).days if last else None,
			"growth_curve": m["growth_curve"], "live": m["live"], "dead": m["dead"], "harvested": m["harvested"],
			"survival_pct": m["survival_pct"], "avg_weight_g": round(m["avg_weight_g"], 1),
			"biomass_kg": round(m["biomass_kg"], 1), "feed_kg": round(m["feed_kg"], 1), "harvest_kg": round(m["harvest_kg"], 1),
			"fcr": m["fcr"], "days_in_water": m["days_in_water"], "growth_g_day": m["growth_g_day"],
			"projected_harvest_date": m["projected_harvest_date"], "projected_weight_g": m["projected_weight_g"],
			"days_to_target": m["days_to_target"], "on_track": m["on_track"],
		})
	growing = [b for b in dicts if not b["closed"]]
	cur = _pooled(growing, today)
	weekly = [(d, _pooled([b for b in growing if getdate(b["start"]) <= d], d)) for d in _week_ends(today)]
	harvested_kg = sum(b["harvest_kg"] for b in dicts)
	kpis = {
		"growing": {"value": len(growing), "series": _series([(d, len([b for b in growing if getdate(b["start"]) <= d])) for d, _ in weekly])},
		"live_fish": {"value": cur["live"], "series": _series([(d, p["live"]) for d, p in weekly])},
		"biomass_kg": {"value": cur["biomass_kg"], "series": _series([(d, p["biomass_kg"]) for d, p in weekly])},
		"fcr": {"value": cur["fcr"], "series": _series([(d, p["fcr"]) for d, p in weekly if p["fcr"] is not None])},
		"survival_pct": {"value": cur["survival_pct"], "series": _series([(d, p["survival_pct"]) for d, p in weekly if p["survival_pct"] is not None])},
		"harvested_kg": {"value": round(harvested_kg, 1), "series": []},
	}
	active = {}
	for b in frappe.get_all("Pond Stocking", filters={"status": "Growing"}, fields=["pond", "name"], limit_page_length=0):
		active[b.pond] = b.name
	return {
		"today": str(today), "batches": batches, "kpis": kpis, "bands": band_logic.get_bands(),
		"sample_stale_days": band_logic.crop_limits(CROP, "sample_stale_days")["sample_stale_days"],
		"form": {
			"ponds": [{"unit": u.name, "label": u.unit_name, "active_stocking": active.get(u.name)} for u in by_unit.values()],
			"species": ["Tilapia", "Catfish"], "statuses": ["Growing", "Harvested", "Closed"],
		},
	}


def _clean(data, fields):
	data = as_dict(data) or {}
	return {k: (data.get(k) if data.get(k) != "" else None) for k in fields if k in data}


def _insert(doctype, data, fields):
	_need(doctype, "create")
	vals = _clean(data, fields)
	doc = frappe.get_doc({"doctype": doctype, **vals})
	doc.insert()
	return doc


STOCKING_FIELDS = ["pond", "species", "stocking_date", "fingerlings_count", "avg_weight_g", "source",
				   "target_harvest_weight_g", "target_harvest_date", "status", "notes"]


@frappe.whitelist(methods=["POST"])
@run
def save_stocking(data):
	"""Stock a pond (new batch), or edit one when `name` is given. One Growing batch per pond."""
	d = as_dict(data)
	if d.get("name"):
		_need("Pond Stocking", "write")
		doc = frappe.get_doc("Pond Stocking", d["name"])
		doc.update(_clean(d, [f for f in STOCKING_FIELDS if f != "pond"]))
		doc.save()
		return {"ok": True, "name": doc.name}
	if not d.get("pond"):
		frappe.throw("Choose the pond.")
	if (d.get("status") or "Growing") == "Growing":
		open_ = frappe.db.get_value("Pond Stocking", {"pond": d["pond"], "status": "Growing"})
		if open_:
			frappe.throw(f"{d['pond']} already has a growing batch ({open_}). Harvest or close it first.")
	doc = _insert("Pond Stocking", d, STOCKING_FIELDS)
	return {"ok": True, "name": doc.name}


@frappe.whitelist(methods=["POST"])
@run
def save_sampling(data):
	"""A weight sample (sample size and average weight) for a batch; `stocking` defaults to the pond's growing one."""
	doc = _insert("Fish Sampling Log", data, ["pond", "stocking", "sample_date", "sample_size", "avg_weight_g"])
	return {"ok": True, "name": doc.name, "stocking": doc.stocking}


@frappe.whitelist(methods=["POST"])
@run
def save_fish_harvest(data):
	"""Record a (partial or final) harvest: a Production Harvest in kg, and the batch's harvested count.

	data: stocking, harvest_date, count, qty_kg, price_per_kg?, final? (marks the batch Harvested).
	"""
	d = as_dict(data)
	_need("Pond Stocking", "write")
	_need("Production Harvest", "create")
	st = frappe.get_doc("Pond Stocking", d.get("stocking"))
	count, kg = cint(d.get("count")), flt(d.get("qty_kg"))
	if count <= 0 or kg <= 0:
		frappe.throw("Enter the number of fish and the kilograms harvested.")
	when = getdate(d.get("harvest_date") or nowdate())
	if when < getdate(st.stocking_date):
		frappe.throw("Harvest date is before the stocking date.")
	b = _stocking_dicts([st])[0]
	live = max(cint(st.fingerlings_count) - cint(st.harvested_count) - sum(cint(n) for _, n in b["deaths"]), 0)
	if count > live:
		frappe.throw(f"Only {live} fish are left in {st.pond}.")
	item = st.species if frappe.db.exists("Item", st.species) else None
	price = _num(d.get("price_per_kg"))
	frappe.get_doc({"doctype": "Production Harvest", "harvest_date": when, "unit": st.pond, "crop": CROP,
					"item": item, "qty": kg, "uom": "Kg", **({"price_per_uom": price} if price else {})}).insert()
	st.harvested_count = cint(st.harvested_count) + count
	st.harvest_date = when
	if d.get("final") or count >= live:
		st.status = "Harvested"
	st.save()
	return {"ok": True, "name": st.name, "status": st.status}


# -- water quality ----------------------------------------------------------------

READING_FIELDS = ["dissolved_oxygen_mg_l", "ph", "temperature_c", "ammonia_mg_l", "nitrite_mg_l", "secchi_cm"]


def _reading_row(r, bands):
	vals = logic.measured_values(r, READING_FIELDS)
	flags = logic.reading_flags(vals, bands)
	return {"name": r.name, "pond": r.pond, "at": str(r.reading_datetime)[:16], **vals, "reader": r.reader,
			"notes": r.notes, "out_of_band": bool(flags), "flags": flags}


@frappe.whitelist(methods=["POST"])
@run
def water_quality(from_date=None, to_date=None, unit=None):
	"""Per pond latest readings against safe bands, alerts and time series for the period."""
	_need("Water Quality Reading")
	start, end = _range(from_date, to_date)
	filters = {"reading_datetime": ("between", [f"{start} 00:00:00", f"{end} 23:59:59"])}
	if unit:
		filters["pond"] = unit
	rows = frappe.get_all("Water Quality Reading", filters=filters, order_by="reading_datetime asc", limit_page_length=0,
		fields=["name", "pond", "reading_datetime", "reader", "notes", "measured", *READING_FIELDS])
	by_pond, pond_bands = {}, {}
	for r in rows:
		if r.pond not in pond_bands:
			pond_bands[r.pond] = logic.bands_for_pond(r.pond)
		by_pond.setdefault(r.pond, []).append(_reading_row(r, pond_bands[r.pond]))
	ponds, alerts = [], []
	for u in _pond_units(unit):
		pond_bands.setdefault(u.name, logic.bands_for_pond(u.name))
		rs = by_pond.get(u.name, [])
		latest = rs[-1] if rs else None
		bad = [r for r in rs if r["out_of_band"]]
		for r in bad:
			for f in r["flags"]:
				alerts.append({"pond": u.name, "pond_name": u.unit_name, "at": r["at"], "metric": f["metric"],
							   "value": f["value"], "message": f["message"]})
		dos = [r["dissolved_oxygen_mg_l"] for r in rs if r["dissolved_oxygen_mg_l"] is not None]
		ponds.append({
			"unit": u.name, "label": u.unit_name, "readings": len(rs), "latest": latest, "bands": pond_bands[u.name],
			"status": "none" if not latest else ("alert" if latest["out_of_band"] else "ok"),
			"out_of_band_count": len(bad), "min_do_mg_l": min(dos) if dos else None,
			"series": [{"at": r["at"], **{k: r[k] for k in READING_FIELDS}, "out_of_band": r["out_of_band"]} for r in rs],
		})
	alerts.sort(key=lambda a: a["at"], reverse=True)
	days = [add_days(start, i) for i in range((end - start).days + 1)]
	def per_day(fn):
		return _series([(d, fn([r for rs in by_pond.values() for r in rs if r["at"][:10] == str(d)])) for d in days])
	def _min_do(rs):
		v = [r["dissolved_oxygen_mg_l"] for r in rs if r["dissolved_oxygen_mg_l"] is not None]
		return min(v) if v else None
	def _avg_t(rs):
		v = [r["temperature_c"] for r in rs if r["temperature_c"] is not None]
		return round(sum(v) / len(v), 1) if v else None
	allr = [r for rs in by_pond.values() for r in rs]
	dos = [r["dissolved_oxygen_mg_l"] for r in allr if r["dissolved_oxygen_mg_l"] is not None]
	ts = [r["temperature_c"] for r in allr if r["temperature_c"] is not None]
	with_latest = [p for p in ponds if p["latest"]]
	def compact(s):
		return [p for p in s if p["value"] is not None]
	return {
		"from_date": str(start), "to_date": str(end), "bands": logic.crop_bands(), "ponds": ponds, "alerts": alerts[:100],
		"readings": [r for r in reversed(allr)][:60],
		"kpis": {
			"ponds_in_band": {"value": len([p for p in with_latest if p["status"] == "ok"]), "of": len(with_latest),
							  "series": []},
			"alerts": {"value": len(alerts), "series": per_day(lambda rs: sum(len(r["flags"]) for r in rs))},
			"lowest_do_mg_l": {"value": min(dos) if dos else None, "series": compact(per_day(_min_do))},
			"avg_temp_c": {"value": round(sum(ts) / len(ts), 1) if ts else None, "series": compact(per_day(_avg_t))},
			"readings": {"value": len(allr), "series": per_day(len)},
		},
		"form": {"ponds": [{"unit": u.name, "label": u.unit_name} for u in _pond_units()], "now": str(now_datetime())[:16]},
	}


@frappe.whitelist(methods=["POST"])
@run
def save_water_reading(data):
	d = as_dict(data)
	if not d.get("reading_datetime"):
		d["reading_datetime"] = str(now_datetime())
	doc = _insert("Water Quality Reading", d, ["pond", "reading_datetime", *READING_FIELDS, "notes"])
	return {"ok": True, "name": doc.name, "out_of_band": bool(doc.out_of_band), "flags": doc.flag_notes or ""}


# -- feeding and mortality ------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
@run
def feeding_mortality(from_date=None, to_date=None, unit=None):
	"""Daily feed and mortality, per-pond totals and the mortality causes for the period."""
	_need("Pond Feeding Log")
	_need("Fish Mortality Log")
	start, end = _range(from_date, to_date, days=28)
	pond_f = {"pond": unit} if unit else {}
	feeds = frappe.get_all("Pond Feeding Log", filters={**pond_f, "feed_date": ("between", [start, end])},
		fields=["name", "pond", "feed_date", "feed_type", "kg_fed", "feeding_times", "times_fed"],
		order_by="feed_date desc, creation desc", limit_page_length=0)
	deaths = frappe.get_all("Fish Mortality Log", filters={**pond_f, "mortality_date": ("between", [start, end])},
		fields=["name", "pond", "mortality_date", "dead_count", "cause", "notes"],
		order_by="mortality_date desc, creation desc", limit_page_length=0)
	days = [add_days(start, i) for i in range((end - start).days + 1)]
	fd, dd = {}, {}
	for r in feeds:
		fd[str(getdate(r.feed_date))] = fd.get(str(getdate(r.feed_date)), 0) + flt(r.kg_fed)
	for r in deaths:
		dd[str(getdate(r.mortality_date))] = dd.get(str(getdate(r.mortality_date)), 0) + cint(r.dead_count)
	daily = [{"date": str(d), "feed_kg": round(fd.get(str(d), 0), 1), "dead": dd.get(str(d), 0)} for d in days]
	live = {}
	for s in frappe.get_all("Pond Stocking", filters={"status": "Growing"},
							fields=["name", "pond", "fingerlings_count", "harvested_count"], limit_page_length=0):
		live[s.pond] = cint(s.fingerlings_count)
	pond_rows = []
	for u in _pond_units(unit):
		pf = sum(flt(r.kg_fed) for r in feeds if r.pond == u.name)
		pd_ = sum(cint(r.dead_count) for r in deaths if r.pond == u.name)
		pond_rows.append({
			"unit": u.name, "label": u.unit_name, "feed_kg": round(pf, 1), "feed_kg_per_day": round(pf / len(days), 1),
			"dead": pd_, "stocked": live.get(u.name), "mortality_pct": round(pd_ / live[u.name] * 100, 2) if live.get(u.name) else None,
			"top_cause": max(((c, sum(cint(r.dead_count) for r in deaths if r.pond == u.name and r.cause == c)) for c in logic.CAUSES),
							 key=lambda x: x[1])[0] if pd_ else None,
		})
	causes = [{"cause": c, "count": sum(cint(r.dead_count) for r in deaths if r.cause == c)} for c in logic.CAUSES]
	causes = [c for c in causes if c["count"]]
	total_feed, total_dead = sum(fd.values()), sum(dd.values())
	def pts(key):
		return _series([(getdate(x["date"]), x[key]) for x in daily])
	return {
		"from_date": str(start), "to_date": str(end), "daily": daily, "ponds": pond_rows, "causes": causes,
		"feed_log": [{**r, "feed_date": str(r.feed_date)} for r in feeds[:60]],
		"mortality_log": [{**r, "mortality_date": str(r.mortality_date)} for r in deaths[:60]],
		"kpis": {
			"feed_kg": {"value": round(total_feed, 1), "series": pts("feed_kg")},
			"feed_kg_per_day": {"value": round(total_feed / len(days), 1), "series": pts("feed_kg")},
			"dead": {"value": total_dead, "series": pts("dead")},
			"worst_pond": {"value": max(pond_rows, key=lambda p: p["dead"])["label"] if total_dead else None,
						   "dead": max((p["dead"] for p in pond_rows), default=0)},
		},
		"form": {
			"ponds": [{"unit": u.name, "label": u.unit_name, "active_stocking": next(iter(frappe.get_all("Pond Stocking", filters={"pond": u.name, "status": "Growing"}, pluck="name", limit_page_length=1)), None)} for u in _pond_units()],
			"causes": logic.CAUSES, "feed_types": _feed_types(), "today": nowdate(),
		},
	}


def _feed_types():
	"""The crop's Production Feed Type rows, in order."""
	return frappe.get_all("Production Feed Type", filters={"parent": CROP, "parenttype": "Production Crop"},
						  pluck="feed_type", order_by="idx asc", limit_page_length=0)


@frappe.whitelist(methods=["POST"])
@run
def save_feeding(data):
	d = as_dict(data)
	d.setdefault("feed_date", nowdate())
	doc = _insert("Pond Feeding Log", d, ["pond", "stocking", "feed_date", "feed_type", "kg_fed", "feeding_times"])
	return {"ok": True, "name": doc.name, "stocking": doc.stocking}


@frappe.whitelist(methods=["POST"])
@run
def save_mortality(data):
	d = as_dict(data)
	d.setdefault("mortality_date", nowdate())
	doc = _insert("Fish Mortality Log", d, ["pond", "stocking", "mortality_date", "dead_count", "cause", "notes"])
	return {"ok": True, "name": doc.name, "stocking": doc.stocking}
