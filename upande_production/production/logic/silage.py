"""Silage production: a Silage Cycle grows forage on a field, chops and ensiles it into a pit.

Where its cost comes from (each read from the records that hold it, never typed twice):

* inputs - Material Issue Stock Entries against the cycle (Stock Entry.production_silage_cycle), valued
  from the stock ledger. Diesel issued for a machine allocation is not an input, even if tagged.
* diesel - submitted Production Asset Allocations whose reference is the cycle (their diesel_cost, the
  value of the allocation's own diesel issue). Read only when that doctype exists on the site.
* labour - the cycle's activity rows (workers x day rate, else the amount typed in), plus approved
  Casual Labour Work on the cycle's crop cycle, or on its field during the cycle.

Submitting the cycle closes it: the costs are frozen on the cycle and a Material Receipt of the silage item
is posted into the pit warehouse at total cost / ensiled kg. That is the price livestock pays for silage.
Cancelling the cycle cancels that receipt (ERPNext refuses if the silage has already been fed out).
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from upande_production.production.logic import silage_cost
from upande_production.production.logic.settings import get_company

DT = "Silage Cycle"
ALLOCATION_DT = "Production Asset Allocation"
OPEN_STATUSES = ("Planned", "Growing", "Harvesting", "Ensiled")
STATUSES = (*OPEN_STATUSES, "Closed", "Cancelled")
CROPS = ("Maize", "Napier", "Sorghum", "Other")


# ---------------------------------------------------------------- settings

def setting(field: str):
	return frappe.db.get_single_value("Production Settings", field)


def day_rate_default() -> float:
	return flt(setting("silage_labour_day_rate"))


def has_allocations() -> bool:
	"""Production Asset Allocation is built separately; the silage module works with or without it."""
	return bool(frappe.db.table_exists(ALLOCATION_DT))


# ---------------------------------------------------------------- validate

def validate_cycle(doc):
	if doc.docstatus == 0 and doc.status in ("Closed", "Cancelled"):
		# Closed is what submitting sets; a draft (or an amendment of a cancelled cycle) is still open
		doc.status = "Ensiled" if flt(doc.ensiled_kg) > 0 else "Planned"
	if doc.production_unit:
		unit = frappe.db.get_value("Production Unit", doc.production_unit,
			["crop", "company", "cost_center", "is_group"], as_dict=True)
		if not unit:
			frappe.throw(_("Field {0} not found").format(doc.production_unit), frappe.ValidationError)
		doc.production_crop = doc.production_crop or unit.crop
		doc.company = doc.company or unit.company
		doc.cost_center = doc.cost_center or unit.cost_center
	if doc.crop_cycle:
		cyc_unit = frappe.db.get_value("Production Crop Cycle", doc.crop_cycle, "unit")
		if doc.production_unit and cyc_unit and cyc_unit != doc.production_unit:
			frappe.throw(_("Crop cycle {0} is on {1}, not on {2}").format(doc.crop_cycle, cyc_unit, doc.production_unit),
				frappe.ValidationError)
	doc.company = doc.company or get_company()
	doc.pit_warehouse = doc.pit_warehouse or setting("silage_pit_warehouse")
	if flt(doc.ensiled_kg) < 0:
		frappe.throw(_("Ensiled kg cannot be negative"), frappe.ValidationError)
	rate = day_rate_default()
	start = getdate(doc.start_date) if doc.start_date else None
	for r in doc.activities or []:
		if start and r.date and getdate(r.date) < start:
			frappe.throw(_("Activity row {0} ({1}) is dated before the cycle starts on {2}").format(r.idx, r.activity, doc.start_date),
				frappe.ValidationError)
		if r.workers and r.workers < 0:
			frappe.throw(_("Activity row {0}: workers cannot be negative").format(r.idx), frappe.ValidationError)
		if r.workers and not flt(r.day_rate) and rate:
			r.day_rate = rate
		r.labour_cost = silage_cost.activity_labour(r.workers, r.day_rate, r.labour_cost)
	if not doc.title:
		where = f" - {doc.production_unit}" if doc.production_unit else ""
		doc.title = f"{doc.crop} silage{where} - {doc.start_date}"
	if doc.docstatus == 0:
		set_costs(doc, compute(doc))


# ---------------------------------------------------------------- cost sources

def window(doc) -> tuple:
	"""(from, to) dates the cycle covers: start date to the closing date, or to today while open."""
	return getdate(doc.start_date), getdate(doc.closed_on or today())


def _allocation_filter_sql() -> str:
	"""Diesel issued by a machine allocation is the allocation's cost, never an input."""
	if frappe.db.has_column("Stock Entry", "production_asset_allocation"):
		return "and ifnull(se.production_asset_allocation, '') = ''"
	return ""


def input_rows(name: str) -> list[dict]:
	"""Each item issued against the cycle (submitted Material Issues), valued from the stock ledger."""
	if not name or not frappe.db.has_column("Stock Entry", "production_silage_cycle"):
		return []
	return frappe.db.sql(f"""
		select se.name as stock_entry, se.posting_date, d.item_code, d.item_name, d.qty, d.uom,
			d.transfer_qty as stock_qty, d.stock_uom, d.s_warehouse as warehouse,
			coalesce((select -sum(sle.stock_value_difference) from `tabStock Ledger Entry` sle
				where sle.voucher_type = 'Stock Entry' and sle.voucher_no = se.name
				and sle.voucher_detail_no = d.name and sle.is_cancelled = 0), d.amount, 0) as amount
		from `tabStock Entry` se join `tabStock Entry Detail` d on d.parent = se.name
		where se.production_silage_cycle = %s and se.docstatus = 1 and se.purpose = 'Material Issue'
		{_allocation_filter_sql()}
		order by se.posting_date asc, se.name asc, d.idx asc""", (name,), as_dict=True)


def draft_input_entries(name: str) -> list[str]:
	if not name or not frappe.db.has_column("Stock Entry", "production_silage_cycle"):
		return []
	return frappe.get_all("Stock Entry", filters={"production_silage_cycle": name, "docstatus": 0}, pluck="name")


def allocation_rows(name: str) -> list[dict]:
	"""Machine work booked to the cycle: Production Asset Allocations referencing it (any docstatus < 2)."""
	if not name or not has_allocations():
		return []
	rows = frappe.get_all(ALLOCATION_DT,
		filters={"reference_doctype": DT, "reference_name": name, "docstatus": ("<", 2)},
		fields=["name", "machine", "operator", "start_time", "end_time", "duration_hours",
			"diesel_litres", "diesel_cost", "docstatus"],
		order_by="start_time asc")
	names = {r.operator for r in rows if r.operator}
	who = dict(frappe.get_all("Employee", filters={"name": ("in", list(names))}, fields=["name", "employee_name"],
		as_list=True)) if names else {}
	for r in rows:
		r["allocation"] = r.pop("name")
		r["operator_name"] = who.get(r.operator) or r.operator
		r["submitted"] = r.pop("docstatus") == 1
	return rows


def casual_labour_filters(doc) -> dict | None:
	"""Filters on Casual Labour Work that belong to the cycle, or None when none does."""
	if not doc.include_casual_labour:
		return None
	if doc.crop_cycle:
		return {"docstatus": 1, "cycle": doc.crop_cycle}
	if doc.production_unit and doc.start_date:
		frm, to = window(doc)
		return {"docstatus": 1, "unit": doc.production_unit, "work_date": ("between", [frm, to])}
	return None


def casual_labour_cost(doc) -> float:
	filters = casual_labour_filters(doc)
	if not filters:
		return 0.0
	return sum(flt(v) for v in frappe.get_all("Casual Labour Work", filters=filters, pluck="pay_value"))


def compute(doc) -> dict:
	"""The cycle's cost now, from its sources: {cost: {...}, diesel_litres, machine_hours}."""
	name = doc.name if not doc.is_new() else None
	inputs = sum(flt(r.amount) for r in input_rows(name))
	alloc = [r for r in allocation_rows(name) if r["submitted"]]
	labour = sum(flt(r.labour_cost) for r in doc.activities or [])
	cost = silage_cost.cycle_cost(inputs=inputs, diesel=sum(flt(r.diesel_cost) for r in alloc), labour=labour,
		casual_labour=casual_labour_cost(doc))
	return {"cost": cost, "diesel_litres": round(sum(flt(r.diesel_litres) for r in alloc), 3),
		"machine_hours": round(sum(flt(r.duration_hours) for r in alloc), 2)}


def set_costs(doc, c: dict):
	cost = c["cost"]
	doc.inputs_cost, doc.diesel_cost, doc.labour_cost = cost["inputs"], cost["diesel"], cost["labour"]
	doc.casual_labour_cost, doc.total_cost = cost["casual_labour"], cost["total"]
	doc.diesel_litres, doc.machine_hours = c["diesel_litres"], c["machine_hours"]
	doc.cost_per_kg = silage_cost.cost_per_kg(cost["total"], doc.ensiled_kg) or 0


def stored_costs(doc) -> dict:
	"""The frozen costs of a closed cycle (what the pit receipt was valued at)."""
	return {"cost": silage_cost.cycle_cost(inputs=doc.inputs_cost, diesel=doc.diesel_cost, labour=doc.labour_cost,
		casual_labour=doc.casual_labour_cost), "diesel_litres": flt(doc.diesel_litres), "machine_hours": flt(doc.machine_hours)}


# ---------------------------------------------------------------- closing

def kg_conversion(item: str) -> tuple[str, float]:
	"""(uom, stock units per that uom) to receive `item` in kilos. Throws when the item has no Kg."""
	stock_uom = frappe.db.get_value("Item", item, "stock_uom")
	if stock_uom == "Kg":
		return "Kg", 1.0
	cf = flt(frappe.db.get_value("UOM Conversion Detail", {"parent": item, "parenttype": "Item", "uom": "Kg"},
		"conversion_factor"))
	if cf <= 0:
		frappe.throw(_("Silage item {0} is stocked in {1}; give it a Kg conversion or stock it in Kg").format(item, stock_uom),
			frappe.ValidationError)
	return "Kg", cf


def before_close(doc):
	if not doc.silage_item:
		frappe.throw(_("Set the Silage Item before closing the cycle"), frappe.ValidationError)
	if not frappe.db.get_value("Item", doc.silage_item, "is_stock_item"):
		frappe.throw(_("Silage item {0} is not a stock item").format(doc.silage_item), frappe.ValidationError)
	if not doc.pit_warehouse:
		frappe.throw(_("Set the Pit Warehouse (or the Silage Pit Warehouse in Production Settings) before closing"),
			frappe.ValidationError)
	if flt(doc.ensiled_kg) <= 0:
		frappe.throw(_("Enter the ensiled kg before closing the cycle"), frappe.ValidationError)
	drafts = draft_input_entries(doc.name)
	if drafts:
		frappe.throw(_("Stock entries {0} against this cycle are still drafts; submit or delete them first").format(", ".join(drafts)),
			frappe.ValidationError)
	open_work = [r["allocation"] for r in allocation_rows(doc.name) if not r["submitted"]]
	if open_work:
		frappe.throw(_("Machine allocations {0} on this cycle are still open; close them first").format(", ".join(open_work)),
			frappe.ValidationError)
	doc.closed_on = doc.closed_on or today()
	if getdate(doc.closed_on) < getdate(doc.start_date):
		frappe.throw(_("The cycle cannot close before it starts"), frappe.ValidationError)
	set_costs(doc, compute(doc))
	doc.cost_per_kg = silage_cost.cost_per_kg(doc.total_cost, doc.ensiled_kg)
	doc.status = "Closed"


def post_pit_receipt(doc):
	"""on_submit: receive the ensiled kilos into the pit at total cost / ensiled kg."""
	uom, cf = kg_conversion(doc.silage_item)
	per_kg = flt(silage_cost.cost_per_kg(doc.total_cost, doc.ensiled_kg))
	rate = per_kg / cf  # basic_rate is per stock unit
	se = frappe.get_doc({
		"doctype": "Stock Entry", "stock_entry_type": "Material Receipt", "purpose": "Material Receipt",
		"company": doc.company or get_company(), "posting_date": doc.closed_on, "set_posting_time": 1,
		"to_warehouse": doc.pit_warehouse, "production_silage_cycle": doc.name,
		"remarks": _("Silage {0}: {1} kg ensiled at {2} per kg").format(doc.name, flt(doc.ensiled_kg), round(per_kg, 4)),
		"items": [{
			"item_code": doc.silage_item, "qty": flt(doc.ensiled_kg), "uom": uom, "conversion_factor": cf,
			"t_warehouse": doc.pit_warehouse, "cost_center": doc.cost_center, "basic_rate": rate,
			"set_basic_rate_manually": 1, "allow_zero_valuation_rate": 0 if rate else 1,
		}],
	})
	se.flags.ignore_permissions = True
	se.flags.silage_receipt = True
	se.insert()
	se.submit()
	doc.db_set({"receipt_stock_entry": se.name, "status": "Closed", "closed_on": doc.closed_on}, update_modified=False)


def reverse_pit_receipt(doc):
	"""before_cancel: cancel the pit receipt (the link is dropped for the cancel and put back after)."""
	if doc.receipt_stock_entry and frappe.db.get_value("Stock Entry", doc.receipt_stock_entry, "docstatus") == 1:
		se = frappe.get_doc("Stock Entry", doc.receipt_stock_entry)
		se.flags.ignore_permissions = True
		doc.db_set("receipt_stock_entry", None, update_modified=False)
		try:
			se.cancel()
		finally:
			doc.db_set("receipt_stock_entry", se.name, update_modified=False)


def check_stock_entry(se, method=None):
	"""Stock Entry before_submit: an entry tagged with a silage cycle is a Material Issue to an open cycle
	(the cycle's own pit receipt aside). A closed cycle's cost is frozen in its silage valuation."""
	cycle = se.get("production_silage_cycle")
	if not cycle or se.flags.get("silage_receipt"):
		return
	status = frappe.db.get_value(DT, cycle, ["docstatus", "receipt_stock_entry"], as_dict=True)
	if not status:
		frappe.throw(_("Silage cycle {0} not found").format(cycle), frappe.ValidationError)
	if status.receipt_stock_entry == se.name:
		return
	if se.purpose != "Material Issue":
		frappe.throw(_("Only a Material Issue can be booked to silage cycle {0}").format(cycle), frappe.ValidationError)
	if status.docstatus != 0:
		frappe.throw(_("Silage cycle {0} is closed; its cost is already in the silage valuation").format(cycle),
			frappe.ValidationError)


# ---------------------------------------------------------------- actions

def issue_inputs(cycle: str, items: list[dict], warehouse: str | None = None, posting_date=None):
	"""Issue inputs (seed, fertiliser, inoculant, sheeting) from stock against an open cycle: one submitted
	Material Issue. items: [{item_code, qty, uom?}]. Returns the Stock Entry."""
	doc = frappe.get_doc(DT, cycle)
	if doc.docstatus != 0:
		frappe.throw(_("Silage cycle {0} is closed").format(cycle), frappe.ValidationError)
	warehouse = warehouse or setting("silage_input_warehouse")
	if not warehouse:
		frappe.throw(_("Choose the store to issue from (or set the Silage Input Warehouse in Production Settings)"),
			frappe.ValidationError)
	rows = []
	for i, it in enumerate(items or [], start=1):
		code, qty = (it.get("item_code") or "").strip(), flt(it.get("qty"))
		if not code:
			continue
		if qty <= 0:
			frappe.throw(_("Line {0}: quantity of {1} must be above zero").format(i, code), frappe.ValidationError)
		stock_uom = frappe.db.get_value("Item", code, "stock_uom")
		if not stock_uom:
			frappe.throw(_("Item {0} not found").format(code), frappe.ValidationError)
		uom = it.get("uom") or stock_uom
		cf = 1.0 if uom == stock_uom else flt(frappe.db.get_value("UOM Conversion Detail",
			{"parent": code, "parenttype": "Item", "uom": uom}, "conversion_factor"))
		if cf <= 0:
			frappe.throw(_("Item {0} has no conversion from {1}").format(code, uom), frappe.ValidationError)
		rows.append({"item_code": code, "qty": qty, "uom": uom, "conversion_factor": cf, "s_warehouse": warehouse,
			"cost_center": doc.cost_center})
	if not rows:
		frappe.throw(_("Add at least one item to issue"), frappe.ValidationError)
	se = frappe.get_doc({
		"doctype": "Stock Entry", "stock_entry_type": "Material Issue", "purpose": "Material Issue",
		"company": doc.company or get_company(), "posting_date": posting_date or today(), "set_posting_time": 1,
		"from_warehouse": warehouse, "production_silage_cycle": doc.name,
		"remarks": _("Inputs for silage {0}").format(doc.title or doc.name), "items": rows,
	})
	se.insert()
	se.submit()
	return se


def close_cycle(cycle: str, ensiled_kg=None, closed_on=None, silage_item=None, pit_warehouse=None):
	doc = frappe.get_doc(DT, cycle)
	if doc.docstatus != 0:
		frappe.throw(_("Silage cycle {0} is already closed").format(cycle), frappe.ValidationError)
	if ensiled_kg is not None:
		doc.ensiled_kg = flt(ensiled_kg)
	if closed_on:
		doc.closed_on = closed_on
	if silage_item:
		doc.silage_item = silage_item
	if pit_warehouse:
		doc.pit_warehouse = pit_warehouse
	doc.save()
	doc.submit()
	return doc


# ---------------------------------------------------------------- read model

def _mask_labour(cost: dict, can_see_pay: bool) -> dict:
	if can_see_pay:
		return cost
	return {**cost, "labour": None, "casual_labour": None}


def cycle_summary(doc, can_see_pay: bool = True) -> dict:
	"""One cycle for a list: its fields, cost by kind (frozen when closed, live while open), cost per kg."""
	c = stored_costs(doc) if doc.docstatus == 1 else compute(doc)
	cost = c["cost"]
	kinds = silage_cost.by_kind(cost)
	if not can_see_pay:
		for k in kinds:
			if k["kind"] in ("labour", "casual_labour"):
				k["amount"] = k["share_pct"] = None
	return {
		"name": doc.name, "title": doc.title, "crop": doc.crop, "production_crop": doc.production_crop,
		"production_unit": doc.production_unit, "crop_cycle": doc.crop_cycle, "status": doc.status,
		"docstatus": doc.docstatus, "start_date": doc.start_date, "closed_on": doc.closed_on,
		"pit_warehouse": doc.pit_warehouse, "silage_item": doc.silage_item, "ensiled_kg": flt(doc.ensiled_kg),
		"cost": _mask_labour(cost, can_see_pay), "by_kind": kinds,
		"cost_per_kg": silage_cost.cost_per_kg(cost["total"], doc.ensiled_kg),
		"diesel_litres": c["diesel_litres"], "machine_hours": c["machine_hours"],
		"receipt_stock_entry": doc.receipt_stock_entry, "activities": len(doc.activities or []),
	}


def list_cycles(status: str | None = None, can_see_pay: bool = True) -> list[dict]:
	filters = {"docstatus": ("<", 2)}
	if status:
		filters = {"status": status} if status == "Cancelled" else {**filters, "status": status}
	names = frappe.get_all(DT, filters=filters, pluck="name", order_by="start_date desc, creation desc")
	return [cycle_summary(frappe.get_doc(DT, n), can_see_pay) for n in names]


def cycle_detail(name: str, can_see_pay: bool = True) -> dict:
	doc = frappe.get_doc(DT, name)
	out = cycle_summary(doc, can_see_pay)
	out["notes"] = doc.notes
	out["include_casual_labour"] = doc.include_casual_labour
	out["activity_rows"] = [{
		"name": r.name, "date": r.date, "activity": r.activity, "workers": r.workers,
		"day_rate": flt(r.day_rate) if can_see_pay else None,
		"labour_cost": flt(r.labour_cost) if can_see_pay else None, "notes": r.notes,
	} for r in sorted(doc.activities or [], key=lambda r: (str(r.date), r.idx))]
	out["inputs"] = input_rows(doc.name)
	out["draft_inputs"] = draft_input_entries(doc.name)
	out["allocations"] = allocation_rows(doc.name)
	out["allocations_available"] = has_allocations()
	return out


def overlaps(doc, frm, to) -> bool:
	"""The cycle ran during [frm, to]: started by `to` and not closed before `frm`."""
	start = getdate(doc.start_date)
	end = getdate(doc.closed_on) if doc.closed_on else None
	return start <= to and (end is None or end >= frm)


def cost_summary(from_date, to_date, can_see_pay: bool = True) -> dict:
	"""Cycles that ran in the window, each with its whole cost by kind, ensiled kg and cost per kg, and the
	totals (cost per kg weighted over cycles that ensiled anything). A cycle's cost is its whole cost: silage
	cost per kg only means something for the whole cycle."""
	frm, to = getdate(from_date), getdate(to_date)
	if frm > to:
		frappe.throw(_("From date is after to date"), frappe.ValidationError)
	names = frappe.get_all(DT, filters={"docstatus": ("<", 2), "start_date": ("<=", to)}, pluck="name",
		order_by="start_date asc")
	cycles = [cycle_summary(d, True) for d in (frappe.get_doc(DT, n) for n in names) if overlaps(d, frm, to)]
	totals = silage_cost.summarise(cycles)
	if not can_see_pay:
		for c in cycles:
			c["cost"] = _mask_labour(c["cost"], False)
			for k in c["by_kind"]:
				if k["kind"] in ("labour", "casual_labour"):
					k["amount"] = k["share_pct"] = None
		totals["cost"] = _mask_labour(totals["cost"], False)
	return {"from_date": str(frm), "to_date": str(to), "cycles": cycles, "totals": totals}


def pit_stock() -> list[dict]:
	"""Silage on hand: every (silage item, pit warehouse) a cycle names, plus the settings pit, from Bin."""
	pairs = {(r.silage_item, r.pit_warehouse) for r in frappe.get_all(DT,
		filters={"docstatus": ("<", 2), "silage_item": ("is", "set"), "pit_warehouse": ("is", "set")},
		fields=["silage_item", "pit_warehouse"])}
	default_pit = setting("silage_pit_warehouse")
	items = {i for i, _w in pairs}
	if default_pit:
		pairs.update((i, default_pit) for i in items)
	out = []
	for item, wh in sorted(pairs):
		b = frappe.db.get_value("Bin", {"item_code": item, "warehouse": wh},
			["actual_qty", "valuation_rate", "stock_value", "stock_uom"], as_dict=True) or {}
		info = frappe.db.get_value("Item", item, ["item_name", "stock_uom"], as_dict=True) or {}
		out.append({"item_code": item, "item_name": info.get("item_name") or item, "warehouse": wh,
			"qty": flt(b.get("actual_qty")), "stock_uom": b.get("stock_uom") or info.get("stock_uom"),
			"valuation_rate": flt(b.get("valuation_rate")), "stock_value": flt(b.get("stock_value"))})
	return out
