"""JSON endpoints for the avocado forecast pages in the React app.

One endpoint per page (`production_forecast`, `season_outlook`, `harvest_calendar`,
`picking_plan`, `dry_matter`), plus the write actions those pages have. They return
everything the page draws, with units in the field names (`_kg`, `_kes`, `_pct`,
`_ha`, `_t` is never used: tonnes are a display choice, the wire is kilograms).

No forecasting maths lives here. The numbers come from `avocadoapi` (forecast,
projection, schedule, losses), `avocadolabour` (picker rates, crew plan) and
`avocadomaturity` (dry matter entry); this module only selects, joins and ports the
arithmetic that the standalone Jinja pages used to do in the browser (cohorts,
treemap bands, calendar cells, KPI cards, alerts, estimate-vs-delivered scoring).

Every endpoint returns data or `{"error": msg}` (see api/envelope.py).
"""

import json

import frappe
from frappe.utils import add_days, cint, flt, getdate, nowdate

from upande_production.api import avocadoapi, avocadolabour, avocadomaturity
from upande_production.api.envelope import as_dict, run
from upande_production.production.logic.settings import can_see_pay

DEFAULT_PRICE_PER_KG = 95.0
DEFAULT_CREW = 60

READ_ROLES = {"Production Manager", "Production Supervisor", "Production Viewer",
			  "Agriculture Manager", "Agriculture User", "System Manager"}
WRITE_ROLES = {"Production Manager", "Agriculture Manager", "Agriculture User", "System Manager"}

PREF_PRICE = "avocado_price_per_kg"
PREF_CREW = "avocado_crew_available"
PREF_MODE = "avocado_forecast_mode"

# Treemap / map shading: a block's kg per tree as a share of what the estate curve
# expects at its age. `to_pct` is exclusive; `dark_text` says which label colour reads.
VS_CURVE_BANDS = [
	{"to_pct": 75, "color": "#eaf0dc", "dark_text": True},
	{"to_pct": 100, "color": "#cfdcb0", "dark_text": True},
	{"to_pct": 150, "color": "#b6c98a", "dark_text": True},
	{"to_pct": 250, "color": "#6f8f3f", "dark_text": False},
	{"to_pct": None, "color": "#33471a", "dark_text": False},
]
NO_CURVE_BAND = {"color": "#e8e6de", "dark_text": True}


# -- helpers -----------------------------------------------------------------


def _user():
	return frappe.session.user


def _need_read():
	if _user() == "Administrator" or READ_ROLES & set(frappe.get_roles()):
		return
	frappe.throw("You are not permitted to see the avocado forecast.", frappe.PermissionError)


def _need_write():
	if _user() == "Administrator" or WRITE_ROLES & set(frappe.get_roles()):
		return
	frappe.throw("You are not permitted to change avocado records.", frappe.PermissionError)


def _num(v):
	"""A number from whatever the browser sent; None when blank or not a number."""
	if v is None or v == "":
		return None
	try:
		return float(v)
	except (TypeError, ValueError):
		return None


def _price(v):
	n = _num(v)
	if n is not None and n >= 0:
		return n
	saved = _num(frappe.defaults.get_user_default(PREF_PRICE))
	return saved if saved is not None else DEFAULT_PRICE_PER_KG


def _crew(v):
	n = _num(v)
	if n is not None and n >= 0:
		return n
	saved = _num(frappe.defaults.get_user_default(PREF_CREW))
	return saved if saved is not None else float(DEFAULT_CREW)


def _mode(v=None):
	m = (v or frappe.defaults.get_user_default(PREF_MODE) or "manual").lower()
	return "automatic" if m in ("auto", "automatic") else "manual"


def _farm(v):
	return (v or "").strip() or None


def _round(v, n=0):
	return None if v is None else round(flt(v), n)


def _all_farms():
	source = avocadoapi._block_source()
	return sorted({f for f in frappe.get_all(source, pluck="farm", limit_page_length=0) if f})


def _monday(d=None):
	d = getdate(d or nowdate())
	return add_days(d, -d.weekday())


def _tag(d):
	"""ISO week number of a date or date string."""
	return getdate(d).isocalendar()[1]


def _median(vals):
	if not vals:
		return None
	s = sorted(vals)
	return s[len(s) // 2]


def _vs_curve(rows, curve):
	"""Each row's kg/tree as a percentage of its age band's curve, set as `vs_curve_pct`."""
	for r in rows:
		age = r.get("age")
		c = next((c for c in curve if age is not None and c["from"] <= age <= c["to"]), None)
		r["vs_curve_pct"] = (round(r["kg_per_tree"] / c["kg_per_tree"] * 100)
							 if c and c["kg_per_tree"] and r.get("kg_per_tree") else None)


def _band(pct):
	if pct is None:
		return dict(NO_CURVE_BAND, index=None)
	for i, b in enumerate(VS_CURVE_BANDS):
		if b["to_pct"] is None or pct < b["to_pct"]:
			return dict(b, index=i)
	return dict(VS_CURVE_BANDS[-1], index=len(VS_CURVE_BANDS) - 1)


def _context(farm, price):
	"""The forecast every page starts from, plus the lookups they all need."""
	f = avocadoapi.overview(price_per_kg=price, farm=farm)
	rows = f["rows"]
	_vs_curve(rows, f["curve"])
	names = {r["block"] for r in rows}
	projection = {p["block"]: p for p in f["projection"]}
	windows = {w["block"]: w for w in f["windows"]}
	history = [h for h in avocadoapi._history()
			   if (h.get("block_code") or h.get("block")) in names]
	harvests = [h for h in avocadolabour.read_harvests() if h.orchard_block in names]
	return frappe._dict(f=f, rows=rows, names=names, projection=projection,
						windows=windows, history=history, harvests=harvests,
						by_block={r["block"]: r for r in rows})


def _unit_total(kg):
	"""Kilograms as the wire number; pages choose t or kg for display."""
	return round(flt(kg), 0)


# -- Production Forecast ------------------------------------------------------


def _issues_grouped(issues):
	by = {}
	for i in issues:
		by.setdefault(i["issue"], []).append(i)
	return [{"issue": k, "count": len(v), "blocks": [i["block"] for i in v],
			 "detail": v[0]["detail"]} for k, v in by.items()]


def _curve_rows(curve):
	out = []
	for c in curve:
		label = (f"{c['from']}+" if c["to"] >= 90 else
				 str(c["from"]) if c["to"] == c["from"] else f"{c['from']}-{c['to']}")
		out.append({"from_age": c["from"], "to_age": c["to"], "label": label,
					"kg_per_tree": round(c["kg_per_tree"], 1), "basis": c["basis"],
					"harvests": c.get("harvests") or 0, "trees": c.get("trees") or 0})
	return out


def _manual(season, farm, price):
	m = avocadoapi.get_manual_forecast(season=season, price_per_kg=price)
	if farm:
		m["rows"] = [r for r in m["rows"] if r.get("farm") == farm]
		m["blocks"] = m["entries"] = len(m["rows"])
		m["total_kg"] = round(sum(r["expected_kg"] for r in m["rows"]), 0)
		m["live_trees"] = sum(r["live_trees"] for r in m["rows"])
		m["bearing_trees"] = sum(r["bearing_trees"] for r in m["rows"])
		m["pct_bearing"] = (round(m["bearing_trees"] / m["live_trees"] * 100, 1)
							if m["live_trees"] else None)
	return m


def _block_rows(rows, price):
	out = []
	for r in rows:
		if not (r["expected_kg"] > 0 or r["live_trees"] > 0):
			continue
		pct = r.get("pct_bearing")
		out.append({
			"block": r["block"], "farm": r.get("farm"), "variety": r.get("variety"),
			"planting_year": r.get("planting_year"), "age": r.get("age"),
			"live_trees": r["live_trees"], "bearing_trees": r["bearing_trees"],
			"pct_bearing": None if pct is None else min(pct, 100),
			"kg_per_tree": r["kg_per_tree"], "basis": r["basis"],
			"evidence": r.get("evidence"), "expected_kg": r["expected_kg"],
			"value_kes": round(r["expected_kg"] * price, 0) if price else None,
		})
	return out


def _forecast_view(kind, src, price, n_blocks_total, sched_next6, undated_kg, loss, g1_share):
	"""One side of the manual / automatic toggle: totals, KPI cards and block rows."""
	blocks = _block_rows(src["rows"], price)
	ranked = sorted((b for b in blocks if b["expected_kg"] > 0), key=lambda b: -b["expected_kg"])
	total = flt(src["total_kg"])
	bearing, live = flt(src["bearing_trees"]), flt(src["live_trees"])
	g1_kg = round(total * g1_share, 0) if g1_share else None
	counted = sum(1 for r in src["rows"] if str(r.get("basis", "")).startswith("counted"))
	cards = [
		{"key": "forecast", "label": "Forecast", "value": _unit_total(total), "unit": "kg",
		 "hint": ("manually entered" if kind == "manual" else "calculated")
				 + ", whole estate, this season"},
		{"key": "grade_1", "label": "Grade 1", "value": g1_kg, "unit": "kg",
		 "hint": (f"{g1_share * 100:.0f}% of packed weight, from what was packed" if g1_share
				  else "no harvest packed yet")},
		{"key": "value", "label": "Value", "value": round(total * price, 0) if price else None,
		 "unit": "KES", "hint": f"at {price:,.0f} / kg"},
		{"key": "bearing", "label": "Bearing", "value": src.get("pct_bearing") or 0, "unit": "%",
		 "hint": f"{bearing:,.0f} of {live:,.0f} trees"},
	]
	if kind == "manual":
		cards.append({"key": "manual_entries", "label": "Manual entries",
					  "value": src["blocks"], "of": n_blocks_total, "unit": "blocks",
					  "hint": (f"of {n_blocks_total} orchard blocks have a typed forecast"
							   if src["blocks"] else "no manual forecasts entered yet")})
	else:
		cards.append({"key": "counted_blocks", "label": "Counted blocks", "value": counted,
					  "of": src["blocks"], "unit": "blocks",
					  "hint": ("forecast from fruit on the tree" if counted
							   else "no fruit counts yet, all on the curve")})
	cards += [
		{"key": "next_6_weeks", "label": "Next 6 weeks", "value": sched_next6, "unit": "kg",
		 "hint": (f"{undated_kg:,.0f} kg has no pick date yet" if undated_kg
				  else "every forecast block is dated")},
		{"key": "losing", "label": "Losing", "value": loss["lost_kg"] or None, "unit": "kg",
		 "lost_kes": loss["lost_value_kes"],
		 "hint": ("sick trees and gaps" if loss["lost_kg"] else "no sick trees or gaps recorded")},
	]
	return {
		"kind": kind, "total_kg": _unit_total(total),
		"total_value_kes": round(total * price, 0) if price else None,
		"blocks": src["blocks"], "live_trees": live, "bearing_trees": bearing,
		"pct_bearing": src.get("pct_bearing"), "grade_1_share": g1_share, "grade_1_kg": g1_kg,
		"counted_blocks": counted if kind == "automatic" else None,
		"manual_entries": src["blocks"] if kind == "manual" else None,
		"cards": cards, "block_rows": blocks, "top_blocks": ranked[:12],
		"forecasting_blocks": len(ranked),
	}


def _vs_budget(budget, forecast_kg, delivered_kg, whole_season):
	"""The budget is for the whole season, so the comparison is the season outturn:
	what is already delivered plus what is still forecast on the trees. A typed
	(manual) forecast is already whole-season, so it is compared as it stands."""
	if not budget.get("set"):
		return None
	bkg = flt(budget["budget_kg"])
	delivered = 0.0 if whole_season else flt(delivered_kg)
	outturn = delivered + forecast_kg
	return {"forecast_kg": _unit_total(forecast_kg), "delivered_kg": _unit_total(delivered),
			"on_trees_kg": _unit_total(forecast_kg), "outturn_kg": _unit_total(outturn),
			"basis": "typed whole-season forecast" if whole_season else "delivered + still on the trees",
			"diff_kg": round(outturn - bkg, 0),
			"pct_of_budget": round(outturn / bkg * 100, 1) if bkg > 0 else None}


def _month_name(d):
	return getdate(d).strftime("%B")


def _budget_months_actual(budget, ctx, season, sched_weeks):
	"""Delivered kilograms per budget month (harvest logs) and the forecast still to come."""
	if not budget.get("set"):
		return budget
	got, ahead = {}, {}
	for h in ctx.harvests:
		# Same rule as the picking plan's refused records: a row whose implied rate is not
		# one day's picking is a mis-keyed record, not a delivery.
		pk = flt(h.get("pickers_count"))
		if pk and not (avocadolabour.PLAUSIBLE_RATE[0] <= flt(h.get("total_kg")) / pk <= avocadolabour.PLAUSIBLE_RATE[1]):
			continue
		if h.harvest_date and getdate(h.harvest_date).year == cint(season):
			m = _month_name(h.harvest_date)
			got[m] = got.get(m, 0.0) + flt(h.total_kg)
	for w in sched_weeks:
		if getdate(w["week"]).year == cint(season):
			m = _month_name(w["week"])
			ahead[m] = ahead.get(m, 0.0) + flt(w["kg"])
	for m in budget["months"]:
		m["delivered_kg"] = round(got.get(m["month"], 0.0), 0)
		m["forecast_kg"] = round(ahead.get(m["month"], 0.0), 0)
	return budget


def _budget_view(budget):
	if not budget.get("set"):
		return {"set": False, "season": budget["season"], "crop": budget["crop"], "months": []}
	months = budget.get("months") or []
	peak = max([m["budget_kg"] for m in months] + [1])
	out = dict(budget)
	out["months"] = [dict(m, share_of_peak_pct=round(m["budget_kg"] / peak * 100, 1))
					 for m in months]
	out["months_total_kg"] = round(sum(m["budget_kg"] for m in months), 0)
	return out


def _score_early(ctx, season):
	"""Per-block estimate (typed Early forecasts) against delivered kilograms this season."""
	names = ctx.names
	est = {}
	for e in frappe.get_all(avocadoapi.MANUAL_FORECAST_DOCTYPE,
							filters={"season": season, "crop": "Early"},
							fields=["orchard_block", "expected_kg"],
							order_by="entry_date desc, creation desc", limit_page_length=0):
		if e.orchard_block in names and e.orchard_block not in est:
			est[e.orchard_block] = flt(e.expected_kg)
	act = {}
	for h in ctx.history:
		if (cint(h.get("year")) == cint(season)
				and str(h.get("season_part") or "Year") in ("Year", "Early")
				and flt(h.get("kg_harvested")) > 0):
			b = h.get("block_code") or h.get("block")
			act[b] = act.get(b, 0.0) + flt(h["kg_harvested"])
	rows = []
	for b in sorted(set(est) | set(act)):
		meta = ctx.by_block.get(b, {})
		e, a = est.get(b, 0.0), act.get(b, 0.0)
		rows.append({"block": b, "farm": meta.get("farm"),
					 "planting_year": meta.get("planting_year"),
					 "estimated_kg": round(e, 0), "delivered_kg": round(a, 0),
					 "pct_of_estimate": round(a / e * 100, 1) if e > 0 and a > 0 else None})
	return rows


def _estimate_vs_delivered(ctx, season):
	f = ctx.f
	cal, delivered = f["calibration"], f["delivered"]
	rows = _score_early(ctx, season)
	has_block = any(r["delivered_kg"] > 0 for r in rows)
	out = {"season": season, "crop": delivered.get("crop") or "Early"}
	if has_block:
		est = sum(r["estimated_kg"] for r in rows)
		act = sum(r["delivered_kg"] for r in rows)
		scored = sorted((r for r in rows if r["pct_of_estimate"] is not None),
						key=lambda r: -r["pct_of_estimate"])
		best = scored[0] if scored else None
		worst = scored[-1] if len(scored) > 1 else None
		out.update({
			"basis": "block", "estimated_kg": round(est, 0), "delivered_kg": round(act, 0),
			"diff_kg": round(act - est, 0),
			"diff_pct": round((act - est) / est * 100, 1) if est > 0 else None,
			"performance_pct": round(act / est * 100, 1) if est > 0 else None,
			"blocks_estimated": sum(1 for r in rows if r["estimated_kg"] > 0),
			"blocks_delivered": sum(1 for r in rows if r["delivered_kg"] > 0),
			"best": best, "weakest": worst,
			"waiting": [{"block": r["block"], "estimated_kg": r["estimated_kg"]}
						for r in rows if r["estimated_kg"] > 0 and r["delivered_kg"] <= 0],
			"note": None, "rows": rows,
		})
	elif delivered["kg"] > 0 and cal["actual_kg"] > 0 and not ctx.history:
		# Whole-estate closed-season totals: nothing per block to score.
		est, act = cal["estimated_kg"], cal["actual_kg"]
		out.update({
			"basis": "estate", "estimated_kg": round(est, 0), "delivered_kg": round(act, 0),
			"diff_kg": round(act - est, 0),
			"diff_pct": round((act - est) / est * 100, 1) if est > 0 else None,
			"performance_pct": round(act / est * 100, 1) if est > 0 else None,
			"blocks_estimated": cal["blocks_estimated"], "blocks_delivered": cal["blocks_harvested"],
			"best": None, "weakest": None, "waiting": [], "rows": [],
			"note": "Whole-estate totals. No block can be scored.",
		})
	else:
		out.update({
			"basis": "none", "estimated_kg": round(sum(r["estimated_kg"] for r in rows), 0),
			"delivered_kg": round(flt(delivered["kg"]), 0), "diff_kg": None, "diff_pct": None,
			"performance_pct": None, "blocks_estimated": sum(1 for r in rows if r["estimated_kg"] > 0),
			"blocks_delivered": 0, "best": None, "weakest": None, "waiting": [], "rows": rows,
			"note": "No harvest has been recorded against these estimates yet.",
		})
	return out


def _by_planting_year(rows):
	"""The same comparison grouped by planting year (blocks with a harvest only)."""
	if not any(r["delivered_kg"] > 0 for r in rows):
		return []
	by = {}
	for r in rows:
		k = r["planting_year"] or None
		e = by.setdefault(k, {"planting_year": k, "blocks": 0, "blocks_picked": 0,
							  "estimated_kg": 0.0, "delivered_kg": 0.0})
		e["blocks"] += 1
		e["estimated_kg"] += r["estimated_kg"]
		e["delivered_kg"] += r["delivered_kg"]
		if r["delivered_kg"] > 0:
			e["blocks_picked"] += 1
	out = sorted(by.values(), key=lambda e: (e["planting_year"] is None, e["planting_year"] or 0))
	for e in out:
		e["pct_of_estimate"] = (round(e["delivered_kg"] / e["estimated_kg"] * 100, 1)
								if e["estimated_kg"] > 0 and e["delivered_kg"] > 0 else None)
		e["estimated_kg"], e["delivered_kg"] = round(e["estimated_kg"], 0), round(e["delivered_kg"], 0)
	best = max([e["pct_of_estimate"] or 0 for e in out] + [100])
	for e in out:
		e["vs_best_year_pct"] = (round(e["pct_of_estimate"] / best * 100, 1)
								 if e["pct_of_estimate"] is not None else None)
	return out


def _schedule_view(sched, price):
	peak = max(sched["kg"] + [1])
	return {
		"weeks": [{"week": w, "iso_week": _tag(w), "kg": kg,
				   "share_of_peak_pct": round(kg / peak * 100, 1),
				   "value_kes": round(kg * price, 0) if price else None}
				  for w, kg in zip(sched["weeks"], sched["kg"])],
		"scheduled_kg": sched["scheduled_kg"], "unscheduled": sched["unscheduled"],
		"unscheduled_kg": sched["unscheduled_kg"], "pick_weeks": sched["pick_weeks"],
		"scheduled_blocks": sched["scheduled"], "kg_by_basis": sched["kg_by_basis"],
		"blocks_by_basis": sched["blocks_by_basis"],
		"next_6_weeks_kg": round(sum(sched["kg"][:6]), 0),
	}


def _loss_view(loss, price):
	rows = [dict(r, lost_value_kes=r.get("lost_value")) for r in loss["rows"]]
	return {"rows": rows, "lost_kg": loss["lost_kg"],
			"lost_value_kes": round(loss["lost_kg"] * price, 0) if price else None}


def _maturity_view(m):
	return {"minimum_pct": m["minimum_pct"], "sampled": m["sampled"],
			"blocks": [{"block": b["block"], "sample_date": b["sample_date"],
						"dry_matter_pct": b["dry_matter_pct"], "shortfall_pct": b["shortfall_pct"],
						"ready": b["ready"]} for b in m["blocks"]]}


@frappe.whitelist(methods=["POST"])
@run
def production_forecast(farm=None, season=None, price_per_kg=None, mode=None):
	"""Production Forecast page (teddy's /avocado-production).

	Both sides of the manual/automatic toggle are returned (`views.manual`,
	`views.automatic`) so switching never refetches; `mode` is the saved choice.
	Quantities in kg, money in KES. The automatic forecast is always for the crop on
	the trees today; `season` selects which season's typed forecast and budget show.
	"""
	_need_read()
	farm, price = _farm(farm), _price(price_per_kg)
	ctx = _context(farm, price)
	f = ctx.f
	season = cint(season) or f["season"]
	manual = _manual(season, farm, price)
	budget = _budget_view(avocadoapi.get_manual_budget(season=season))
	sched = _schedule_view(f["schedule"], price)
	loss = _loss_view(f["losses"], price)
	n_blocks = f["blocks"]
	views = {
		"automatic": _forecast_view("automatic", f, price, n_blocks, sched["next_6_weeks_kg"],
									sched["unscheduled_kg"], loss, f["grade_1_share"]),
		# The typed forecast has no packed-weight split behind it, so no Grade 1.
		"manual": _forecast_view("manual", manual, price, n_blocks, sched["next_6_weeks_kg"],
								 sched["unscheduled_kg"], loss, None),
	}
	delivered_kg = f["delivered"]["kg"] if season == f["season"] else 0
	for k, v in views.items():
		v["vs_budget"] = _vs_budget(budget, v["total_kg"], delivered_kg, k == "manual")
	_budget_months_actual(budget, ctx, season, sched["weeks"])
	score = _estimate_vs_delivered(ctx, season)
	by_year = _by_planting_year(score["rows"])
	return {
		"farm": farm, "farms": _all_farms(), "season": season,
		"seasons": sorted({season, f["season"]} | {cint(h.get("year")) for h in ctx.history if h.get("year")}),
		"crop": f["crop"], "price_per_kg": price, "mode": _mode(mode),
		"header": {
			"blocks": n_blocks, "live_trees": f["live_trees"], "bearing_trees": f["bearing_trees"],
			"pct_bearing": f["pct_bearing"], "biennial_factor": f["biennial_factor"],
			"on_year": f["biennial_factor"] >= 1,
		},
		"views": views,
		"manual_note": {"entries": manual["entries"], "blocks_total": n_blocks},
		"budget": budget,
		"estimate_vs_delivered": score,
		"by_planting_year": by_year,
		"yield_curve": _curve_rows(f["curve"]),
		"schedule": sched,
		"losses": loss,
		"maturity": _maturity_view(f["maturity"]),
		"data_gaps": _issues_grouped(f["issues"]),
		"calibration": f["calibration"],
		"delivered": f["delivered"],
		"units": {"weight": "kg", "money": "KES", "price": "KES per kg", "age": "years"},
	}


# -- Season Outlook ------------------------------------------------------------


def _cohorts(ctx, minimum):
	"""Planting cohorts: blocks of one age ripen together, the unit the packhouse plans by."""
	cm = {}
	for r in ctx.rows:
		p = ctx.projection.get(r["block"])
		if not p:
			continue
		k = r.get("planting_year") or 0
		c = cm.setdefault(k, {"planting_year": k or None, "blocks_n": 0, "expected_kg": 0.0,
							  "dm": 0.0, "gain": 0.0, "stale_blocks": 0, "blocks": [],
							  "weeks": [], "opens": []})
		c["blocks_n"] += 1
		c["expected_kg"] += r["expected_kg"] or 0
		c["dm"] += p["dry_matter_pct"] or 0
		c["gain"] += p["gain_per_week"] or 0
		c["blocks"].append(r["block"])
		if p["stale"]:
			c["stale_blocks"] += 1
		if p["weeks_to_minimum"] is not None:
			c["weeks"].append(p["weeks_to_minimum"])
		if p["ready_date"]:
			c["opens"].append(p["ready_date"])
	out = []
	for c in cm.values():
		n = c["blocks_n"]
		dm = c["dm"] / n
		opens = sorted(c["opens"])
		out.append({
			"planting_year": c["planting_year"], "blocks_n": n, "blocks": c["blocks"],
			"expected_kg": round(c["expected_kg"], 0), "dry_matter_pct": round(dm, 1),
			"gain_pct_per_week": round(c["gain"] / n, 2),
			"weeks_to_minimum": _median(c["weeks"]), "open_date": opens[0] if opens else None,
			"short_pct": round(max(0.0, minimum - dm), 1), "stale_blocks": c["stale_blocks"],
		})
	out.sort(key=lambda c: -c["dry_matter_pct"])
	return out


def _picked_by_week(ctx, season):
	by = {}
	for h in ctx.harvests:
		# mis-keyed logs (several days in one row) are not picks: same rule as the labour plan
		if h.harvest_date and getdate(h.harvest_date).year == cint(season) and avocadolabour.is_plausible(h):
			w = str(_monday(h.harvest_date))
			by[w] = by.get(w, 0.0) + flt(h.total_kg)
	return by


def _timeline(ctx, season, cohorts, minimum):
	f = ctx.f
	sched = f["schedule"]
	forecast = dict(zip(sched["weeks"], sched["kg"]))
	picked = _picked_by_week(ctx, season)
	keys = sorted(set(forecast) | set(picked))
	weeks = []
	today_week = str(_monday())
	if keys:
		w, end = getdate(keys[0]), getdate(keys[-1])
		while w <= end:
			s = str(w)
			weeks.append({"week": s, "iso_week": _tag(w), "picked_kg": round(picked.get(s, 0.0), 0),
						  "forecast_kg": round(forecast.get(s, 0.0), 0), "is_past": s < today_week})
			w = add_days(w, 7)
	fc = [x["forecast_kg"] for x in weeks]
	peak = max(range(len(weeks)), key=lambda i: fc[i]) if weeks and max(fc) else None
	return {
		"weeks": weeks, "today_week": today_week,
		"scheduled_kg": sched["scheduled_kg"], "unscheduled_kg": sched["unscheduled_kg"],
		"picked_kg": round(sum(picked.values()), 0),
		"peak": ({"week": weeks[peak]["week"], "kg": weeks[peak]["forecast_kg"]}
				 if peak is not None else None),
		"calibration_factor": f["calibration"]["factor"],
		"calibration_basis": f["calibration"]["basis"],
		"crossings": [{"planting_year": c["planting_year"], "open_date": c["open_date"],
					   "week": str(_monday(c["open_date"])), "blocks_n": c["blocks_n"],
					   "expected_kg": c["expected_kg"]}
					  for c in cohorts if c["open_date"]],
		"minimum_pct": minimum,
	}


def _map(ctx):
	"""Surveyed block boundaries, joined to the forecast. Boundaries are optional."""
	source = avocadoapi._block_source()
	meta = frappe.get_all(source, fields=["name", "block_code", "farm", "area_ha", "centroid_lat",
										  "centroid_lon", "mapped_area_m2", "geojson"],
						  limit_page_length=0)
	blocks, missing = [], 0
	for b in meta:
		if b["name"] not in ctx.names:
			continue
		geo = None
		try:
			geo = json.loads(b["geojson"]) if b.get("geojson") else None
		except Exception:
			geo = None
		if not geo:
			missing += 1
			continue
		r = ctx.by_block.get(b["name"], {})
		surveyed = flt(b.get("mapped_area_m2")) / 10000.0
		gap = None
		if surveyed and flt(b.get("area_ha")):
			ratio = surveyed / flt(b["area_ha"])
			if ratio > 1.25 or ratio < 0.75:
				gap = {"surveyed_ha": round(surveyed, 2), "paper_ha": flt(b["area_ha"]),
					   "ratio": round(ratio, 2)}
		vs = r.get("vs_curve_pct")
		blocks.append({
			"block": b["name"], "code": b.get("block_code") or b["name"], "geojson": geo,
			"centroid_lat": b.get("centroid_lat") or None, "centroid_lon": b.get("centroid_lon") or None,
			"area_gap": gap, "expected_kg": r.get("expected_kg") or 0, "vs_curve_pct": vs,
			"band": _band(vs), "farm": r.get("farm") or b.get("farm"), "basis": r.get("basis"),
		})
	return {"blocks": blocks, "surveyed": len(blocks), "without_boundary": missing,
			"area_disagrees": sum(1 for b in blocks if b["area_gap"])}


def _treemap(ctx):
	blocks = sorted((r for r in ctx.rows if (r["expected_kg"] or 0) > 0),
					key=lambda r: -r["expected_kg"])
	return {
		"bands": VS_CURVE_BANDS,
		"blocks": [{
			"block": r["block"], "farm": r.get("farm"), "expected_kg": r["expected_kg"],
			"value_kes": r.get("value"), "vs_curve_pct": r.get("vs_curve_pct"),
			"band": _band(r.get("vs_curve_pct")), "age": r.get("age"), "basis": r["basis"],
			"bearing_trees": r["bearing_trees"], "live_trees": r["live_trees"],
			"planting_year": r.get("planting_year"),
		} for r in blocks],
		"with_crop": len(blocks), "without_crop": len(ctx.rows) - len(blocks),
	}


def _pickers(ctx, crew, days_per_week=5):
	f = ctx.f
	plan = avocadolabour.build_plan(ctx.rows, ctx.projection, ctx.windows, ctx.harvests,
									crew_available=crew, days_per_week=days_per_week, pay_per_day=0)
	rows = plan["rows"]
	this_mon = str(_monday())
	nxt = next((r for r in rows if r["week"] >= this_mon), None)
	return plan, {
		"crew_available": crew, "days_per_week": plan["days_per_week"], "rows": rows,
		"summary": plan["summary"], "next_week": nxt,
		"weeks_short": plan["summary"].get("short_weeks", 0),
	}


@frappe.whitelist(methods=["POST"])
@run
def season_outlook(farm=None, price_per_kg=None, crew_available=None):
	"""Season Outlook page (teddy's /avocado-outlook). kg / KES / pickers."""
	_need_read()
	farm, price, crew = _farm(farm), _price(price_per_kg), _crew(crew_available)
	ctx = _context(farm, price)
	f, rows = ctx.f, ctx.rows
	minimum = f["maturity"]["minimum_pct"]
	proj = f["projection"]
	cal = f["calibration"]
	season = f["season"]

	stale = [p for p in proj if p["stale"]]
	oldest = max([p["sample_age_weeks"] or 0 for p in proj] + [0])
	ready_now = [p for p in proj if p["ready"] and not p["stale"]]
	ready_kg = sum((ctx.by_block.get(p["block"]) or {}).get("expected_kg", 0) or 0 for p in ready_now)
	cohorts = _cohorts(ctx, minimum)
	timeline = _timeline(ctx, season, cohorts, minimum)
	plan, pickers = _pickers(ctx, crew)
	nxt = pickers["next_week"]
	delivered_season = round(sum(flt(h.get("kg_harvested")) for h in ctx.history
								 if cint(h.get("year")) == season), 0)
	by_year = {}
	for h in ctx.history:
		y = cint(h.get("year"))
		if y > 0:
			e = by_year.setdefault(y, {"year": y, "kg": 0.0, "blocks": set()})
			e["kg"] += flt(h.get("kg_harvested"))
			e["blocks"].add(h.get("block_code") or h.get("block"))
	delivered_by_season = [{"year": y, "kg": round(e["kg"], 0), "blocks": len(e["blocks"]),
							"on_year": avocadoapi.biennial_factor(y) == 1.0}
						   for y, e in sorted(by_year.items())]
	acc = round(100 - abs(cal["factor"] - 1) * 100, 1) if cal["factor"] else None
	cum, series = 0.0, []
	for r in rows:
		cum += r.get("value") or r["expected_kg"] or 0
		series.append(round(cum, 0))
	n_proj = len(proj)
	need = round(nxt["pickers_needed"]) if nxt else None
	sched = f["schedule"]
	kpis = [
		{"key": "season_crop", "label": "Season crop", "value": _unit_total(f["total_kg"]), "unit": "kg",
		 "note": (f"{delivered_season:,.0f} kg delivered" if delivered_season else "none delivered yet"),
		 "delivered_kg": delivered_season, "calibration_factor": cal["factor"],
		 "meter_pct": round(delivered_season / f["total_kg"] * 100, 1) if f["total_kg"] else 0},
		{"key": "crop_value", "label": "Crop value", "value": f["total_value"], "unit": "KES",
		 "note": f"at KES {price:,.0f} / kg", "series": series},
		{"key": "ready_to_pick", "label": "Ready to pick", "value": len(ready_now), "unit": "blocks",
		 "note": (f"{ready_kg:,.0f} kg at the floor" if ready_now else f"{len(stale)} readings stale"),
		 "ready_kg": ready_kg, "meter_pct": round(len(ready_now) / n_proj * 100, 1) if n_proj else 0},
		{"key": "crew_next_week", "label": "Crew next week", "value": need, "unit": "pickers",
		 "note": (f"{crew:,.0f} available" if need is not None else "no week dated yet"),
		 "crew_available": crew, "week": nxt["week"] if nxt else None,
		 "short": bool(need is not None and need > crew),
		 "meter_pct": (0 if need is None else round(need / crew * 100, 1) if crew else 100)},
		{"key": "estimate_accuracy", "label": "Estimate accuracy", "value": acc, "unit": "%",
		 "note": cal["basis"] or "not calibrated", "estimated_kg": cal["estimated_kg"],
		 "actual_kg": cal["actual_kg"], "calibration_factor": cal["factor"],
		 "meter_pct": acc or 0},
		{"key": "stale_readings", "label": "Stale readings", "value": len(stale), "of": n_proj,
		 "unit": "readings",
		 "note": (f"{round(oldest)} weeks old" if stale else
				  "every reading current" if n_proj else "no samples on file"),
		 "meter_pct": round(len(stale) / n_proj * 100, 1) if n_proj else 0},
	]

	loss = _loss_view(f["losses"], price)
	undated = {
		"kg": sched["unscheduled_kg"], "blocks": sched["unscheduled"],
		"stale_blocks": [{"block": p["block"], "sample_date": p["sample_date"],
						  "sample_age_weeks": p["sample_age_weeks"], "needs": p["needs"]}
						 for p in stale],
	}
	alerts = _alerts(rows, plan, stale, oldest, sched, loss, f["issues"])
	return {
		"farm": farm, "farms": _all_farms(), "season": season, "price_per_kg": price,
		"crew_available": crew, "crop": f["crop"],
		"header": {"blocks": f["blocks"], "total_kg": _unit_total(f["total_kg"]),
				   "stale_readings": len(stale), "weeks_dated": len(timeline["weeks"]),
				   "biennial_factor": f["biennial_factor"], "on_year": f["biennial_factor"] >= 1,
				   "evidence_split": f["evidence_split"]},
		"kpis": kpis, "timeline": timeline, "map": _map(ctx), "treemap": _treemap(ctx),
		"dry_matter": {"minimum_pct": minimum, "cohorts": cohorts,
					   "blocks": [{"block": p["block"], "dry_matter_pct": p["dry_matter_pct"],
								   "sample_date": p["sample_date"], "samples": p["samples"],
								   "gain_pct_per_week": p["gain_per_week"],
								   "weeks_to_minimum": p["weeks_to_minimum"],
								   "ready_date": p["ready_date"], "ready": p["ready"],
								   "stale": p["stale"]} for p in proj]},
		"pickers": pickers, "losses": loss, "undated": undated, "alerts": alerts,
		"delivered_by_season": delivered_by_season, "calibration": cal,
		"units": {"weight": "kg", "money": "KES", "pickers": "people"},
	}


def _alerts(rows, plan, stale, oldest, sched, loss, issues):
	"""Only what is actually wrong, five at most, worst first."""
	a = []
	s = plan["summary"]
	if s.get("short_weeks"):
		a.append({"weight": 10, "kind": "neg", "key": "crew_short", "count": s["short_weeks"],
				  "label": "weeks short of crew",
				  "detail": f"{round(s['worst_shortfall'])} pickers short at worst",
				  "first_week": s.get("first_short_week")})
	if stale:
		a.append({"weight": 9, "kind": "warn", "key": "stale", "count": len(stale),
				  "label": "readings stale",
				  "detail": f"{round(oldest)} weeks old, no block can be dated from them"})
	if sched["unscheduled_kg"]:
		a.append({"weight": 8, "kind": "warn", "key": "undated", "count": len(sched["unscheduled"]),
				  "kg": sched["unscheduled_kg"], "label": "blocks with no pick date",
				  "detail": f"{sched['unscheduled_kg']:,.0f} kg undated"})
	if loss["lost_kg"]:
		a.append({"weight": 7, "kind": "neg", "key": "losses", "count": len(loss["rows"]),
				  "kg": loss["lost_kg"], "label": "blocks losing fruit to sick trees and gaps",
				  "detail": f"{loss['lost_kg']:,.0f} kg" + (
					  f", KES {loss['lost_value_kes']:,.0f}" if loss["lost_value_kes"] else "")})
	uncounted = sum(1 for r in rows if (r["expected_kg"] or 0) > 0
					and not str(r.get("basis") or "").startswith("counted"))
	if uncounted:
		a.append({"weight": 5, "kind": "", "key": "uncounted", "count": uncounted,
				  "label": "blocks never counted", "detail": "sized off the estate curve, not off the tree"})
	nocrop = sum(1 for r in rows if not (r["expected_kg"] or 0))
	if nocrop:
		a.append({"weight": 4, "kind": "", "key": "no_crop", "count": nocrop,
				  "label": "blocks with no crop",
				  "detail": "not bearing yet, or no planting year on record"})
	if issues:
		a.append({"weight": 3, "kind": "", "key": "records", "count": len(issues),
				  "label": "records disagree",
				  "detail": ", ".join(i["block"] for i in issues[:3])})
	a.sort(key=lambda x: -x["weight"])
	return a[:5]


# -- Harvest Calendar -----------------------------------------------------------


def _cohort_notes(rows, projection):
	"""A reading shared by several blocks is a planting-year reading, not the block's own."""
	by_reading, notes = {}, {}
	for b, p in projection.items():
		by_reading.setdefault((p["sample_date"], round(p["dry_matter_pct"], 2)), []).append(b)
	year_of = {r["block"]: r.get("planting_year") for r in rows}
	for blocks in by_reading.values():
		if len(blocks) < 2:
			continue
		years = {year_of[b] for b in blocks if year_of.get(b)}
		note = (f"{next(iter(years))} planting, not this block" if len(years) == 1
				else f"shared by {len(blocks)} blocks, not this block")
		for b in blocks:
			notes[b] = note
	return notes


def _shade(kg, mx):
	if not kg or not mx:
		return 0
	f = kg / mx
	return 5 if f > 0.8 else 4 if f > 0.6 else 3 if f > 0.4 else 2 if f > 0.2 else 1


def _calendar_blocks(ctx):
	"""Every forecasting block placed in weeks (own dry matter first, last season's window next)."""
	notes = _cohort_notes(ctx.rows, ctx.projection)
	blocks, young = [], []
	for r in ctx.rows:
		kg = flt(r["expected_kg"])
		if not kg:
			young.append(r)
			continue
		p = ctx.projection.get(r["block"])
		w = ctx.windows.get(r["block"])
		one = avocadoapi.weekly_spread([r], ctx.projection, windows=ctx.windows)
		placed = one["scheduled"][0] if one["scheduled"] else None
		b = {"block": r["block"], "farm": r.get("farm") or "", "planting_year": r.get("planting_year"),
			 "expected_kg": kg, "cohort_note": notes.get(r["block"], ""),
			 "dry_matter_pct": p["dry_matter_pct"] if p else None,
			 "dm_basis": p["gain_basis"] if p else "", "samples": p["samples"] if p else 0,
			 "ready_date": p["ready_date"] if p else None,
			 "weeks_to_go": p["weeks_to_minimum"] if p else None,
			 "stale": bool(p and p["stale"]),
			 "start": placed["start"] if placed else None, "placed_on": placed["measured_on"] if placed else None,
			 "placed_basis": placed["basis"] if placed else None,
			 "cells": dict(zip(one["weeks"], one["kg"]))}
		if placed and placed["measured_on"] == "dry matter":
			b["state"] = "ready" if p["ready"] else "waiting"
		elif placed:
			b["state"] = "last_season"
		elif p:
			b["state"] = "nodate"
		else:
			b["state"] = "unsampled"
		blocks.append(b)
	order = {"ready": 0, "waiting": 0, "last_season": 1, "nodate": 2, "unsampled": 3}
	blocks.sort(key=lambda b: (order[b["state"]], b["start"] or "9", -b["expected_kg"]))
	return blocks, young


@frappe.whitelist(methods=["POST"])
@run
def harvest_calendar(farm=None, planting_year=None):
	"""Harvest Calendar page: block x week grid, KPIs and the two lists under it.

	`farm` and `planting_year` filter the grid, KPIs and lists. `filters` always lists
	every option so the pickers do not shrink as you filter. A week is a Monday.
	kg_per_crate is 18; every cell and total carries kg and crates.
	"""
	_need_read()
	farm = _farm(farm)
	year = cint(planting_year) or None
	ctx = _context(None, 0)
	minimum = ctx.f["maturity"]["minimum_pct"]
	all_blocks, all_young = _calendar_blocks(ctx)
	kpc = avocadolabour.KG_PER_CRATE
	filters = {"farms": sorted({b["farm"] for b in all_blocks + all_young if b.get("farm")}),
			   "planting_years": sorted({cint(b.get("planting_year")) for b in all_blocks + all_young
										 if b.get("planting_year")})}

	def keep(b):
		return ((not farm or (b.get("farm") or "") == farm)
				and (not year or cint(b.get("planting_year")) == year))

	blocks = [b for b in all_blocks if keep(b)]
	young = [r for r in all_young if keep(r)]
	weeks = sorted({w for b in blocks for w in b["cells"]})
	col_kg = [sum(b["cells"].get(w, 0.0) for b in blocks) for w in weeks]
	total_kg = sum(col_kg)
	max_cell = max([kg for b in blocks for kg in b["cells"].values()] + [0])
	peak = max(range(len(weeks)), key=lambda i: col_kg[i]) if weeks and total_kg else None

	grid = []
	for b in blocks:
		cells = []
		for w in weeks:
			kg = b["cells"].get(w, 0.0)
			if kg:
				kind = "fill"
			elif b["state"] in ("unsampled", "nodate"):
				kind = "no_sample"
			elif b["state"] == "waiting" and b["start"] and w < b["start"]:
				kind = "locked"
			else:
				kind = "empty"
			cells.append({"week": w, "kind": kind, "kg": round(kg, 0), "crates": round(kg / kpc),
						  "shade": _shade(kg, max_cell)})
		row_kg = sum(b["cells"].values())
		out = {k: v for k, v in b.items() if k != "cells"}
		out.update({"cells": cells, "row_kg": round(row_kg, 0), "row_crates": round(row_kg / kpc),
					"has_date": bool(row_kg)})
		grid.append(out)

	ready_now = [b for b in blocks if b["state"] == "ready"]
	no_date = [b for b in blocks if b["state"] in ("unsampled", "nodate")]
	no_date_kg = sum(b["expected_kg"] for b in no_date)
	return {
		"filters": filters, "selected": {"farm": farm, "planting_year": year},
		"minimum_pct": minimum, "kg_per_crate": kpc, "pick_weeks": ctx.f["schedule"]["pick_weeks"],
		"summary": {"blocks": len(blocks), "weeks": len(weeks), "total_kg": round(total_kg, 0),
					"total_crates": round(total_kg / kpc)},
		"kpis": {
			"peak_week": ({"week": weeks[peak], "iso_week": _tag(weeks[peak]),
						   "kg": round(col_kg[peak], 0), "crates": round(col_kg[peak] / kpc)}
						  if peak is not None else None),
			"in_window": {"kg": round(total_kg, 0), "crates": round(total_kg / kpc),
						  "from_iso_week": _tag(weeks[0]) if weeks else None,
						  "to_iso_week": _tag(weeks[-1]) if weeks else None},
			"pickable_now": {"blocks": len(ready_now), "of": len(blocks), "minimum_pct": minimum},
			"no_pick_date": {"kg": round(no_date_kg, 0), "blocks": len(no_date)},
		},
		"weeks": [{"week": w, "iso_week": _tag(w), "label": getdate(w).strftime("%-d %b"),
				   "kg": round(col_kg[i], 0), "crates": round(col_kg[i] / kpc),
				   "is_peak": i == peak, "shade": _shade(col_kg[i], max(col_kg))}
				  for i, w in enumerate(weeks)],
		"max_cell_kg": round(max_cell, 0),
		"blocks": grid,
		"no_pick_date": [{"block": b["block"], "farm": b["farm"], "expected_kg": b["expected_kg"],
						  "reason": ("never_sampled" if b["state"] == "unsampled" else
								   "stale_sample" if b["stale"] else "not_rising")}
						 for b in no_date],
		"no_forecast": [{"block": r["block"], "farm": r.get("farm"),
						 "planting_year": r.get("planting_year"), "bearing_trees": r["bearing_trees"],
						 "reason": "not_bearing" if r.get("planting_year") else "no_planting_year"}
						for r in young],
		"states": {"ready": "Ready now", "waiting": "Ready in N weeks (locked until then)",
				   "last_season": "Dated off last season's window, no dry matter",
				   "nodate": "Sampled but dry matter is not rising",
				   "unsampled": "Never sampled"},
	}


# -- Picking Plan ---------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
@run
def picking_plan(farm=None, week=None, crew_available=None, days_per_week=5, pay_per_day=0):
	"""Picking Plan page (teddy's /avocado-labour) on the crop still on the trees.

	`week` is any date inside the week to open in detail (default: the first dated
	week from today). Wage fields are null unless the caller may see pay.
	"""
	_need_read()
	farm, crew = _farm(farm), _crew(crew_available)
	days = cint(days_per_week) or 5
	pay = flt(pay_per_day) if can_see_pay() else 0.0
	ctx = _context(farm, 0)
	plan = avocadolabour.build_plan(ctx.rows, ctx.projection, ctx.windows, ctx.harvests,
									crew_available=crew, days_per_week=days, pay_per_day=pay)
	rows, summary = plan["rows"], plan["summary"]
	for r in rows:
		sf = r["shortfall"]
		r["status"] = "no_crew" if sf is None else "short" if sf > 0 else "spare"
		r["people_short"] = round(sf, 1) if sf is not None and sf > 0 else 0
		r["people_spare"] = round(-sf, 1) if sf is not None and sf < 0 else 0
		r["by_block"] = _week_blocks(plan, r["week"], days)

	focus = None
	if week:
		focus = str(_monday(week))
	else:
		this_mon = str(_monday())
		focus = next((r["week"] for r in rows if r["week"] >= this_mon), rows[0]["week"] if rows else None)
	detail = next((r for r in rows if r["week"] == focus), None)

	rates = plan["rates"]
	rate_rows = [{"block": k, "kg_per_picker_day": round(v["kg_per_picker_day"], 1),
				  "basis": v["basis"], "events": v["events"]}
				 for k, v in sorted(rates.items()) if k != ""]
	estate = rates.get("")
	return {
		"farm": farm, "farms": _all_farms(), "crew_available": crew, "days_per_week": days,
		"pay_per_day_kes": pay if can_see_pay() else None, "can_see_pay": can_see_pay(),
		"kg_per_crate": plan["kg_per_crate"],
		"summary": summary,
		"kpis": {
			"peak_week": {"pickers": summary.get("peak_pickers"), "week": summary.get("peak_week")},
			"weeks_short": {"weeks": summary.get("short_weeks"), "first_week": summary.get("first_short_week"),
							"worst_shortfall_pickers": summary.get("worst_shortfall")},
			"picker_days": {"total": summary.get("total_picker_days"), "days_per_week": days},
			"wage_bill_kes": summary.get("wage_cost") if can_see_pay() else None,
			"cannot_staff": {"kg": plan["unscheduled_kg"], "blocks": len(plan["unscheduled"])},
		},
		"weeks": rows, "focus_week": focus, "week_detail": detail,
		"rates": {"blocks": rate_rows,
				  "estate": ({"kg_per_picker_day": round(estate["kg_per_picker_day"], 1),
							  "basis": estate["basis"], "events": estate["events"]} if estate else None)},
		"unscheduled": plan["unscheduled"], "unscheduled_kg": plan["unscheduled_kg"],
		"rejected_records": plan["rejected_records"],
	}


def _week_blocks(plan, week, days):
	out = []
	rates = {k: v for k, v in plan["rates"].items()}
	for block, kg in sorted(plan["block_kg"].get(week, {}).items(), key=lambda kv: -kv[1]):
		rate, basis = avocadolabour.rate_for(rates, block)
		pd = kg / rate if rate else 0
		out.append({"block": block, "kg": round(kg, 0),
					"crates": round(kg / avocadolabour.KG_PER_CRATE),
					"kg_per_picker_day": round(rate, 1), "rate_basis": basis,
					"measured": bool(rates.get(block)),
					"picker_days": round(pd, 1), "pickers_needed": round(pd / max(days, 1), 1)})
	return out


# -- Dry Matter -----------------------------------------------------------------


def _verdict_kind(dm):
	if dm is None:
		return None
	if dm >= avocadomaturity.MAX_DRY_MATTER_PCT:
		return "over"
	return "in" if dm >= avocadomaturity.MIN_DRY_MATTER_PCT else "under"


def _preview(readings):
	readings = as_dict(readings) if not isinstance(readings, list) else readings
	if isinstance(readings, dict):
		readings = [{"count_size": k, "moisture": v} for k, v in readings.items()]
	lo, hi = avocadomaturity.MIN_DRY_MATTER_PCT, avocadomaturity.MAX_DRY_MATTER_PCT
	sizes, dms = [], []
	for r in readings or []:
		dm = avocadomaturity._dry_matter(r.get("moisture"))
		if not dm:
			sizes.append({"count_size": cint(r.get("count_size")), "dry_matter_pct": None, "window": None})
			continue
		dms.append(dm)
		kind = _verdict_kind(dm)
		sizes.append({"count_size": cint(r.get("count_size")), "dry_matter_pct": dm, "window": kind,
					  "short_by_points": round(lo - dm, 1) if dm < lo else 0})
	avg = round(sum(dms) / len(dms), 1) if dms else None
	return {"sizes": sizes, "average_dry_matter_pct": avg,
			"ready_sizes": sum(1 for d in dms if d >= lo), "of": len(dms),
			"window": _verdict_kind(avg),
			"verdict": avocadomaturity._verdict(avg) if avg is not None else None,
			"min_pct": lo, "max_pct": hi}


@frappe.whitelist(methods=["POST"])
@run
def dry_matter_preview(readings):
	"""Moisture to dry matter for each fruit size, the average and the verdict (no save)."""
	_need_read()
	return _preview(readings)


@frappe.whitelist(methods=["POST"])
@run
def dry_matter(farm=None, block=None):
	"""Dry Matter page: the entry form's lookups, every block's state, trend and recent visits."""
	_need_read()
	farm, block = _farm(farm), _farm(block)
	form = avocadomaturity.get_form()
	if farm:
		form["blocks"] = [b for b in form["blocks"] if b.get("farm") == farm]
	names = {b["block"] for b in form["blocks"]}
	minimum = avocadomaturity.MIN_DRY_MATTER_PCT
	projection = avocadoapi.dm_projection([s for s in avocadoapi._samples()
										   if s.get("orchard_block") in names])

	series = {}
	for s in avocadoapi._samples():
		b = s.get("orchard_block")
		if b not in names or not flt(s.get("avg_dry_matter_pct")):
			continue
		series.setdefault(b, []).append({
			"date": str(s.get("sample_date")),
			"dry_matter_pct": avocadoapi.dry_matter_from_moisture(s.get("avg_dry_matter_pct")),
			"measured_on": s.get("measured_on") or "block"})
	for pts in series.values():
		pts.sort(key=lambda p: p["date"])

	rows = []
	for b in form["blocks"]:
		p = projection.get(b["block"])
		pts = series.get(b["block"], [])
		if p:
			dm = p["dry_matter_pct"]
			state = ("stale" if p["stale"] else "ready" if p["ready"] else "rising")
		else:
			dm, state = None, "never_sampled"
		rows.append({
			"block": b["block"], "farm": b.get("farm"), "planting_year": b.get("planting_year"),
			"state": state, "dry_matter_pct": dm,
			"short_pct": round(max(0.0, minimum - dm), 1) if dm is not None else None,
			"sample_date": p["sample_date"] if p else None, "samples": p["samples"] if p else 0,
			"gain_pct_per_week": p["gain_per_week"] if p else None,
			"gain_basis": p["gain_basis"] if p else None,
			"weeks_to_minimum": p["weeks_to_minimum"] if p else None,
			"ready_date": p["ready_date"] if p else None,
			"sample_age_weeks": p["sample_age_weeks"] if p else None,
			"needs": p["needs"] if p else "a first dry matter sample",
			"measured_on": pts[-1]["measured_on"] if pts else None,
			"trend": pts,
		})
	rows.sort(key=lambda r: (r["dry_matter_pct"] is None, -(r["dry_matter_pct"] or 0)))

	recent = avocadomaturity.recent(orchard_block=block) if block else avocadomaturity.recent()
	visits = [v for v in recent["visits"]
			  if not farm or v["where"] in names or v["measured_on"] == "area"]
	return {
		"farm": farm, "block": block, "farms": _all_farms(), "form": form,
		"minimum_pct": minimum, "maximum_pct": avocadomaturity.MAX_DRY_MATTER_PCT,
		"blocks": rows,
		"summary": {"blocks": len(rows),
					"ready": sum(1 for r in rows if r["state"] == "ready"),
					"rising": sum(1 for r in rows if r["state"] == "rising"),
					"stale": sum(1 for r in rows if r["state"] == "stale"),
					"never_sampled": sum(1 for r in rows if r["state"] == "never_sampled")},
		"recent_visits": visits,
		"units": {"dry_matter": "% of fresh weight", "moisture_input": "fraction (0.77) or % (77)"},
	}


# -- Writes ---------------------------------------------------------------------


@frappe.whitelist(methods=["POST"])
@run
def set_forecast_mode(mode):
	"""Remember the manual/automatic toggle for this user."""
	_need_read()
	m = _mode(mode)
	frappe.defaults.set_user_default(PREF_MODE, m)
	return {"ok": True, "mode": m}


@frappe.whitelist(methods=["POST"])
@run
def save_price_per_kg(price_per_kg):
	"""Remember this user's KES per kg for forecast value."""
	_need_read()
	p = _num(price_per_kg)
	if p is None or p < 0:
		frappe.throw("Price per kg must be a number, zero or more.")
	frappe.defaults.set_user_default(PREF_PRICE, p)
	return {"ok": True, "price_per_kg": p}


@frappe.whitelist(methods=["POST"])
@run
def save_crew_available(crew_available):
	"""Remember how many pickers this user has on the books."""
	_need_read()
	n = _num(crew_available)
	if n is None or n < 0:
		frappe.throw("Crew available must be a number, zero or more.")
	frappe.defaults.set_user_default(PREF_CREW, n)
	return {"ok": True, "crew_available": n}


@frappe.whitelist(methods=["POST"])
@run
def save_dry_matter(readings, orchard_block=None, planting_area=None, week_number=None,
					test_date=None, notes=None):
	"""Record a dry matter visit: moisture per fruit size for one block or planting area.

	`readings` is [{count_size, moisture}] (moisture as a fraction or a percentage).
	Returns what was saved, the average, and the verdict.
	"""
	_need_write()
	out = avocadomaturity.save_readings(
		readings, orchard_block=orchard_block, planting_area=planting_area,
		week_number=week_number, test_date=test_date, notes=notes)
	out["ok"] = True
	return out


@frappe.whitelist(methods=["POST"])
@run
def save_manual_forecast(orchard_block, expected_kg, season=None, crop="Whole Season",
						 price_per_kg=None, notes=None):
	"""Type a block's forecast for a season. One entry per block/season/crop: saving again updates it."""
	_need_write()
	kg = _num(expected_kg)
	if not orchard_block or kg is None or kg < 0:
		frappe.throw("Give the block and the expected kilograms.")
	if not frappe.db.exists(avocadoapi._block_source(), orchard_block):
		frappe.throw(f"There is no block {orchard_block}.")
	season = cint(season) or getdate(nowdate()).year
	crop = crop if crop in ("Whole Season", "Early", "Late") else "Whole Season"
	dt = avocadoapi.MANUAL_FORECAST_DOCTYPE
	name = frappe.db.exists(dt, {"orchard_block": orchard_block, "season": season, "crop": crop})
	doc = frappe.get_doc(dt, name) if name else frappe.new_doc(dt)
	doc.update({"orchard_block": orchard_block, "season": season, "crop": crop,
				"expected_kg": kg, "price_per_kg": _num(price_per_kg) or None,
				"entry_date": nowdate(), "notes": notes})
	doc.save(ignore_permissions=True)
	return {"ok": True, "name": doc.name, "created": not name, "block": orchard_block,
			"season": season, "crop": crop, "expected_kg": kg}


@frappe.whitelist(methods=["POST"])
@run
def save_season_budget(season, months, budget_price_per_kg=None, crop="Whole Season", notes=None):
	"""Set the season budget. `months` is [{month, budget_kg}]; the total is their sum."""
	_need_write()
	season = cint(season)
	if not season:
		frappe.throw("Say which season the budget is for.")
	crop = crop if crop in ("Whole Season", "Early", "Late") else "Whole Season"
	months = as_dict(months) if not isinstance(months, list) else months
	months = [m for m in (months or []) if _num(m.get("budget_kg")) is not None]
	# The doctype only ever totals its months, so a bare total has nowhere to live.
	if not months:
		frappe.throw("A budget is built month by month: give at least one month with kilograms.")
	total = sum(_num(m["budget_kg"]) for m in months)
	price = _num(budget_price_per_kg)
	dt = avocadoapi.MANUAL_BUDGET_DOCTYPE
	name = frappe.db.exists(dt, {"season": season, "crop": crop})
	doc = frappe.get_doc(dt, name) if name else frappe.new_doc(dt)
	doc.season, doc.crop, doc.entry_date, doc.notes = season, crop, nowdate(), notes
	doc.budget_price_per_kg = price or None
	doc.budget_kg = total
	doc.budget_value = round(total * price, 0) if price else None
	doc.set("months", [])
	for m in months:
		doc.append("months", {"month": m["month"], "budget_kg": _num(m["budget_kg"]),
							  "budget_value": round(_num(m["budget_kg"]) * price, 0) if price else None})
	doc.save(ignore_permissions=True)
	return {"ok": True, "name": doc.name, "created": not name, "season": season, "crop": crop,
			"budget_kg": total}
