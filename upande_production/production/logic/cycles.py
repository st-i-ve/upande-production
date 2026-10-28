"""Which crops run in crop cycles. Bees and fish do not: they run in hives and ponds."""

import frappe

CYCLE_LINKS = [
	("Production Plan Task", "cycle"),
	("Value Adder Work", "cycle"),
	("Production Harvest", "cycle"),
	("Production Forecast", "cycle"),
	("Yield Sample", "cycle"),
]


def crop_uses_cycles(crop) -> bool:
	"""`crop` is a Production Crop name. Unknown crops default to using cycles."""
	if not crop:
		return True
	v = frappe.db.get_value("Production Crop", crop, "uses_crop_cycles")
	return True if v is None else bool(v)


def remove_cycles_for_cycleless_crops() -> int:
	"""Idempotent: delete Production Crop Cycle rows of crops that do not use cycles,
	clearing every link to them first so plans, work and harvests stay valid."""
	crops = frappe.get_all("Production Crop", filters={"uses_crop_cycles": 0}, pluck="name")
	if not crops:
		return 0
	cycles = frappe.get_all("Production Crop Cycle", filters={"crop": ("in", crops)}, pluck="name")
	if not cycles:
		return 0
	for dt, field in CYCLE_LINKS:
		frappe.db.sql(f"update `tab{dt}` set `{field}` = NULL where `{field}` in %s", (tuple(cycles),))
	frappe.db.sql("update `tabProduction Crop Cycle` set previous_cycle = NULL where previous_cycle in %s", (tuple(cycles),))
	for name in cycles:
		frappe.delete_doc("Production Crop Cycle", name, force=True, ignore_permissions=True)
	frappe.db.commit()
	return len(cycles)
