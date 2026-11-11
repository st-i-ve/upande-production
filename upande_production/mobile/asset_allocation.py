"""Mobile (field capture) endpoints for machine allocation by QR scan. Same conventions as
mobile/api.py: payload via request JSON (snake_case keys), result in frappe.response['data'],
a refusal or validation problem is {"error": msg}.

GPS: the phone reads ONE fix at the moment it scans a machine's QR code and sends it with the
start or close call (``latitude``, ``longitude``, ``accuracy`` in metres, ``scanned_at``), the
same fields SCP's field apps send. Nothing here asks for a track.
"""
import frappe

from upande_production.api import asset_allocation as desk
from upande_production.mobile.api import _denied, _fail, _payload, _require, _run
from upande_production.production.logic import asset_allocation as aa


@frappe.whitelist()
def productionListMachines():
	"""Machines with their open allocation and last position."""
	if _denied((aa.MACHINE, "read")):
		return
	_run("productionListMachines", lambda: aa.machines())


@frappe.whitelist()
def productionAllocationForm():
	"""Operators, targets, references, cost centres and the user's own Employee for the start sheet."""
	if _denied((aa.ALLOCATION, "read")):
		return

	def go():
		out = desk.allocation_form()
		if out.get("error"):
			raise frappe.ValidationError(out["error"])
		return out

	_run("productionAllocationForm", go)


@frappe.whitelist()
def productionScanMachine():
	"""{code} (the label's link or its token) -> {machine, open_allocation}. Open allocation present:
	the next call is productionCloseAllocation; absent: productionStartAllocation."""
	if _denied((aa.ALLOCATION, "read")):
		return
	data = _payload()
	err = _require(data, "code")
	if err:
		return _fail(err)

	def go():
		m = aa.machine_by_code(data["code"])
		name = aa.open_allocation(m.name)
		m["last_seen_at"] = str(m.last_seen_at) if m.last_seen_at else None
		return {"machine": m, "open_allocation": desk._allocation_row(name) if name else None}

	_run("productionScanMachine", go)


@frappe.whitelist()
def productionStartAllocation():
	"""{code, operator, allocated_to, reference_doctype?, reference_name?, cost_center?, latitude?,
	longitude?, accuracy?, scanned_at?, notes?} -> the new allocation."""
	if _denied((aa.ALLOCATION, "create")):
		return
	data = _payload()
	err = _require(data, "code", "operator")
	if err:
		return _fail(err)

	def go():
		doc = aa.start_allocation(data, scanned=True)
		frappe.db.commit()
		return {"status": "success", "name": doc.name, "allocation": desk._allocation_row(doc.name),
			"message": "Machine allocated."}

	_run("productionStartAllocation", go)


@frappe.whitelist()
def productionCloseAllocation():
	"""{code or allocation, latitude?, longitude?, accuracy?, scanned_at?, diesel_litres?, notes?,
	submit?} -> the closed (and, with submit, posted) allocation."""
	if _denied((aa.ALLOCATION, "write")):
		return
	data = _payload()
	if not (data.get("code") or data.get("allocation")):
		return _fail("Code is required.")

	def go():
		doc = aa.close_allocation(data.get("allocation"), data)
		frappe.db.commit()
		return {"status": "success", "name": doc.name, "allocation": desk._allocation_row(doc.name),
			"message": "Diesel issued." if doc.docstatus == 1 and doc.diesel_stock_entry else "Allocation closed."}

	_run("productionCloseAllocation", go)


@frappe.whitelist()
def productionListAllocations():
	"""{from_date?, to_date?, status?, machine?} -> allocations newest first (open ones always)."""
	if _denied((aa.ALLOCATION, "read")):
		return
	data = _payload()
	_run("productionListAllocations", lambda: aa.list_allocations(data.get("from_date"), data.get("to_date"),
		data.get("status"), data.get("machine"), data.get("allocated_to")))
