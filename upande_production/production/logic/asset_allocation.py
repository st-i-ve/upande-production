"""Machines and their allocations: who ran which machine, where, for how long, on what diesel.

A Production Machine carries a stable QR token on its label. Scanning it opens a Production
Asset Allocation (the GPS fix read at that moment is stored as the start position); scanning
again closes it (a second fix, the end position). Litres are entered and the allocation is
submitted, which posts, in the same transaction, a **Material Issue** Stock Entry of the
machine's fuel item out of Production Settings' Fuel Warehouse, on the allocation's cost centre,
linked back by two custom fields on Stock Entry (see production/setup/stock_entry_fields.py).
Cancelling the allocation cancels that entry. The diesel cost is the entry's value, never a typed
price.

One open allocation per machine: a machine is in one place at a time.

``allocation_costs`` is what other apps (upande_livestock's cost per animal) read: diesel litres,
diesel cost and machine hours per day, plus the allocations behind them.
"""

from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.utils import flt, get_datetime, getdate, now_datetime

from upande_production.production.logic import geo, qr

MACHINE = "Production Machine"
ALLOCATION = "Production Asset Allocation"
MACHINE_TYPES = ("Tractor", "Chopper", "Mixer Wagon", "Shredder", "Backhoe", "Pickup", "Other")
ALLOCATED_TO = ("Feedlot", "Production Unit", "Silage Cycle", "Other")
# What an allocation's target names as its reference document, when it names one.
REFERENCE_DOCTYPE = {"Production Unit": "Production Unit", "Silage Cycle": "Silage Cycle"}
STOCK_ENTRY_TYPE = "Material Issue"


# ---------------------------------------------------------------- pure helpers

def hours_between(start, end) -> float:
	"""Hours from start to end, 2 decimals. 0 when either is missing."""
	if not start or not end:
		return 0.0
	return round((get_datetime(end) - get_datetime(start)).total_seconds() / 3600.0, 2)


def split_hours_by_day(start, end, from_date=None, to_date=None) -> dict[str, float]:
	"""{'YYYY-MM-DD': hours} of the time from start to end on each calendar day, clipped to
	[from_date, to_date] (inclusive dates) when given. A run over midnight is split at midnight."""
	if not start or not end:
		return {}
	start, end = get_datetime(start), get_datetime(end)
	if from_date:
		start = max(start, datetime.combine(getdate(from_date), datetime.min.time()))
	if to_date:
		end = min(end, datetime.combine(getdate(to_date) + timedelta(days=1), datetime.min.time()))
	out: dict[str, float] = {}
	cur = start
	while cur < end:
		midnight = datetime.combine(cur.date() + timedelta(days=1), datetime.min.time())
		stop = min(end, midnight)
		key = cur.date().isoformat()
		out[key] = round(out.get(key, 0.0) + (stop - cur).total_seconds() / 3600.0, 4)
		cur = stop
	return {k: round(v, 2) for k, v in out.items()}


def date_range(from_date, to_date) -> list[str]:
	d, end = getdate(from_date), getdate(to_date)
	out = []
	while d <= end:
		out.append(d.isoformat())
		d += timedelta(days=1)
	return out


def day_totals(from_date, to_date, hours_rows, diesel_rows) -> list[dict]:
	"""One row per day of the range (empty days included).

	hours_rows: [{start_time, end_time}] — machine hours split over the days they ran.
	diesel_rows: [{posting_date, litres, cost}] — diesel counted on the day it was issued.
	"""
	days = {d: {"date": d, "diesel_litres": 0.0, "diesel_cost": 0.0, "machine_hours": 0.0}
		for d in date_range(from_date, to_date)}
	for r in hours_rows:
		for d, h in split_hours_by_day(r.get("start_time"), r.get("end_time"), from_date, to_date).items():
			if d in days:
				days[d]["machine_hours"] += h
	for r in diesel_rows:
		d = getdate(r.get("posting_date")).isoformat() if r.get("posting_date") else None
		if d in days:
			days[d]["diesel_litres"] += flt(r.get("litres"))
			days[d]["diesel_cost"] += flt(r.get("cost"))
	for row in days.values():
		row["machine_hours"] = round(row["machine_hours"], 2)
		row["diesel_litres"] = round(row["diesel_litres"], 3)
		row["diesel_cost"] = round(row["diesel_cost"], 2)
	return list(days.values())


# ---------------------------------------------------------------- machines

def new_token() -> str:
	"""A short, unique token for a machine label (upper case, no look-alike ambiguity needed: it
	is read by a scanner, and typed only as a fallback)."""
	while True:
		token = frappe.generate_hash(length=10).upper()
		if not frappe.db.exists(MACHINE, {"qr_code": token}):
			return token


def ensure_qr_token(doc):
	if not doc.qr_code:
		doc.qr_code = new_token()


def validate_machine(doc):
	ensure_qr_token(doc)
	if doc.machine_type and doc.machine_type not in MACHINE_TYPES:
		frappe.throw(_("Machine type must be one of {0}").format(", ".join(MACHINE_TYPES)), frappe.ValidationError)
	if doc.fuel_item and not frappe.db.get_value("Item", doc.fuel_item, "is_stock_item"):
		frappe.throw(_("Fuel item {0} is not a stock item; diesel is issued from stock").format(doc.fuel_item),
			frappe.ValidationError)


def machine_by_code(code) -> frappe._dict:
	"""The machine a scanned (or typed) code names: its QR token, else its name. Throws when there
	is none or it is disabled."""
	token = qr.parse_scan_code(code)
	if not token:
		frappe.throw(_("Scan a machine's QR code"), frappe.ValidationError)
	fields = ["name", "machine_name", "machine_type", "fuel_item", "default_cost_center", "disabled", "qr_code",
		"last_latitude", "last_longitude", "last_seen_at"]
	row = frappe.db.get_value(MACHINE, {"qr_code": token}, fields, as_dict=True) \
		or frappe.db.get_value(MACHINE, {"qr_code": token.upper()}, fields, as_dict=True) \
		or frappe.db.get_value(MACHINE, token, fields, as_dict=True)
	if not row:
		frappe.throw(_("No machine has the code {0}").format(token), frappe.DoesNotExistError)
	if row.disabled:
		frappe.throw(_("Machine {0} is disabled").format(row.machine_name), frappe.ValidationError)
	return row


def open_allocation(machine: str, exclude: str | None = None) -> str | None:
	"""The machine's open allocation (draft, not yet ended), if any."""
	filters = {"machine": machine, "docstatus": 0, "end_time": ("is", "not set")}
	if exclude:
		filters["name"] = ("!=", exclude)
	return frappe.db.get_value(ALLOCATION, filters, "name", order_by="start_time desc")


def record_position(machine: str, fix, at=None):
	"""Store a scan's fix as the machine's last known position (no fix: nothing changes)."""
	if not fix:
		return
	frappe.db.set_value(MACHINE, machine, {"last_latitude": fix[0], "last_longitude": fix[1],
		"last_seen_at": get_datetime(at) if at else now_datetime()}, update_modified=False)


# ---------------------------------------------------------------- allocation document

def fuel_warehouse() -> str | None:
	return frappe.db.get_single_value("Production Settings", "fuel_warehouse")


def _reference_cost_center(doctype, name):
	if not (doctype and name) or not frappe.db.exists("DocType", doctype):
		return None
	if not frappe.get_meta(doctype).has_field("cost_center"):
		return None
	return frappe.db.get_value(doctype, name, "cost_center")


def default_cost_center(allocated_to, reference_doctype=None, reference_name=None, machine=None) -> str | None:
	"""The reference's own cost centre (a Production Unit's), else the Feedlot Cost Center from
	Production Settings for the feedlot, else the machine's default."""
	cc = _reference_cost_center(reference_doctype, reference_name)
	if not cc and allocated_to == "Feedlot":
		cc = frappe.db.get_single_value("Production Settings", "feedlot_cost_center")
	if not cc and machine:
		cc = frappe.db.get_value(MACHINE, machine, "default_cost_center")
	return cc or None


def validate_allocation(doc):
	machine = frappe.db.get_value(MACHINE, doc.machine, ["disabled", "fuel_item"], as_dict=True)
	if not machine:
		frappe.throw(_("Machine {0} not found").format(doc.machine), frappe.ValidationError)
	if machine.disabled and doc.is_new():
		frappe.throw(_("Machine {0} is disabled").format(doc.machine), frappe.ValidationError)
	if doc.allocated_to not in ALLOCATED_TO:
		frappe.throw(_("Allocated To must be one of {0}").format(", ".join(ALLOCATED_TO)), frappe.ValidationError)

	if doc.reference_name and not doc.reference_doctype:
		doc.reference_doctype = REFERENCE_DOCTYPE.get(doc.allocated_to)
	if doc.reference_doctype and not doc.reference_name:
		doc.reference_doctype = None
	expected = REFERENCE_DOCTYPE.get(doc.allocated_to)
	if doc.reference_doctype and expected and doc.reference_doctype != expected:
		frappe.throw(_("An allocation to {0} references a {1}, not a {2}").format(
			doc.allocated_to, expected, doc.reference_doctype), frappe.ValidationError)
	if doc.reference_doctype and not frappe.db.exists(doc.reference_doctype, doc.reference_name):
		frappe.throw(_("{0} {1} not found").format(doc.reference_doctype, doc.reference_name), frappe.ValidationError)

	doc.cost_center = doc.cost_center or default_cost_center(doc.allocated_to, doc.reference_doctype,
		doc.reference_name, doc.machine)
	if not doc.cost_center:
		frappe.throw(_("Choose the cost centre this machine's work is charged to"), frappe.ValidationError)
	doc.company = frappe.db.get_value("Cost Center", doc.cost_center, "company") or doc.company
	doc.fuel_item = doc.fuel_item or machine.fuel_item

	doc.start_time = doc.start_time or now_datetime()
	if doc.end_time and get_datetime(doc.end_time) < get_datetime(doc.start_time):
		frappe.throw(_("The allocation ends before it starts"), frappe.ValidationError)
	if doc.end_time and get_datetime(doc.end_time) > now_datetime() + timedelta(minutes=5):
		frappe.throw(_("The end time is in the future"), frappe.ValidationError)
	doc.duration_hours = hours_between(doc.start_time, doc.end_time)
	if flt(doc.diesel_litres) < 0:
		frappe.throw(_("Diesel litres cannot be negative"), frappe.ValidationError)

	if not doc.end_time:
		other = open_allocation(doc.machine, exclude=None if doc.is_new() else doc.name)
		if other:
			frappe.throw(_("{0} is already allocated ({1}); close that allocation first").format(doc.machine, other),
				frappe.ValidationError)
	if doc.docstatus == 0:
		doc.status = "Closed" if doc.end_time else "Open"


def before_submit(doc):
	if not doc.end_time:
		frappe.throw(_("Close the allocation (end time) before submitting it"), frappe.ValidationError)
	if flt(doc.diesel_litres) > 0:
		if not doc.fuel_item:
			frappe.throw(_("Set the fuel item on machine {0}").format(doc.machine), frappe.ValidationError)
		if not fuel_warehouse():
			frappe.throw(_("Set the Fuel Warehouse in Production Settings"), frappe.ValidationError)
	doc.status = "Posted"


def _stock_entry(doc):
	warehouse = fuel_warehouse()
	end = get_datetime(doc.end_time)
	uom = frappe.db.get_value("Item", doc.fuel_item, "stock_uom")
	se = frappe.get_doc({
		"doctype": "Stock Entry", "stock_entry_type": STOCK_ENTRY_TYPE, "purpose": "Material Issue",
		"company": doc.company, "set_posting_time": 1, "posting_date": end.date(),
		"posting_time": end.time().strftime("%H:%M:%S"), "from_warehouse": warehouse,
		"production_asset_allocation": doc.name, "production_machine": doc.machine,
		"remarks": _("Diesel for {0} ({1}), operator {2}, {3} h").format(
			doc.machine, doc.name, doc.operator_name or doc.operator, doc.duration_hours),
		"items": [{
			"item_code": doc.fuel_item, "qty": flt(doc.diesel_litres), "uom": uom, "stock_uom": uom,
			"conversion_factor": 1, "s_warehouse": warehouse, "cost_center": doc.cost_center,
		}],
	})
	se.flags.ignore_permissions = True
	se.insert()
	se.submit()
	return se


def post_diesel(doc):
	"""on_submit: the diesel Material Issue (when litres were burnt) and its value on the allocation."""
	if flt(doc.diesel_litres) <= 0:
		doc.db_set({"diesel_stock_entry": None, "diesel_cost": 0}, update_modified=False)
		return
	se = _stock_entry(doc)
	cost = flt(frappe.db.get_value("Stock Entry", se.name, "total_outgoing_value"))
	doc.db_set({"diesel_stock_entry": se.name, "diesel_cost": cost}, update_modified=False)


def reverse_diesel(doc):
	"""before_cancel: cancel the diesel entry. The allocation links to it and Frappe refuses to
	cancel a linked document, so the link is dropped for the cancel and restored after (the
	cancelled allocation still shows its cancelled entry), as harvest.reverse_batch does."""
	if doc.diesel_stock_entry and frappe.db.get_value("Stock Entry", doc.diesel_stock_entry, "docstatus") == 1:
		se = frappe.get_doc("Stock Entry", doc.diesel_stock_entry)
		se.flags.ignore_permissions = True
		doc.db_set("diesel_stock_entry", None, update_modified=False)
		try:
			se.cancel()
		finally:
			doc.db_set("diesel_stock_entry", se.name, update_modified=False)


# ---------------------------------------------------------------- scan flow

def start_allocation(data: dict, scanned: bool = True):
	"""Open an allocation for the scanned machine. data: {code | machine, operator, allocated_to,
	cost_center?, reference_doctype?, reference_name?, latitude?, longitude?, accuracy?,
	scanned_at?, notes?}. The fix is the one read when the code was scanned."""
	data = frappe._dict(data or {})
	machine = machine_by_code(data.get("code") or data.get("machine"))
	current = open_allocation(machine.name)
	if current:
		frappe.throw(_("{0} is already allocated ({1}); scan again to close it").format(machine.machine_name, current),
			frappe.ValidationError)
	fix = geo.check_fix(data.get("latitude"), data.get("longitude"), data.get("accuracy"))
	at = get_datetime(data.get("scanned_at")) if data.get("scanned_at") else now_datetime()
	doc = frappe.get_doc({
		"doctype": ALLOCATION, "machine": machine.name, "allocated_to": data.get("allocated_to") or "Feedlot",
		"operator": data.get("operator"), "cost_center": data.get("cost_center") or None,
		"reference_doctype": data.get("reference_doctype") or None, "reference_name": data.get("reference_name") or None,
		"start_time": at, "scanned": 1 if scanned else 0, "notes": data.get("notes") or None,
		"start_latitude": fix[0] if fix else None, "start_longitude": fix[1] if fix else None,
		"start_accuracy": fix[2] if fix else None,
	})
	doc.insert()
	record_position(machine.name, fix, at)
	return doc


def close_allocation(name: str | None, data: dict):
	"""Close an open allocation (named, or the scanned machine's open one): end time and the fix
	read at the closing scan, litres when known, and submit when asked (data.submit)."""
	data = frappe._dict(data or {})
	if not name:
		machine = machine_by_code(data.get("code") or data.get("machine"))
		name = open_allocation(machine.name)
		if not name:
			frappe.throw(_("{0} has no open allocation; scan it to start one").format(machine.machine_name),
				frappe.ValidationError)
	doc = frappe.get_doc(ALLOCATION, name)
	doc.check_permission("write")
	if doc.docstatus != 0:
		frappe.throw(_("{0} is already submitted").format(name), frappe.ValidationError)
	fix = geo.check_fix(data.get("latitude"), data.get("longitude"), data.get("accuracy"))
	at = get_datetime(data.get("scanned_at")) if data.get("scanned_at") else now_datetime()
	if not doc.end_time:
		doc.end_time = at
		if fix:
			doc.end_latitude, doc.end_longitude, doc.end_accuracy = fix
	elif data.get("end_time"):
		doc.end_time = get_datetime(data.get("end_time"))
	if data.get("diesel_litres") not in (None, ""):
		doc.diesel_litres = flt(data.get("diesel_litres"))
	if data.get("notes"):
		doc.notes = data.get("notes")
	doc.save()
	record_position(doc.machine, fix, at)
	if frappe.utils.cint(data.get("submit")):
		doc.submit()
	return doc


def submit_allocation(name: str, diesel_litres=None):
	doc = frappe.get_doc(ALLOCATION, name)
	if diesel_litres not in (None, ""):
		doc.diesel_litres = flt(diesel_litres)
		doc.save()
	doc.submit()
	return doc


# ---------------------------------------------------------------- reads

ROW_FIELDS = ["name", "machine", "machine_type", "allocated_to", "reference_doctype", "reference_name", "operator",
	"operator_name", "cost_center", "status", "docstatus", "start_time", "end_time", "duration_hours", "scanned",
	"start_latitude", "start_longitude", "start_accuracy", "end_latitude", "end_longitude", "end_accuracy",
	"diesel_litres", "diesel_stock_entry", "diesel_cost", "fuel_item", "notes"]


def _cost_centers(cost_center) -> list[str]:
	"""The named cost centre(s) and every cost centre under a group among them."""
	if not cost_center:
		return []
	if isinstance(cost_center, str):
		cost_center = frappe.parse_json(cost_center) if cost_center.strip().startswith("[") else [cost_center]
	out: set[str] = set()
	for cc in cost_center:
		bounds = frappe.db.get_value("Cost Center", cc, ["lft", "rgt"], as_dict=True)
		if not bounds:
			out.add(cc)
			continue
		out.update(frappe.get_all("Cost Center", filters={"lft": (">=", bounds.lft), "rgt": ("<=", bounds.rgt)},
			pluck="name"))
	return sorted(out)


def allocation_costs(from_date, to_date, cost_center=None, reference_doctype=None, reference_name=None) -> dict:
	"""Diesel and machine hours of submitted allocations in [from_date, to_date].

	days: every day of the range; diesel_litres / diesel_cost on the day the diesel was issued
	(the Stock Entry's posting date), machine_hours split over the calendar days the machine ran.
	rows: the submitted allocations that ran or were issued diesel in the range. diesel_cost is
	read from the Stock Entry (its outgoing value), so a repost of the ledger shows here.
	cost_center (a name or a list) includes the cost centres under a group.
	"""
	from_date, to_date = getdate(from_date), getdate(to_date)
	if to_date < from_date:
		frappe.throw(_("The period ends before it starts"), frappe.ValidationError)
	start = datetime.combine(from_date, datetime.min.time())
	end = datetime.combine(to_date + timedelta(days=1), datetime.min.time())
	conds = ["a.docstatus = 1", "a.start_time < %(end)s",
		"(ifnull(a.end_time, a.start_time) >= %(start)s or se.posting_date between %(from_date)s and %(to_date)s)"]
	params = {"start": start, "end": end, "from_date": from_date, "to_date": to_date}
	ccs = _cost_centers(cost_center)
	if cost_center and ccs:
		conds.append("a.cost_center in %(ccs)s")
		params["ccs"] = tuple(ccs)
	if reference_doctype:
		conds.append("a.reference_doctype = %(rdt)s")
		params["rdt"] = reference_doctype
	if reference_name:
		conds.append("a.reference_name = %(rn)s")
		params["rn"] = reference_name
	rows = frappe.db.sql(f"""
		select a.name as allocation, a.machine, a.operator, a.operator_name, a.start_time, a.end_time,
			a.duration_hours, a.diesel_litres, a.cost_center, a.reference_doctype, a.reference_name,
			a.allocated_to, se.name as stock_entry, se.posting_date, se.docstatus as se_docstatus,
			se.total_outgoing_value as se_value
		from `tab{ALLOCATION}` a
		left join `tabStock Entry` se on se.name = a.diesel_stock_entry
		where {" and ".join(conds)}
		order by a.start_time asc""", params, as_dict=True)

	out_rows, diesel = [], []
	for r in rows:
		posted = r.stock_entry and r.se_docstatus == 1
		cost = flt(r.se_value) if posted else 0.0
		litres = flt(r.diesel_litres) if posted else 0.0
		if posted:
			diesel.append({"posting_date": r.posting_date, "litres": litres, "cost": cost})
		out_rows.append({
			"allocation": r.allocation, "machine": r.machine, "operator": r.operator, "operator_name": r.operator_name,
			"start_time": str(r.start_time) if r.start_time else None, "end_time": str(r.end_time) if r.end_time else None,
			"duration_hours": flt(r.duration_hours), "diesel_litres": litres, "diesel_cost": round(cost, 2),
			"cost_center": r.cost_center, "reference_doctype": r.reference_doctype, "reference_name": r.reference_name,
		})
	return {"ok": True, "days": day_totals(from_date, to_date, rows, diesel), "rows": out_rows}


def list_allocations(from_date=None, to_date=None, status=None, machine=None, allocated_to=None, limit=500) -> list[dict]:
	"""Allocations newest first, for the Allocations page. Open ones are always listed; the others
	when they started in [from_date, to_date]. status: Open · Closed · Posted · Cancelled."""
	filters = {"docstatus": 2} if status == "Cancelled" else {"docstatus": ("<", 2)}
	if status and status != "Cancelled":
		filters["status"] = status
	if machine:
		filters["machine"] = machine
	if allocated_to:
		filters["allocated_to"] = allocated_to
	lo = datetime.combine(getdate(from_date), datetime.min.time()) if from_date else None
	hi = datetime.combine(getdate(to_date) + timedelta(days=1), datetime.min.time()) if to_date else None
	out = []
	for r in frappe.get_all(ALLOCATION, filters=filters, fields=ROW_FIELDS, order_by="start_time desc", limit=limit):
		is_open = r.docstatus == 0 and not r.end_time
		started = get_datetime(r.start_time) if r.start_time else None
		if not is_open and started and ((lo and started < lo) or (hi and started >= hi)):
			continue
		for k in ("start_time", "end_time"):
			r[k] = str(r[k]) if r.get(k) else None
		r["running_hours"] = hours_between(r.start_time, now_datetime()) if is_open else None
		out.append(r)
	return out


def machines(include_disabled=False) -> list[dict]:
	"""Every machine with its open allocation (if any) and last known position."""
	filters = {} if include_disabled else {"disabled": 0}
	rows = frappe.get_all(MACHINE, filters=filters, fields=["name", "machine_name", "machine_type", "asset",
		"fuel_item", "default_cost_center", "qr_code", "disabled", "last_latitude", "last_longitude", "last_seen_at",
		"notes"], order_by="machine_name asc")
	open_rows = {r.machine: r for r in frappe.get_all(ALLOCATION,
		filters={"docstatus": 0, "end_time": ("is", "not set")},
		fields=["name", "machine", "operator", "operator_name", "allocated_to", "reference_name", "start_time"])}
	for r in rows:
		o = open_rows.get(r.name)
		r["last_seen_at"] = str(r.last_seen_at) if r.last_seen_at else None
		r["has_position"] = bool(r.last_latitude or r.last_longitude)
		r["open_allocation"] = {
			"name": o.name, "operator": o.operator, "operator_name": o.operator_name, "allocated_to": o.allocated_to,
			"reference_name": o.reference_name, "start_time": str(o.start_time),
			"running_hours": hours_between(o.start_time, now_datetime()),
		} if o else None
	return rows
