"""Tagged-fruit dry matter monitoring (avocado).

A fruit is tagged on a tree (a tree is a block plus a tree label, e.g. "R12-T7") and measured again and
again as it matures. Each reading holds up to two methods:

* microwave: fresh weight and dry weight in grams, optional dish (tare) weight.
  dry matter % = (dry - dish) / (fresh - dish) x 100. Nobody does the sum by hand.
* machine: the % read straight off a dry matter meter (NIR), optional instrument id.

One number drives the trend and "ready": a reading's `dm_pct` is the AVERAGE of the two methods when both
were used, else the one that was. Both values are stored and shown; the chart draws them as separate series.

Series: a fruit's series is its own readings by date. A tree's and a block's series are weekly: each fruit's
readings in an ISO week are averaged, then the fruit averages are averaged (so a fruit measured three times
in a week counts once). The projected date a series crosses the export target is a straight line fitted to its
last few points.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, today

from upande_production.production.logic import drymatter

TAG = "Dry Matter Fruit Tag"
STATUSES = ("Active", "Harvested", "Lost")
# the line is fitted to the last N points, no older than this many days before the newest
FIT_POINTS = 6
FIT_WINDOW_DAYS = 42
MAX_PROJECT_DAYS = 180
# a fruit that reads outside this is very likely a slip of the finger (an avocado is 10 to 50 % dry matter)
PLAUSIBLE = (5.0, 60.0)
READING_KEYS = ("reading_date", "fresh_g", "dish_g", "dry_g", "machine_pct", "instrument", "notes")


def microwave_pct(fresh_g, dry_g, dish_g=0):
	"""Dry matter % from the two weighings, or None when they are not both given. Raises on impossible weights."""
	fresh, dry, dish = flt(fresh_g), flt(dry_g), flt(dish_g)
	if not fresh and not dry:
		return None
	if not fresh or not dry:
		frappe.throw(_("A microwave reading needs both the fresh and the dry weight."), frappe.ValidationError)
	if dish < 0:
		frappe.throw(_("The dish weight cannot be negative."), frappe.ValidationError)
	net_fresh, net_dry = fresh - dish, dry - dish
	if net_fresh <= 0:
		frappe.throw(_("The fresh weight must be more than the dish weight."), frappe.ValidationError)
	if net_dry <= 0:
		frappe.throw(_("The dry weight must be more than the dish weight."), frappe.ValidationError)
	if net_dry > net_fresh:
		frappe.throw(_("The dry weight cannot be more than the fresh weight."), frappe.ValidationError)
	return round(net_dry / net_fresh * 100, 2)


def combine(micro, machine):
	"""The value that drives the trend: the average of both methods, else whichever exists."""
	vals = [v for v in (micro, machine) if v is not None]
	return round(sum(vals) / len(vals), 2) if vals else None


def fill_reading(row, user=None):
	"""Compute a reading row (child doc or dict-like) in place: microwave %, method label, combined %."""
	micro = microwave_pct(row.get("fresh_g"), row.get("dry_g"), row.get("dish_g"))
	machine = row.get("machine_pct")
	machine = None if machine in (None, "") or not flt(machine) else flt(machine)
	if machine is not None and not (0 < machine <= 100):
		frappe.throw(_("The machine reading must be a percentage between 0 and 100."), frappe.ValidationError)
	if micro is None and machine is None:
		frappe.throw(_("Enter the microwave weights, the machine reading, or both."), frappe.ValidationError)
	if not row.get("reading_date"):
		frappe.throw(_("A reading needs a date."), frappe.ValidationError)
	if getdate(row.get("reading_date")) > getdate(today()):
		frappe.throw(_("A reading cannot be dated in the future."), frappe.ValidationError)
	row.microwave_pct = micro
	row.machine_pct = machine
	row.method = "Both" if micro is not None and machine is not None else "Microwave" if micro is not None else "Machine"
	row.dm_pct = combine(micro, machine)
	row.recorded_by = row.get("recorded_by") or frappe.session.user
	if not any(PLAUSIBLE[0] <= v <= PLAUSIBLE[1] for v in (micro, machine, row.dm_pct) if v is not None):
		frappe.throw(_("{0} % dry matter is not plausible for a fruit. Check the weights or the reading.").format(row.dm_pct),
			frappe.ValidationError)
	return row


def refresh_latest(doc):
	rows = sorted(doc.readings or [], key=lambda r: (str(r.reading_date), r.idx))
	last = rows[-1] if rows else None
	doc.latest_pct = last.dm_pct if last else None
	doc.latest_on = last.reading_date if last else None


# -- series -----------------------------------------------------------------


def _monday(d):
	d = getdate(d)
	return add_days(d, -d.weekday())


def _mean(vals):
	vals = [v for v in vals if v is not None]
	return round(sum(vals) / len(vals), 2) if vals else None


def fruit_series(readings):
	"""[{date, dm_pct, microwave_pct, machine_pct}] oldest first, one point per reading date (same-day readings averaged)."""
	by_day = {}
	for r in readings:
		by_day.setdefault(str(r["reading_date"]), []).append(r)
	return [{"date": d, "dm_pct": _mean([r.get("dm_pct") for r in rs]),
		"microwave_pct": _mean([r.get("microwave_pct") for r in rs]),
		"machine_pct": _mean([r.get("machine_pct") for r in rs]), "fruit": 1}
		for d, rs in sorted(by_day.items())]


def group_series(tags):
	"""Weekly average over several fruit: [{date (Monday), dm_pct, microwave_pct, machine_pct, fruit}]."""
	weeks = {}
	for t in tags:
		per = {}
		for r in t["readings"]:
			per.setdefault(str(_monday(r["reading_date"])), []).append(r)
		for wk, rs in per.items():
			w = weeks.setdefault(wk, {"dm": [], "mw": [], "mc": []})
			w["dm"].append(_mean([r.get("dm_pct") for r in rs]))
			w["mw"].append(_mean([r.get("microwave_pct") for r in rs]))
			w["mc"].append(_mean([r.get("machine_pct") for r in rs]))
	return [{"date": wk, "dm_pct": _mean(w["dm"]), "microwave_pct": _mean(w["mw"]), "machine_pct": _mean(w["mc"]),
		"fruit": len([v for v in w["dm"] if v is not None])} for wk, w in sorted(weeks.items())]


def projection(points, target):
	"""When a series reaches `target`: a straight line through its last few points.

	{state: reached|rising|flat|few|far|none, date, slope_per_week, points}. `reached` carries the first date a point was at or
	over the target. Needs two readings on different days."""
	pts = [(getdate(p["date"]), flt(p["dm_pct"])) for p in points if p.get("dm_pct") is not None]
	if not target:
		return {"state": "none", "date": None, "slope_per_week": None, "points": 0}
	if not pts:
		return {"state": "none", "date": None, "slope_per_week": None, "points": 0}
	last_d, last_v = pts[-1]
	if last_v >= target:
		first = next(d for d, v in pts if v >= target)
		return {"state": "reached", "date": str(first), "slope_per_week": None, "points": len(pts)}
	fit = [(d, v) for d, v in pts[-FIT_POINTS:] if (last_d - d).days <= FIT_WINDOW_DAYS]
	if len(fit) < 2 or (fit[-1][0] - fit[0][0]).days < 3:
		return {"state": "few", "date": None, "slope_per_week": None, "points": len(fit)}
	x0 = fit[0][0]
	xs = [(d - x0).days for d, _v in fit]
	ys = [v for _d, v in fit]
	mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
	den = sum((x - mx) ** 2 for x in xs)
	slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
	out = {"slope_per_week": round(slope * 7, 2), "points": len(fit)}
	if slope <= 0:
		return {**out, "state": "flat", "date": None}
	intercept = my - slope * mx
	x_cross = (target - intercept) / slope
	x_last = (last_d - x0).days
	days_from_last = max(0.0, x_cross - x_last)
	if days_from_last > MAX_PROJECT_DAYS:
		return {**out, "state": "far", "date": None}
	return {**out, "state": "rising", "date": str(add_days(last_d, int(round(days_from_last))))}


# -- reading and writing tags -----------------------------------------------


def _read_row(r):
	# an empty Float comes back from the database as 0; a weight or a percentage of 0 means "not measured"
	return {"name": r.name, "idx": r.idx, "reading_date": str(r.reading_date), "method": r.method,
		"fresh_g": r.fresh_g or None, "dish_g": r.dish_g or None, "dry_g": r.dry_g or None,
		"microwave_pct": r.microwave_pct or None, "machine_pct": r.machine_pct or None,
		"instrument": r.instrument, "dm_pct": r.dm_pct, "recorded_by": r.recorded_by, "notes": r.notes}


def tag_row(doc, target=None):
	rows = [_read_row(r) for r in sorted(doc.readings or [], key=lambda r: (str(r.reading_date), r.idx))]
	return {"name": doc.name, "unit": doc.unit, "farm": doc.farm, "crop": doc.crop, "cycle": doc.cycle,
		"variety": doc.variety, "tree_label": doc.tree_label, "fruit_tag": doc.fruit_tag,
		"tagged_on": str(doc.tagged_on) if doc.tagged_on else None, "status": doc.status, "notes": doc.notes,
		"readings": rows, "latest_pct": doc.latest_pct, "latest_on": str(doc.latest_on) if doc.latest_on else None,
		"ready": bool(target and doc.latest_pct is not None and flt(doc.latest_pct) >= target)}


def create_tag(d, ignore_permissions=False):
	"""Tag a fruit: {unit, tree_label, fruit_tag, tagged_on?, notes?, reading?}; an optional first reading goes in with it."""
	doc = frappe.new_doc(TAG)
	doc.update({"unit": d.get("unit"), "tree_label": d.get("tree_label"), "fruit_tag": d.get("fruit_tag"),
		"tagged_on": d.get("tagged_on") or today(), "notes": d.get("notes"), "status": "Active"})
	if d.get("reading"):
		doc.append("readings", clean_reading(d["reading"]))
	doc.flags.ignore_permissions = ignore_permissions
	doc.insert()
	return doc


def clean_reading(data):
	return {k: data.get(k) for k in READING_KEYS if data.get(k) not in (None, "")}


def add_reading(tag, reading, ignore_permissions=False):
	doc = frappe.get_doc(TAG, tag)
	doc.append("readings", clean_reading(reading))
	doc.flags.ignore_permissions = ignore_permissions
	doc.save()
	return doc


def delete_reading(tag, row_name, ignore_permissions=False):
	doc = frappe.get_doc(TAG, tag)
	rows = [r for r in doc.readings if r.name == row_name]
	if not rows:
		frappe.throw(_("That reading is not on this fruit."), frappe.ValidationError)
	doc.remove(rows[0])
	doc.flags.ignore_permissions = ignore_permissions
	doc.save()
	return doc


def update_tag(tag, status=None, notes=None, ignore_permissions=False):
	doc = frappe.get_doc(TAG, tag)
	if status is not None:
		if status not in STATUSES:
			frappe.throw(_("Status must be one of {0}.").format(", ".join(STATUSES)), frappe.ValidationError)
		doc.status = status
	if notes is not None:
		doc.notes = notes
	doc.flags.ignore_permissions = ignore_permissions
	doc.save()
	return doc


# -- the page ---------------------------------------------------------------


def crop_window(crop):
	"""(target, max) export window of the crop; None where unset."""
	c = frappe.db.get_value("Production Crop", crop, ["dry_matter_target_pct", "dry_matter_max_pct"], as_dict=True)
	if not c:
		return None, None
	return flt(c.dry_matter_target_pct) or None, flt(c.dry_matter_max_pct) or None


def blocks_of(crop, farm=None):
	filters = {"crop": crop, "status": ("!=", "Retired"), "is_group": 0}
	if farm:
		filters["farm"] = farm
	return frappe.get_all("Production Unit", filters=filters, fields=["name", "farm", "avocado_block_code"],
		order_by="name asc", limit_page_length=0)


def lab_points(units):
	"""{unit: [{date, dm_pct}]}: the lab maturity tests (count-size readings) of each block, averaged per test date."""
	if not frappe.db.exists("DocType", "Avocado Maturity Test") or not units:
		return {}
	by_code = {}
	for u in units:
		by_code[u["name"]] = u["name"]
		if u.get("avocado_block_code"):
			by_code[u["avocado_block_code"]] = u["name"]
	rows = frappe.get_all("Avocado Maturity Test", filters={"orchard_block": ("in", list(by_code))},
		fields=["orchard_block", "test_date", "dry_matter_pct"], order_by="test_date asc", limit_page_length=0)
	acc = {}
	for r in rows:
		if flt(r.dry_matter_pct):
			acc.setdefault((by_code[r.orchard_block], str(r.test_date)), []).append(flt(r.dry_matter_pct))
	out = {}
	for (u, d), v in sorted(acc.items(), key=lambda kv: kv[0][1]):
		out.setdefault(u, []).append({"date": d, "dm_pct": round(sum(v) / len(v), 2)})
	return out


def monitor(crop, farm=None, unit=None):
	"""Everything the page draws: the blocks, every tagged fruit with its readings, and the fruit, tree and block series."""
	target, maximum = crop_window(crop)
	units = blocks_of(crop, farm)
	names = [u["name"] for u in units]
	if unit:
		names = [n for n in names if n == unit]
	tag_names = frappe.get_all(TAG, filters={"unit": ("in", names or [""])}, pluck="name", order_by="unit asc, tree_label asc, fruit_tag asc",
		limit_page_length=0)
	tags = [tag_row(frappe.get_doc(TAG, n), target) for n in tag_names]

	series = {"fruit": {}, "tree": {}, "block": {}}
	trees, blocks = {}, {}
	for t in tags:
		s = fruit_series(t["readings"])
		series["fruit"][t["name"]] = {"points": s, "projection": projection(s, target)}
		trees.setdefault(f"{t['unit']}||{t['tree_label']}", []).append(t)
		blocks.setdefault(t["unit"], []).append(t)
	for key, ts in trees.items():
		s = group_series(ts)
		series["tree"][key] = {"points": s, "projection": projection(s, target), "fruit": len(ts)}
	for key, ts in blocks.items():
		s = group_series(ts)
		series["block"][key] = {"points": s, "projection": projection(s, target), "fruit": len(ts)}
	lab = lab_points([u for u in units if u["name"] in names])
	return {"crop": crop, "target_pct": target, "max_pct": maximum,
		"blocks": [{"unit": u["name"], "farm": u["farm"]} for u in units], "tags": tags, "series": series, "lab": lab,
		"drives": "The average of the microwave and machine values when both were used, else the one that was."}


def tag_context(doc):
	"""Fill the unit-derived fields of a tag (crop, farm, cycle, variety)."""
	unit = frappe.db.get_value("Production Unit", doc.unit, ["crop", "farm"], as_dict=True)
	if not unit:
		frappe.throw(_("Block {0} was not found.").format(doc.unit), frappe.ValidationError)
	doc.crop = unit.crop
	doc.farm = unit.farm
	if not doc.cycle:
		doc.cycle = drymatter.cycle_on(doc.unit, doc.tagged_on)
	if doc.cycle and not doc.variety:
		doc.variety = frappe.db.get_value("Production Crop Cycle", doc.cycle, "variety")
