"""Machines and asset allocations: the desk pages' API and the read other apps call.

Every endpoint returns data or {"error": msg} (api/envelope.run). Gates are document rights:
reading needs read on Production Asset Allocation or Production Machine; starting and closing an
allocation needs create / write on Production Asset Allocation (Production Supervisor and up);
saving a machine needs Production Manager's rights on Production Machine.

``allocation_costs`` is the consumer API (upande_livestock's cost per animal reads it for the
feedlot's diesel). It is read-guarded: the caller must be able to read Production Asset
Allocation, or Stock Entry, since every figure it returns is the value of a posted Stock Entry.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime

from upande_production.api.envelope import as_dict, run
from upande_production.production.logic import asset_allocation as aa
from upande_production.production.logic import qr

MACHINE_FIELDS = ("machine_name", "machine_type", "asset", "fuel_item", "default_cost_center", "disabled", "notes")


def _can(doctype, ptype="read") -> bool:
	return bool(frappe.has_permission(doctype, ptype))


def _need_read():
	if not (_can(aa.ALLOCATION) or _can(aa.MACHINE)):
		frappe.throw(_("You are not permitted to see machine allocations."), frappe.PermissionError)


def _need(doctype, ptype):
	if not _can(doctype, ptype):
		frappe.throw(_("You are not permitted to do this."), frappe.PermissionError)


@frappe.whitelist(methods=["GET", "POST"])
@run
def allocation_costs(from_date, to_date, cost_center=None, reference_doctype=None, reference_name=None):
	"""{"ok": True, "days": [{date, diesel_litres, diesel_cost, machine_hours}], "rows": [{allocation,
	machine, operator, operator_name, start_time, end_time, duration_hours, diesel_litres, diesel_cost,
	cost_center, reference_doctype, reference_name}]} for submitted allocations in the period.
	cost_center may be a name or a JSON list; a group includes the cost centres under it."""
	if not (_can(aa.ALLOCATION) or _can("Stock Entry")):
		frappe.throw(_("You are not permitted to see machine costs."), frappe.PermissionError)
	return aa.allocation_costs(from_date, to_date, cost_center or None, reference_doctype or None,
		reference_name or None)


# ---------------------------------------------------------------- machines

def _rights() -> dict:
	return {
		"can_manage": _can(aa.MACHINE, "write") and _can(aa.MACHINE, "create"),
		"can_allocate": _can(aa.ALLOCATION, "create"),
		"can_submit": _can(aa.ALLOCATION, "submit"),
	}


def _settings() -> dict:
	return {
		"fuel_warehouse": aa.fuel_warehouse(),
		"feedlot_cost_center": frappe.db.get_single_value("Production Settings", "feedlot_cost_center"),
	}


@frappe.whitelist(methods=["POST"])
@run
def list_machines(include_disabled=0):
	"""{ok, machines: [...with open_allocation and last position], machine_types, settings, rights}."""
	_need_read()
	return {"ok": True, "machines": aa.machines(bool(cint(include_disabled))), "machine_types": list(aa.MACHINE_TYPES),
		"settings": _settings(), **_rights()}


@frappe.whitelist(methods=["POST"])
@run
def save_machine(data):
	"""Create or update a machine: {name?, machine_name, machine_type, asset?, fuel_item?,
	default_cost_center?, disabled?, notes?}. The QR token is set once, on creation, and never
	changes (it is printed on the label)."""
	data = as_dict(data) or {}
	values = {k: data.get(k) for k in MACHINE_FIELDS if k in data}
	for k in ("asset", "fuel_item", "default_cost_center", "notes"):
		if k in values and not values[k]:
			values[k] = None
	if data.get("name"):
		_need(aa.MACHINE, "write")
		doc = frappe.get_doc(aa.MACHINE, data["name"])
		doc.update(values)
		doc.save()
	else:
		_need(aa.MACHINE, "create")
		doc = frappe.get_doc({"doctype": aa.MACHINE, **values})
		doc.insert()
	return {"ok": True, "name": doc.name}


def _label(row) -> dict:
	url = qr.scan_url(row.qr_code)
	return {"machine": row.name, "machine_name": row.machine_name, "machine_type": row.machine_type,
		"qr_code": row.qr_code, "url": url, "image": qr.qr_data_uri(url)}


@frappe.whitelist(methods=["POST"])
@run
def machine_qr(machine):
	"""The machine's label: {machine, machine_name, machine_type, qr_code (token), url (what the QR
	encodes), image (data: URI)}."""
	_need_read()
	row = frappe.db.get_value(aa.MACHINE, machine, ["name", "machine_name", "machine_type", "qr_code"], as_dict=True)
	if not row:
		frappe.throw(_("Machine {0} not found").format(machine), frappe.DoesNotExistError)
	if not row.qr_code:  # a machine made before tokens existed (or by data import)
		_need(aa.MACHINE, "write")
		row.qr_code = aa.new_token()
		frappe.db.set_value(aa.MACHINE, row.name, "qr_code", row.qr_code)
	return {"ok": True, **_label(row)}


@frappe.whitelist(methods=["POST"])
@run
def machine_labels(machines=None):
	"""Labels for printing: the named machines (a JSON list), else every enabled one."""
	_need_read()
	names = as_dict(machines) if isinstance(machines, str) else machines
	filters = {"name": ("in", names)} if names else {"disabled": 0}
	rows = frappe.get_all(aa.MACHINE, filters=filters, fields=["name", "machine_name", "machine_type", "qr_code"],
		order_by="machine_name asc")
	missing = [r for r in rows if not r.qr_code]
	if missing:
		_need(aa.MACHINE, "write")
		for r in missing:
			r.qr_code = aa.new_token()
			frappe.db.set_value(aa.MACHINE, r.name, "qr_code", r.qr_code)
	return {"ok": True, "labels": [_label(r) for r in rows]}


# ---------------------------------------------------------------- allocating

def _employees():
	return [{"value": e.name, "label": e.employee_name or e.name}
		for e in frappe.get_all("Employee", filters={"status": "Active"}, fields=["name", "employee_name"],
			order_by="employee_name asc", limit_page_length=0)]


def _references() -> dict:
	units = [{"value": u.name, "label": u.name, "crop": u.crop, "cost_center": u.cost_center}
		for u in frappe.get_all("Production Unit", filters={"is_group": 0, "status": ("!=", "Retired")},
			fields=["name", "crop", "cost_center"], order_by="name asc", limit_page_length=0)]
	out = {"Production Unit": units}
	if frappe.db.exists("DocType", "Silage Cycle"):
		meta = frappe.get_meta("Silage Cycle")
		filters = {"docstatus": ("<", 2)}
		if meta.has_field("status"):
			filters["status"] = ("!=", "Closed")
		out["Silage Cycle"] = [{"value": n, "label": n} for n in frappe.get_all("Silage Cycle", filters=filters,
			pluck="name", order_by="creation desc", limit_page_length=200)]
	return out


@frappe.whitelist(methods=["POST"])
@run
def allocation_form():
	"""What the scan screen offers: machines, operators, targets, references, cost centres, the
	session user's own Employee (default operator), settings and rights."""
	_need_read()
	company_filter = {"is_group": 0, "disabled": 0}
	return {
		"ok": True,
		"machines": [{"value": m.name, "label": m.machine_name, "machine_type": m.machine_type,
			"busy": bool(m.open_allocation)} for m in aa.machines()],
		"employees": _employees(),
		"me": frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "name"),
		"allocated_to": list(aa.ALLOCATED_TO),
		"reference_doctypes": aa.REFERENCE_DOCTYPE,
		"references": _references(),
		"cost_centers": [{"value": c, "label": c} for c in frappe.get_all("Cost Center", filters=company_filter,
			pluck="name", order_by="name asc", limit_page_length=0)],
		"settings": _settings(),
		"now": str(now_datetime()),
		**_rights(),
	}


def _allocation_row(name) -> dict:
	row = frappe.db.get_value(aa.ALLOCATION, name, aa.ROW_FIELDS, as_dict=True)
	for k in ("start_time", "end_time"):
		row[k] = str(row[k]) if row.get(k) else None
	row["running_hours"] = aa.hours_between(row.start_time, now_datetime()) if not row.end_time else None
	return row


@frappe.whitelist(methods=["POST"])
@run
def scan_machine(code):
	"""Resolve a scanned code (label link or token): {ok, machine, open_allocation (row or null)}.
	The caller reads GPS at the scan and sends it with start_allocation / close_allocation."""
	_need_read()
	m = aa.machine_by_code(code)
	open_name = aa.open_allocation(m.name)
	m["last_seen_at"] = str(m.last_seen_at) if m.last_seen_at else None
	return {"ok": True, "machine": m, "open_allocation": _allocation_row(open_name) if open_name else None}


@frappe.whitelist(methods=["POST"])
@run
def start_allocation(data):
	"""Open an allocation by scan: {code, operator, allocated_to, reference_doctype?, reference_name?,
	cost_center?, latitude?, longitude?, accuracy?, notes?}. GPS is the fix read when the code was
	scanned; none is fine (the user refused location)."""
	_need(aa.ALLOCATION, "create")
	data = as_dict(data) or {}
	if not data.get("operator"):
		frappe.throw(_("Choose the operator"), frappe.ValidationError)
	doc = aa.start_allocation(data, scanned=True)
	return {"ok": True, "allocation": _allocation_row(doc.name)}


@frappe.whitelist(methods=["POST"])
@run
def close_allocation(data, allocation=None):
	"""Close by scan: {code (or allocation), latitude?, longitude?, accuracy?, diesel_litres?, notes?,
	submit?}. With submit, the diesel is issued from stock."""
	_need(aa.ALLOCATION, "write")
	data = as_dict(data) or {}
	doc = aa.close_allocation(allocation or data.get("allocation"), data)
	return {"ok": True, "allocation": _allocation_row(doc.name)}


@frappe.whitelist(methods=["POST"])
@run
def submit_allocation(allocation, diesel_litres=None):
	"""Submit a closed allocation (with its litres): posts the diesel Material Issue."""
	_need(aa.ALLOCATION, "submit")
	doc = aa.submit_allocation(allocation, diesel_litres)
	return {"ok": True, "allocation": _allocation_row(doc.name)}


@frappe.whitelist(methods=["POST"])
@run
def list_allocations(from_date=None, to_date=None, status=None, machine=None, allocated_to=None):
	"""{ok, rows, kpis, machines (last positions for the map), settings, rights}."""
	_need_read()
	rows = aa.list_allocations(from_date or None, to_date or None, status or None, machine or None,
		allocated_to or None)
	posted = [r for r in rows if r.docstatus == 1]
	kpis = {
		"open": sum(1 for r in rows if r.status == "Open"),
		"to_submit": sum(1 for r in rows if r.status == "Closed"),
		"hours": round(sum(flt(r.duration_hours) for r in posted), 2),
		"diesel_litres": round(sum(flt(r.diesel_litres) for r in posted), 2),
		"diesel_cost": round(sum(flt(r.diesel_cost) for r in posted), 2),
	}
	return {"ok": True, "from_date": str(getdate(from_date)) if from_date else None,
		"to_date": str(getdate(to_date)) if to_date else None, "rows": rows, "kpis": kpis,
		"machines": aa.machines(), "allocated_to": list(aa.ALLOCATED_TO), "settings": _settings(), **_rights()}
