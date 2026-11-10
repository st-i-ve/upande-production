"""Export count sizes: the gram band each count covers, and the checks that keep the bands contiguous.

A count is fruits per 4 kg carton, so a low count is big fruit. Sorted by count, each band's max should
equal the min of the next-lower count (the bigger fruit above it): no gap, no overlap. Pure functions on
rows ({count, min_g, max_g}), so the form, the settings screen and the importers all use the same check.
"""

from frappe.utils import cint, flt


def _g(v):
	v = flt(v)
	return int(v) if v == int(v) else round(v, 2)


def _clean(rows):
	"""Rows with a count, as (count, min, max, row)."""
	out = []
	for r in rows or []:
		get = r.get if hasattr(r, "get") else (lambda k, d=None: getattr(r, k, d))
		count = cint(get("count"))
		if count:
			out.append((count, flt(get("min_g")), flt(get("max_g")), r))
	return sorted(out, key=lambda t: t[0])


def band_issues(rows):
	"""List of {kind, counts, lo, hi, message}. kind: invalid | duplicate | order | gap | overlap."""
	issues = []
	bands = _clean(rows)
	seen = set()
	for c, lo, hi, _r in bands:
		if c in seen:
			issues.append({"kind": "duplicate", "counts": [c], "lo": None, "hi": None,
						   "message": f"Count {c} appears more than once"})
		seen.add(c)
		if lo >= hi:
			issues.append({"kind": "invalid", "counts": [c], "lo": lo, "hi": hi,
						   "message": f"Count {c}: min {_g(lo)} g is not below max {_g(hi)} g"})
	for (ca, alo, ahi, _a), (cb, blo, bhi, _b) in zip(bands, bands[1:]):
		if ca == cb or alo >= ahi or blo >= bhi:
			continue
		if blo >= alo:
			issues.append({"kind": "order", "counts": [ca, cb], "lo": blo, "hi": alo,
						   "message": f"Count {cb} is not lighter than count {ca} (a higher count is smaller fruit)"})
		elif bhi < alo:
			issues.append({"kind": "gap", "counts": [ca, cb], "lo": bhi, "hi": alo,
						   "message": f"Fruit between {_g(bhi)} g and {_g(alo)} g has no count size"})
		elif bhi > alo:
			issues.append({"kind": "overlap", "counts": [ca, cb], "lo": alo, "hi": bhi,
						   "message": f"Counts {ca} and {cb} both cover {_g(alo)}–{_g(bhi)} g"})
	return issues


def close_gaps(rows):
	"""[(count, min, max)] with every band's max snapped to the next-lower count's min."""
	bands = [[c, lo, hi] for c, lo, hi, _r in _clean(rows)]
	for prev, cur in zip(bands, bands[1:]):
		cur[2] = prev[1]
	return [tuple(b) for b in bands]


def _band_list(crop):
	rows = crop.get("count_sizes") if hasattr(crop, "get") else None
	if rows is None and isinstance(crop, str):
		import frappe
		rows = frappe.get_all("Production Crop Count Size", filters={"parent": crop},
							  fields=["count", "min_g", "max_g"], limit_page_length=0)
	return _clean(rows)


def count_for_weight(crop, grams):
	"""The count whose band holds `grams` (min <= grams < max), or None when it falls in a gap or outside every band.
	`crop` is a Production Crop document or name."""
	g = flt(grams)
	for c, lo, hi, _r in _band_list(crop):
		if lo <= g < hi:
			return c
	return None


def nearest_counts(crop, grams):
	"""(bigger_fruit_count, smaller_fruit_count) either side of a weight that fits no band; either may be None."""
	g = flt(grams)
	bands = _band_list(crop)
	above = [c for c, lo, hi, _r in bands if lo >= g]
	below = [c for c, lo, hi, _r in bands if hi <= g]
	big = min(above, key=lambda c: next(lo for cc, lo, _h, _r in bands if cc == c) - g) if above else None
	small = min(below, key=lambda c: g - next(hi for cc, _l, hi, _r in bands if cc == c)) if below else None
	return big, small


def weight_warning(crop, grams):
	"""None when the weight has a count; otherwise a sentence naming the nearest counts."""
	if count_for_weight(crop, grams) is not None:
		return None
	big, small = nearest_counts(crop, grams)
	near = " and ".join(f"count {c}" for c in (big, small) if c)
	g = _g(grams)
	return (f"{g} g falls in no count size" + (f"; nearest are {near}" if near else "")
			+ ". Check the count size bands on the crop.")
