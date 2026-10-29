"""KPI colour bands (Production Settings > Bands) and the per-crop limits behind the field logs.

A band row covers `min <= value < max`; `max` empty or not above `min` means no upper limit.
Thresholds live only here and in the settings: pages get them in their payload and never keep
their own copy.
"""

import frappe
from frappe.utils import flt

BAND_FIELDS = ["band_set", "label", "metric", "min", "max", "severity"]


def _row(r) -> dict:
	lo, hi = flt(r.get("min")), flt(r.get("max"))
	return {
		"band_set": r.get("band_set"), "label": r.get("label") or "", "metric": r.get("metric") or "",
		"min": lo, "max": hi if hi > lo else None, "severity": r.get("severity") or "Good",
	}


def get_bands() -> dict[str, list[dict]]:
	"""{band_set: [rows in the order the manager keeps them]}; empty when none are set."""
	rows = frappe.get_all(
		"Production Band", filters={"parent": "Production Settings", "parenttype": "Production Settings"},
		fields=BAND_FIELDS, order_by="idx asc", limit_page_length=0,
	)
	out: dict[str, list[dict]] = {}
	for r in rows:
		if (r.band_set or "").strip():
			out.setdefault(r.band_set.strip(), []).append(_row(r))
	return out


def band_for(rows: list[dict] | None, value) -> dict | None:
	"""The first row `value` falls in, or None (no value, no rows, or a gap)."""
	if value is None:
		return None
	for r in rows or []:
		if value >= r["min"] and (r["max"] is None or value < r["max"]):
			return r
	return None


def band_of(band_set: str, value, bands: dict | None = None) -> dict | None:
	return band_for((bands if bands is not None else get_bands()).get(band_set), value)


def on_target_from(rows: list[dict] | None) -> float | None:
	"""The lowest `min` among Good rows: values at or above it count as on target."""
	good = [r["min"] for r in rows or [] if r["severity"] == "Good"]
	return min(good) if good else None


def save_bands(rows) -> None:
	"""Replace the settings' band rows (permission is checked by the caller)."""
	doc = frappe.get_doc("Production Settings")
	doc.set("bands", [])
	for r in rows or []:
		if not (r.get("band_set") or "").strip():
			frappe.throw("Every band needs a band set.", frappe.ValidationError)
		lo, hi = flt(r.get("min")), flt(r.get("max"))
		if hi and hi <= lo:
			frappe.throw(f"{r.get('band_set')}: 'Up to' must be above 'From'.", frappe.ValidationError)
		doc.append("bands", {k: r.get(k) for k in BAND_FIELDS if k in r})
	doc.save()


def crop_limits(crop: str, *fields: str) -> dict:
	"""{field: float or None} from the Production Crop; None where the manager has not set it."""
	vals = frappe.db.get_value("Production Crop", crop, list(fields), as_dict=True) or {}
	return {f: (flt(vals.get(f)) if vals.get(f) not in (None, "", 0) else None) for f in fields}
