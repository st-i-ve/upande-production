"""Convert the old `steps` table of every protocol into key and cultural activity rows.

A step that repeats (repeat_every_days > 0 and repeat_count > 1) becomes a cultural Interval activity
whose establishment period is the weeks before its first occurrence; any other step becomes a key
activity in the week it falls due. The old steps stay in place (hidden). Idempotent.
"""

import frappe
from frappe.utils import cint

ONCE_ONLY = ("planting", "gap filling")


def _offset_days(step, stage_starts):
	base = stage_starts.get(step.get("anchor_stage")) or 0 if step.get("anchor_stage") else 0
	return base + cint(step.get("day_offset"))


def convert(doc) -> dict:
	"""Add key / cultural rows to a protocol document from its steps. Returns {"key": n, "cultural": n}."""
	if isinstance(doc, str):
		doc = frappe.get_doc("Production Protocol", doc)
	if doc.get("key_activities") or doc.get("cultural_activities") or not doc.get("steps"):
		return {"key": 0, "cultural": 0}
	starts = {}
	if doc.get("variety"):
		starts = {s.stage: cint(s.start_day) for s in frappe.get_doc("Production Variety", doc.variety).stages}
	names = dict(frappe.get_all("Production Operation", filters={"name": ["in", [s.operation for s in doc.steps]]},
		fields=["name", "operation_name"], as_list=True))
	key, cultural = [], []
	for s in doc.steps:
		off = _offset_days(s, starts)
		if cint(s.repeat_every_days) > 0 and cint(s.repeat_count) > 1:
			cultural.append({"operation": s.operation, "schedule": "Interval",
				"interval_weeks": max(1, round(cint(s.repeat_every_days) / 7)),
				"establishment_period_weeks": max(0, off // 7), "planned_qty": s.planned_qty, "description": s.note})
		else:
			once = (names.get(s.operation) or "").strip().lower() in ONCE_ONLY
			key.append({"operation": s.operation, "week": max(1, off // 7 + 1),
				"repeats": "First cycle only" if once else "Every cycle", "planned_qty": s.planned_qty,
				"description": s.note})
	key.sort(key=lambda r: r["week"])
	doc.set("key_activities", key)
	doc.set("cultural_activities", cultural)
	doc.flags.protocol_transition = True
	doc.save(ignore_permissions=True)
	return {"key": len(key), "cultural": len(cultural)}


def execute():
	frappe.reload_doctype("Production Protocol")
	total = {"key": 0, "cultural": 0, "protocols": 0}
	for name in frappe.get_all("Production Protocol", pluck="name"):
		r = convert(frappe.get_doc("Production Protocol", name))
		if r["key"] or r["cultural"]:
			total["protocols"] += 1
			total["key"] += r["key"]
			total["cultural"] += r["cultural"]
	print(f"convert_protocol_steps: {total}")
