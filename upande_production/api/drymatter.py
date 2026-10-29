"""Generic dry matter tests (crops with dry_matter_testing on). Avocado keeps its own Maturity Test."""

import frappe

from upande_production.api.envelope import as_dict, run
from upande_production.production.logic import drymatter as logic
from upande_production.production.logic.units import unit_filter


def _shape(r, samples=None):
	out = {k: r.get(k) for k in (
		"name", "unit", "cycle", "crop", "variety", "test_date", "tested_on", "tested_by",
		"avg_pct", "target_pct", "ready", "stage",
	)}
	out["ready"] = bool(out["ready"])
	if samples is not None:
		out["samples"] = samples.get(r.name, [])
	return out


@frappe.whitelist(methods=["POST"])
@run
def list_tests(crop, unit=None):
	frappe.has_permission("Dry Matter Test", "read", throw=True)
	filters = {"crop": crop}
	if unit:
		filters["unit"] = unit
	else:
		filters = unit_filter(filters)
	rows = frappe.get_all(
		"Dry Matter Test", filters=filters, fields=["*"], order_by="test_date desc, creation desc", limit=500
	)
	samples = {}
	for s in frappe.get_all(
		"Dry Matter Sample", filters={"parenttype": "Dry Matter Test", "parent": ("in", [r.name for r in rows] or [""])},
		fields=["parent", "sample_no", "dry_matter_pct"], order_by="idx asc",
	):
		samples.setdefault(s.parent, []).append({"sample_no": s.sample_no, "dry_matter_pct": s.dry_matter_pct})
	return {"rows": [_shape(r, samples) for r in rows]}


@frappe.whitelist(methods=["POST"])
@run
def list_due(crop):
	"""Blocks whose variety is tested for dry matter and where each stands against its sampling stage."""
	frappe.has_permission("Dry Matter Test", "read", throw=True)
	return logic.due_rows(crop)


@frappe.whitelist(methods=["POST"])
@run
def save_test(data):
	"""Insert a test (the doctype computes average, target and ready)."""
	data = dict(as_dict(data) or {})
	for k in ("doctype", "docstatus", "name", "avg_pct", "target_pct", "ready"):
		data.pop(k, None)
	doc = frappe.get_doc({"doctype": "Dry Matter Test", **data})
	doc.insert()
	return {"name": doc.name, "avg_pct": doc.avg_pct, "ready": doc.ready}


def latest_by_unit(crop):
	"""{unit: {pct, target, ready, date}} from each unit's most recent test."""
	out = {}
	for r in frappe.get_all(
		"Dry Matter Test", filters=unit_filter({"crop": crop}), fields=["unit", "test_date", "avg_pct", "target_pct", "ready"],
		order_by="test_date desc, creation desc", limit_page_length=0,
	):
		out.setdefault(r.unit, {
			"pct": r.avg_pct, "target": r.target_pct, "ready": bool(r.ready), "date": str(r.test_date),
		})
	return out
