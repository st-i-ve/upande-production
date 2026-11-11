"""Silage production API: for the Silage page and for consumers (upande_livestock reads silage cost per kg).

Every endpoint returns data or {"error": msg} (see envelope.run). Labour figures are None for users who
cannot see pay; totals and cost per kg are not pay and are always returned.

Consumers:
* silage_cycles(status=None) -> {"ok": True, "cycles": [cycle]}
* silage_cost_summary(from_date, to_date) -> {"ok": True, "from_date", "to_date",
  "cycles": [cycle with cost by kind, ensiled_kg, cost_per_kg], "totals": {cost, ensiled_kg, cost_per_kg, cycles}}

A cycle: {name, title, crop, production_crop, production_unit, crop_cycle, status, docstatus, start_date,
closed_on, pit_warehouse, silage_item, ensiled_kg, cost: {inputs, diesel, labour, casual_labour, total},
by_kind: [{kind, label, amount, share_pct}], cost_per_kg, diesel_litres, machine_hours, receipt_stock_entry,
activities}.
"""

import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, today

from upande_production.api.envelope import as_dict, run
from upande_production.production.logic import silage
from upande_production.production.logic.settings import can_see_pay

DT = silage.DT
EDITABLE = ("title", "crop", "production_crop", "production_unit", "crop_cycle", "status", "start_date",
	"pit_warehouse", "silage_item", "ensiled_kg", "include_casual_labour", "notes")


def _need(doctype=DT, ptype="read"):
	frappe.has_permission(doctype, ptype, throw=True)


# ---------------------------------------------------------------- consumers

@frappe.whitelist(methods=["GET", "POST"])
@run
def silage_cycles(status=None):
	_need()
	if status and status not in silage.STATUSES:
		frappe.throw(_("Unknown status {0}").format(status), frappe.ValidationError)
	return {"ok": True, "cycles": silage.list_cycles(status or None, can_see_pay())}


@frappe.whitelist(methods=["GET", "POST"])
@run
def silage_cost_summary(from_date, to_date):
	_need()
	return {"ok": True, **silage.cost_summary(from_date, to_date, can_see_pay())}


# ---------------------------------------------------------------- the Silage page

@frappe.whitelist(methods=["POST"])
@run
def silage_page(status=None):
	"""Everything the page opens with: cycles, the pit stock, the year's summary and the form options."""
	_need()
	pay = can_see_pay()
	to = getdate(today())
	frm = add_days(to, -364)
	return {
		"ok": True,
		"cycles": silage.list_cycles(status or None, pay),
		"pit_stock": silage.pit_stock(),
		"summary": silage.cost_summary(frm, to, pay)["totals"],
		"summary_window": {"from_date": str(frm), "to_date": str(to)},
		"can_see_pay": pay,
		"can_edit": bool(frappe.has_permission(DT, "write")),
		"can_close": bool(frappe.has_permission(DT, "submit")),
		"allocations_available": silage.has_allocations(),
		"options": _options(),
	}


def _options() -> dict:
	silage_crops = frappe.get_all("Production Crop", filters={"enabled": 1, "grown_for_silage": 1}, pluck="name",
		order_by="sort_order asc, name asc") if frappe.get_meta("Production Crop").has_field("grown_for_silage") else []
	unit_filters = {"is_group": 0, "status": ("!=", "Retired")}
	if silage_crops:
		unit_filters["crop"] = ("in", silage_crops)
	return {
		"crops": list(silage.CROPS),
		"statuses": list(silage.STATUSES),
		"activities": _activity_options(),
		"production_crops": silage_crops,
		"units": frappe.get_all("Production Unit", filters=unit_filters, fields=["name", "unit_name", "crop"],
			order_by="unit_name asc"),
		"warehouses": frappe.get_all("Warehouse", filters={"is_group": 0, "disabled": 0}, pluck="name",
			order_by="name asc"),
		"input_warehouse": silage.setting("silage_input_warehouse"),
		"pit_warehouse": silage.setting("silage_pit_warehouse"),
		"day_rate": silage.day_rate_default() if can_see_pay() else None,
	}


def _activity_options() -> list[str]:
	field = frappe.get_meta("Silage Cycle Activity").get_field("activity")
	return [o for o in (field.options or "").split("\n") if o] if field else []


@frappe.whitelist(methods=["POST"])
@run
def silage_cycle(name):
	_need()
	return {"ok": True, "cycle": silage.cycle_detail(name, can_see_pay())}


@frappe.whitelist(methods=["POST"])
@run
def silage_items(search=""):
	"""Stock items for the input and silage-item pickers."""
	_need()
	filters = {"is_stock_item": 1, "disabled": 0}
	or_filters = {"item_code": ("like", f"%{search}%"), "item_name": ("like", f"%{search}%")} if search else None
	rows = frappe.get_all("Item", filters=filters, or_filters=or_filters, fields=["name", "item_name", "stock_uom"],
		order_by="item_name asc", limit=50)
	return {"ok": True, "items": [{"item_code": r.name, "item_name": r.item_name, "stock_uom": r.stock_uom} for r in rows]}


@frappe.whitelist(methods=["POST"])
@run
def save_silage_cycle(data):
	"""Create (no name) or update a draft cycle. Only the page's fields are taken."""
	data = as_dict(data) or {}
	name = data.get("name")
	values = {k: data[k] for k in EDITABLE if k in data}
	if name:
		_need(ptype="write")
		doc = frappe.get_doc(DT, name)
		if doc.docstatus != 0:
			frappe.throw(_("Silage cycle {0} is closed").format(name), frappe.ValidationError)
		doc.update(values)
		doc.save()
	else:
		_need(ptype="create")
		doc = frappe.get_doc({"doctype": DT, **values})
		doc.insert()
	return {"ok": True, "name": doc.name, "cycle": silage.cycle_detail(doc.name, can_see_pay())}


@frappe.whitelist(methods=["POST"])
@run
def add_silage_activity(cycle, date, activity, workers=None, day_rate=None, labour_cost=None, notes=None):
	"""Append one activity row to a draft cycle. Labour is workers x day rate (rate defaults from settings)."""
	_need(ptype="write")
	doc = frappe.get_doc(DT, cycle)
	if doc.docstatus != 0:
		frappe.throw(_("Silage cycle {0} is closed").format(cycle), frappe.ValidationError)
	pay = can_see_pay()
	doc.append("activities", {
		"date": date, "activity": activity, "workers": int(flt(workers)) if workers not in (None, "") else None,
		# a user who cannot see pay cannot set it either: the settings rate applies
		"day_rate": flt(day_rate) if pay and day_rate not in (None, "") else None,
		"labour_cost": flt(labour_cost) if pay and labour_cost not in (None, "") else None,
		"notes": notes,
	})
	doc.save()
	return {"ok": True, "cycle": silage.cycle_detail(doc.name, pay)}


@frappe.whitelist(methods=["POST"])
@run
def remove_silage_activity(cycle, row):
	_need(ptype="write")
	doc = frappe.get_doc(DT, cycle)
	if doc.docstatus != 0:
		frappe.throw(_("Silage cycle {0} is closed").format(cycle), frappe.ValidationError)
	doc.activities = [r for r in doc.activities if r.name != row]
	doc.save()
	return {"ok": True, "cycle": silage.cycle_detail(doc.name, can_see_pay())}


@frappe.whitelist(methods=["POST"])
@run
def issue_silage_inputs(cycle, items, warehouse=None, posting_date=None):
	"""Issue inputs from stock to the cycle: one submitted Material Issue. items: [{item_code, qty, uom?}]."""
	_need(ptype="write")
	frappe.has_permission("Stock Entry", "submit", throw=True)
	rows = as_dict(items) if isinstance(items, str) else items
	se = silage.issue_inputs(cycle, rows if isinstance(rows, list) else [], warehouse, posting_date)
	return {"ok": True, "stock_entry": se.name, "cycle": silage.cycle_detail(cycle, can_see_pay())}


@frappe.whitelist(methods=["POST"])
@run
def close_silage_cycle(name, ensiled_kg, closed_on=None, silage_item=None, pit_warehouse=None):
	"""Close: freeze the cost and receive the ensiled kilos into the pit at cost per kg."""
	_need(ptype="submit")
	doc = silage.close_cycle(name, ensiled_kg, closed_on, silage_item, pit_warehouse)
	return {"ok": True, "stock_entry": doc.receipt_stock_entry, "cycle": silage.cycle_detail(doc.name, can_see_pay())}


@frappe.whitelist(methods=["POST"])
@run
def silage_pit_stock():
	_need()
	return {"ok": True, "pit_stock": silage.pit_stock()}
