"""Desk API: add a crop cycle (new or already in production) and import many from a sheet."""

import frappe
from frappe import _

from upande_production.api.envelope import as_dict, run
from upande_production.production.logic import cycle_setup
from upande_production.production.logic.settings import crop_allowed


def _gate(crop=None):
	frappe.has_permission("Production Crop Cycle", "create", throw=True)
	if crop and not crop_allowed(crop):
		frappe.throw(_("You are not permitted to see this crop."), frappe.PermissionError)


@frappe.whitelist(methods=["POST"])
@run
def add_cycle(data):
	"""Create one cycle. data: unit, variety, protocol, start_date, area_ha, plant_count, cycle_type, and for a
	cycle already in production existing=1, planting_date, current_stage, last_flowering_date,
	last_harvest_date, last_season_yield_kg. Returns {name, warnings}; a block over capacity warns, never fails."""
	data = as_dict(data) or {}
	crop = frappe.db.get_value("Production Unit", data.get("unit"), "crop")
	_gate(crop)
	return cycle_setup.create_cycle(data)


@frappe.whitelist(methods=["POST"])
@run
def import_template():
	_gate()
	return {"filename": "crop-cycles-template.csv", "columns": cycle_setup.TEMPLATE_COLUMNS, "content": cycle_setup.template_csv()}


@frappe.whitelist(methods=["POST"])
@run
def preview_import(crop, filename, content):
	"""Parse an uploaded CSV / XLSX (content = base64) and check every row; nothing is created."""
	_gate(crop)
	rows = cycle_setup.check_rows(crop, cycle_setup.parse_file(filename, content))
	return {"rows": rows, "ok": sum(1 for r in rows if not r["errors"]), "bad": sum(1 for r in rows if r["errors"])}


@frappe.whitelist(methods=["POST"])
@run
def import_cycles(crop, rows):
	"""Create the cycles of the (raw) rows a preview returned; rows that fail are reported, the rest are made."""
	_gate(crop)
	results = cycle_setup.import_rows(crop, as_dict(rows) or [])
	return {"results": results, "created": sum(1 for r in results if r["ok"])}
