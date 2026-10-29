"""Field harvesting: crates scanned to a team, closed into a Harvest Batch, posted as stock.

A Harvest Batch (submittable) closes one team's open crates for one block. Submitting it, in the
same transaction, posts

* a Stock Entry of type "Harvesting" (Material Receipt) at the *estimated* weight: crates x average
  kg per crate, into the harvest warehouse, on the block's cost centre;
* a Production Harvest for the block (so Overview, Forecast, Block Costs update);
* Value Adder Work drafts per picker (qty = crates, uom Crate, Pending approval);
* for an avocado block, an Avocado Harvest Log row (the avocado pages read that doctype).

Cancelling the batch reverses all of it. Nothing here receives, weighs or packs the fruit.
"""

import frappe
from frappe.utils.nestedset import get_descendants_of
from frappe import _
from frappe.utils import flt, getdate, now_datetime, today

from upande_production.production.logic.analytics import current_cycles
from upande_production.production.logic.settings import get_company

OPEN_STATUSES = ("Filling", "Full")
STOCK_ENTRY_TYPE = "Harvesting"
BATCH_LOG_PREFIX = "harvest-batch:"  # client_ref of the Avocado Harvest Log a batch writes
DEFAULT_PICK_RATE = 30  # per crate, when a crop has no crate harvest operation yet


# ---------------------------------------------------------------- masters

def crate_crops() -> list[str]:
	"""Production Crops that harvest into crates (avocado, fruits & vegetables)."""
	return frappe.get_all("Production Crop", filters={"enabled": 1, "harvests_in_crates": 1}, pluck="name",
		order_by="sort_order, crop_name")


def resolve_farm(farm: str | None) -> str | None:
	"""A Farm by name, farm_name or abbreviation (the app sends its farm_name / farm_code)."""
	farm = (farm or "").strip()
	if not farm:
		return None
	if frappe.db.exists("Farm", farm):
		return farm
	return (frappe.db.get_value("Farm", {"farm_name": farm}) or frappe.db.get_value("Farm", {"abbreviation": farm}))


def crate_unit(unit: str) -> frappe._dict:
	"""The block (leaf Production Unit of a crate crop). Throws otherwise."""
	row = frappe.db.get_value(
		"Production Unit", unit, ["name", "crop", "farm", "company", "cost_center", "is_group", "avocado_block_code"], as_dict=True)
	if not row:
		frappe.throw(_("Block {0} not found").format(unit), frappe.ValidationError)
	if row.is_group:
		frappe.throw(_("{0} is a group; pick a block").format(unit), frappe.ValidationError)
	if not frappe.db.get_value("Production Crop", row.crop, "harvests_in_crates"):
		frappe.throw(_("{0} ({1}) is not harvested in crates").format(unit, row.crop), frappe.ValidationError)
	return row


def current_item(unit: str, crop: str) -> tuple[str, str | None]:
	"""(item, cycle) of the block's current cycle. Falls back to its latest cycle of any status."""
	cyc = current_cycles(crop).get(unit)
	if not (cyc and cyc.item):
		cyc = frappe.db.get_value("Production Crop Cycle", {"unit": unit, "item": ("is", "set")},
			["name", "item"], order_by="start_date desc", as_dict=True)
	if not (cyc and cyc.item):
		frappe.throw(_("Block {0} has no current cycle with an item; start a crop cycle first").format(unit),
			frappe.ValidationError)
	return cyc.item, cyc.name


def avg_kg_per_crate(item: str | None, crop: str | None) -> float:
	"""The item's own figure, else the crop's (Production Crop, Avg Kg per Crate). No figure is an
	error: a crate with no weight would book an invented quantity."""
	if item:
		v = flt(frappe.db.get_value("Item", item, "production_avg_kg_per_crate"))
		if v > 0:
			return v
	if crop:
		v = flt(frappe.db.get_value("Production Crop", crop, "avg_kg_per_crate"))
		if v > 0:
			return v
	frappe.throw(_("Set the Avg Kg per Crate on the item or on crop {0}").format(crop or ""),
		frappe.ValidationError)


def valuation_rate(item: str | None, crop: str | None) -> float:
	"""Per-kg value of a harvest: the item's valuation rate, else the latest buyer price (of the item,
	else of the crop), else the crop's own Price per Kg (Production Crop), else the Production Settings
	fallback, else 0 (a receipt is then booked with allow_zero_valuation_rate)."""
	v = flt(frappe.db.get_value("Item", item, "valuation_rate")) if item else 0
	if v > 0:
		return v
	for filters in ([{"item": item}] if item else []) + ([{}] if crop else []):
		if crop:
			filters = {**filters, "crop": crop}
		v = flt(frappe.db.get_value("Buyer Commitment", {**filters, "price_per_uom": (">", 0)}, "price_per_uom",
			order_by="week_start desc"))
		if v > 0:
			return v
	v = flt(frappe.db.get_value("Production Crop", crop, "price_per_kg")) if crop else 0
	if v > 0:
		return v
	return flt(frappe.db.get_single_value("Production Settings", "harvest_default_rate"))


def harvest_warehouse() -> str:
	wh = frappe.db.get_single_value("Production Settings", "harvest_warehouse")
	if not wh:
		frappe.throw(_("Set the Harvest Warehouse in Production Settings"), frappe.ValidationError)
	return wh


SCP_LOCATION_TYPES = ("Phase", "Pivot", "Section", "Block", "Farm")
BLOCKS_GROUP = "Production Blocks"


def block_warehouses() -> set[str]:
	"""Location warehouses, never harvest stores: those linked from a Production Unit (where chemicals
	and fertiliser are issued), SCP's location warehouses (Phase, Pivot, Section, Block, Farm) and
	anything under the "Production Blocks" group."""
	out = set(frappe.get_all("Production Unit", filters={"warehouse": ("is", "set")}, pluck="warehouse"))
	out.update(frappe.get_all("Warehouse", filters={"warehouse_type": ("in", SCP_LOCATION_TYPES)}, pluck="name"))
	for g in frappe.get_all("Warehouse", filters={"warehouse_name": BLOCKS_GROUP, "is_group": 1}, pluck="name"):
		out.update(get_descendants_of("Warehouse", g, ignore_permissions=True))
	return out


def stores(company: str | None = None) -> list[dict]:
	"""[{name, label}] - the stores a harvest may be received into: the company's non-group, enabled
	warehouses that are not block warehouses."""
	company = company or get_company()
	filters = {"is_group": 0, "disabled": 0}
	if company:
		filters["company"] = company
	blocks = block_warehouses()
	return [{"name": w.name, "label": w.warehouse_name or w.name} for w in frappe.get_all("Warehouse",
		filters=filters, fields=["name", "warehouse_name"], order_by="warehouse_name asc") if w.name not in blocks]


def default_store(farm: str | None = None) -> str:
	"""The last store a batch of the farm was received into (while it is still a valid store),
	else the Production Settings harvest warehouse."""
	if farm:
		last = frappe.get_all("Harvest Batch", filters={"farm": farm, "docstatus": 1, "warehouse": ("is", "set")},
			pluck="warehouse", order_by="creation desc", limit=5)
		blocks = block_warehouses()
		for wh in last:
			if wh not in blocks and frappe.db.get_value("Warehouse", wh, "disabled") == 0:
				return wh
	return harvest_warehouse()


def check_store(warehouse: str, company: str | None = None) -> str:
	"""Throws unless `warehouse` is a store a harvest may be received into."""
	row = frappe.db.get_value("Warehouse", warehouse, ["is_group", "disabled", "company"], as_dict=True)
	if not row:
		frappe.throw(_("Warehouse {0} not found").format(warehouse), frappe.ValidationError)
	if row.is_group or row.disabled:
		frappe.throw(_("{0} cannot receive stock; pick a store").format(warehouse), frappe.ValidationError)
	if company and row.company != company:
		frappe.throw(_("{0} belongs to {1}, not {2}").format(warehouse, row.company, company), frappe.ValidationError)
	if warehouse in block_warehouses():
		frappe.throw(_("{0} is a block warehouse; harvested fruit is received into a store").format(warehouse),
			frappe.ValidationError)
	return warehouse


def ensure_stock_entry_type() -> str:
	if not frappe.db.exists("Stock Entry Type", STOCK_ENTRY_TYPE):
		doc = frappe.get_doc({"doctype": "Stock Entry Type", "__newname": STOCK_ENTRY_TYPE,
			"purpose": "Material Receipt"})
		doc.flags.ignore_permissions = True
		doc.insert()
	return STOCK_ENTRY_TYPE


def new_warehouse(name: str, company: str | None = None, parent: str | None = None, farm: str | None = None,
		is_group: int = 0) -> str:
	"""Create (or return) the warehouse `<name> - <abbr>`; sets the custom farm field when another app makes it mandatory."""
	company = company or get_company()
	wh = f"{name} - {frappe.db.get_value('Company', company, 'abbr')}"
	if frappe.db.exists("Warehouse", wh):
		return wh
	doc = frappe.get_doc({"doctype": "Warehouse", "warehouse_name": name, "company": company, "is_group": is_group,
		"parent_warehouse": parent or frappe.db.get_value("Warehouse", {"company": company, "is_group": 1, "parent_warehouse": ("is", "not set")})})
	if frappe.get_meta("Warehouse").has_field("custom_farm"):
		doc.custom_farm = farm or frappe.db.get_value("Production Unit", {"company": company, "farm": ("is", "set")}, "farm")
	doc.insert(ignore_permissions=True)
	return doc.name


def ensure_harvest_warehouse(name: str = "Mutara Harvest Store", company: str | None = None) -> str:
	"""Create a warehouse under the company's group warehouse and make it the harvest warehouse
	when none is set. Returns the warehouse that Production Settings ends up using."""
	current = frappe.db.get_single_value("Production Settings", "harvest_warehouse")
	if current and frappe.db.exists("Warehouse", current):
		return current
	company = company or get_company()
	abbr = frappe.db.get_value("Company", company, "abbr")
	wh = f"{name} - {abbr}"
	if not frappe.db.exists("Warehouse", wh):
		parent = frappe.db.get_value("Warehouse", {"company": company, "is_group": 1, "parent_warehouse": ("is", "not set")})
		doc = frappe.get_doc({"doctype": "Warehouse", "warehouse_name": name, "company": company, "parent_warehouse": parent})
		if frappe.get_meta("Warehouse").has_field("custom_farm"):  # another app on the site makes the farm mandatory
			doc.custom_farm = frappe.db.get_value("Production Unit", {"company": company, "farm": ("is", "set")}, "farm")
		doc.insert(ignore_permissions=True)
	frappe.db.set_single_value("Production Settings", "harvest_warehouse", wh)
	return wh


def harvest_operation(crop: str) -> str:
	"""The crop's crate harvest operation (existing one with uom Crate), else a new "Harvesting"."""
	op = frappe.db.get_value("Production Operation", {"crop": crop, "is_harvest": 1, "work_uom": "Crate"})
	if op:
		return op
	op = frappe.db.get_value("Production Operation", {"crop": crop, "operation_name": "Harvesting"})
	if op:
		return op
	if not frappe.db.exists("UOM", "Crate"):
		frappe.get_doc({"doctype": "UOM", "uom_name": "Crate"}).insert(ignore_permissions=True)
	doc = frappe.get_doc({"doctype": "Production Operation", "crop": crop, "operation_name": "Harvesting",
		"category": "Harvesting", "work_uom": "Crate", "default_rate": DEFAULT_PICK_RATE, "is_harvest": 1})
	doc.insert(ignore_permissions=True)
	return doc.name


# ---------------------------------------------------------------- batch posting

def assign_pickers(rows, team: str):
	"""Crates scanned without a picker are shared evenly (round robin) over the team's members; a team
	with no members pays the leader."""
	members = [m for m in frappe.get_all("Harvest Team Member", filters={"parent": team, "parenttype": "Harvest Team"},
		pluck="employee", order_by="idx asc") if m]
	if not members:
		leader = frappe.db.get_value("Harvest Team", team, "team_leader")
		members = [leader] if leader else []
	i = 0
	for r in rows:
		if r.harvestor or not members:
			continue
		r.harvestor = members[i % len(members)]
		i += 1


def validate_batch(doc):
	unit = crate_unit(doc.unit)
	doc.crop, doc.farm = unit.crop, unit.farm
	if not doc.crates:
		frappe.throw(_("A harvest batch needs at least one crate"), frappe.ValidationError)
	seen = set()
	for r in doc.crates:
		scan = frappe.db.get_value("Harvest Crate Scan", r.crate_scan,
			["crate_id", "status", "block_ref", "team_id", "batch_id_ref", "harvestor"], as_dict=True) if r.crate_scan else None
		if not scan:
			frappe.throw(_("Row {0}: crate scan not found").format(r.idx), frappe.ValidationError)
		if r.crate_scan in seen:
			frappe.throw(_("Row {0}: {1} is listed twice").format(r.idx, scan.crate_id), frappe.ValidationError)
		seen.add(r.crate_scan)
		if scan.batch_id_ref and scan.batch_id_ref != doc.name:
			frappe.throw(_("Crate {0} is already in batch {1}").format(scan.crate_id, scan.batch_id_ref), frappe.ValidationError)
		if scan.status not in OPEN_STATUSES and scan.batch_id_ref != doc.name:
			frappe.throw(_("Crate {0} is {1}, not open").format(scan.crate_id, scan.status), frappe.ValidationError)
		if scan.block_ref != doc.unit:
			frappe.throw(_("Crate {0} was scanned for {1}, not {2}").format(scan.crate_id, scan.block_ref, doc.unit),
				frappe.ValidationError)
		r.crate_id = scan.crate_id
		r.harvestor = r.harvestor or scan.harvestor
	assign_pickers(doc.crates, doc.team)
	doc.crate_count = len(doc.crates)
	doc.item, doc.cycle = current_item(doc.unit, doc.crop)
	doc.avg_kg_per_crate = avg_kg_per_crate(doc.item, doc.crop)
	doc.estimated_kg = round(doc.crate_count * doc.avg_kg_per_crate, 3)
	doc.warehouse = check_store(doc.warehouse or default_store(doc.farm), unit.company)
	doc.cost_center = unit.cost_center
	doc.valuation_rate = valuation_rate(doc.item, doc.crop)
	doc.status = "Closed"
	doc.harvest_date = doc.harvest_date or today()


def _stock_entry(doc, company: str):
	ensure_stock_entry_type()
	rate = flt(doc.valuation_rate)
	se = frappe.get_doc({
		"doctype": "Stock Entry", "stock_entry_type": STOCK_ENTRY_TYPE, "purpose": "Material Receipt",
		"company": company, "posting_date": doc.harvest_date, "to_warehouse": doc.warehouse,
		"production_harvest_batch": doc.name,
		"remarks": _("Harvest {0}: {1} crate(s) from {2}, team {3}").format(doc.name, doc.crate_count, doc.unit, doc.team_number or doc.team),
		"items": [{
			"item_code": doc.item, "qty": doc.estimated_kg, "uom": "Kg", "stock_uom": "Kg", "conversion_factor": 1,
			"t_warehouse": doc.warehouse, "cost_center": doc.cost_center, "basic_rate": rate,
			"allow_zero_valuation_rate": 0 if rate else 1,
			"production_harvest_batch": doc.name, "production_unit": doc.unit, "production_crates": doc.crate_count,
		}],
	})
	se.flags.ignore_permissions = True
	se.insert()
	se.submit()
	return se


def _avocado_log(doc, pickers: int):
	"""The avocado pages read Avocado Harvest Log, so a batch on an avocado block writes one row
	(estimated kg). pickers_count is held inside the plausible kg-per-picker-day band so the row is
	not thrown out as a data problem: a batch is part of a day, not a picker-day."""
	code = frappe.db.get_value("Production Unit", doc.unit, "avocado_block_code")
	if not code or not frappe.db.exists("Avocado Yield Block", code):
		return None
	from upande_production.api.avocado_model import load_model
	lo, hi = load_model()["plausible_rate"]
	kg = flt(doc.estimated_kg)
	n = max(int(kg // hi) + (1 if kg % hi else 0), min(max(pickers, 1), max(int(kg // lo), 1)))
	log = frappe.get_doc({
		"doctype": "Avocado Harvest Log", "naming_series": "AHL-.YYYY.-.####", "harvest_date": doc.harvest_date,
		"orchard_block": code, "farm": doc.farm, "variety": doc.item, "total_kg": kg, "pickers_count": n,
		"bins_harvested": doc.crate_count, "status": "Batched (estimated)",
		"client_ref": BATCH_LOG_PREFIX + doc.name,
		"notes": f"Estimated from {doc.crate_count} crates x {doc.avg_kg_per_crate:g} kg ({doc.name}).",
	})
	log.insert(ignore_permissions=True)
	return log.name


def post_batch(doc):
	"""on_submit: stock entry, production harvest, picker work drafts, avocado log, crates -> Batched."""
	company = frappe.db.get_value("Production Unit", doc.unit, "company") or get_company()
	se = _stock_entry(doc, company)
	harvest = frappe.get_doc({
		"doctype": "Production Harvest", "harvest_date": doc.harvest_date, "unit": doc.unit, "crop": doc.crop,
		"cycle": doc.cycle, "item": doc.item, "qty": doc.estimated_kg, "uom": "Kg",
		"harvest_batch": doc.name, "stock_entry": se.name,
	})
	harvest.insert(ignore_permissions=True)

	per_picker: dict[str, int] = {}
	for r in doc.crates:
		if r.harvestor:
			per_picker[r.harvestor] = per_picker.get(r.harvestor, 0) + 1
	op = harvest_operation(doc.crop)
	for emp, n in per_picker.items():
		frappe.get_doc({
			"doctype": "Value Adder Work", "work_date": doc.harvest_date, "employee": emp, "unit": doc.unit,
			"cycle": doc.cycle, "operation": op, "qty": n, "uom": "Crate", "approval_status": "Pending",
			"harvest_batch": doc.name,
		}).insert(ignore_permissions=True)

	log = _avocado_log(doc, len(per_picker))
	for r in doc.crates:
		frappe.db.set_value("Harvest Crate Scan", r.crate_scan, {"status": "Batched", "batch_id_ref": doc.name})
	doc.db_set({"stock_entry": se.name, "production_harvest": harvest.name, "avocado_harvest_log": log},
		update_modified=False)


def reverse_batch(doc):
	"""before_cancel: undo everything the batch posted. Approved picker work blocks the cancel."""
	approved = frappe.get_all("Value Adder Work", filters={"harvest_batch": doc.name, "docstatus": 1}, pluck="name")
	if approved:
		frappe.throw(_("Picker work {0} is already approved; reject it before cancelling the batch").format(", ".join(approved)),
			frappe.ValidationError)
	if doc.stock_entry and frappe.db.get_value("Stock Entry", doc.stock_entry, "docstatus") == 1:
		se = frappe.get_doc("Stock Entry", doc.stock_entry)
		se.flags.ignore_permissions = True
		# the batch links to the entry and Frappe refuses to cancel a linked document: drop the link for the
		# cancel, then restore it so the cancelled batch still shows its (cancelled) stock entry
		doc.db_set("stock_entry", None, update_modified=False)
		try:
			se.cancel()
		finally:
			doc.db_set("stock_entry", se.name, update_modified=False)
	harvest, log = doc.production_harvest, doc.avocado_harvest_log
	doc.db_set({"production_harvest": None, "avocado_harvest_log": None}, update_modified=False)
	if harvest and frappe.db.exists("Production Harvest", harvest):
		frappe.delete_doc("Production Harvest", harvest, force=True, ignore_permissions=True)
	if log and frappe.db.exists("Avocado Harvest Log", log):
		frappe.delete_doc("Avocado Harvest Log", log, force=True, ignore_permissions=True)
	for name in frappe.get_all("Value Adder Work", filters={"harvest_batch": doc.name, "docstatus": 0}, pluck="name"):
		frappe.delete_doc("Value Adder Work", name, force=True, ignore_permissions=True)
	for r in doc.crates:  # the crates are open again, back with their team
		if r.crate_scan and frappe.db.exists("Harvest Crate Scan", r.crate_scan):
			frappe.db.set_value("Harvest Crate Scan", r.crate_scan, {"status": "Filling", "batch_id_ref": None})


# ---------------------------------------------------------------- closing a team's crates

def open_scans(team: str, unit: str) -> list[str]:
	return frappe.get_all("Harvest Crate Scan",
		filters={"team_id": team, "block_ref": unit, "status": ("in", OPEN_STATUSES)}, pluck="name",
		order_by="allocated_at asc, creation asc")


def close_batch(team: str, unit: str, harvest_date=None, warehouse: str | None = None):
	"""Close the team's open crates for the block into a submitted Harvest Batch (None if there are none).
	The stock is received into `warehouse` (a store), default `default_store(farm)`."""
	scans = open_scans(team, unit)
	if not scans:
		return None
	doc = frappe.get_doc({
		"doctype": "Harvest Batch", "team": team, "unit": unit, "harvest_date": harvest_date or today(),
		"crates": [{"crate_scan": s} for s in scans],
		"warehouse": warehouse or None,
	})
	doc.flags.ignore_permissions = True
	doc.insert()
	doc.submit()
	return doc
