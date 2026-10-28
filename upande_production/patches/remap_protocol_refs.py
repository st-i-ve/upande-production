"""Rewrite protocol_ref on Production Plan Tasks written before steps became key / cultural rows.

Old refs were `{cycle}:{step.name}:{k}`; new ones are `{cycle}:{row.name}:{k}`. A task whose ref points at
a row its cycle's protocol does not have is matched by operation and ISO week of its due date to the
occurrence the protocol schedules, and gets that occurrence's ref. Tasks with no match are left alone
(plans and analytics also match them by cycle + operation + week). Idempotent.
"""

import frappe
from frappe.utils import add_days, getdate

from upande_production.production.logic import schedule


def remap() -> dict:
	tasks = frappe.get_all("Production Plan Task", filters={"parenttype": "Production Work Plan",
		"cycle": ("is", "set"), "protocol_ref": ("is", "set")},
		fields=["name", "cycle", "operation", "due_date", "protocol_ref"])
	by_cycle = {}
	for t in tasks:
		by_cycle.setdefault(t.cycle, []).append(t)
	done = unmatched = 0
	for cycle, rows in by_cycle.items():
		cy = frappe.db.get_value("Production Crop Cycle", cycle, ["name", "protocol", "start_date", "cycle_no"],
			as_dict=True)
		if not (cy and cy.protocol and frappe.db.exists("Production Protocol", cy.protocol)):
			continue
		proto = frappe.get_doc("Production Protocol", cy.protocol)
		legacy = schedule.legacy_tasks(rows, cycle, proto)
		if not legacy:
			continue
		dues = [getdate(t.due_date) for t in legacy.values()]
		items = schedule.due_for_cycle(cy, proto, add_days(min(dues), -7), add_days(max(dues), 7))
		wanted = {}
		for it in items:
			wanted.setdefault((it["operation"], *schedule._week_key(it["due_date"])), it["ref"])
		taken = {t.protocol_ref for t in rows}
		for key, t in legacy.items():
			ref = wanted.get(key)
			if not ref or ref in taken:
				unmatched += 1
				continue
			frappe.db.set_value("Production Plan Task", t.name, "protocol_ref", ref, update_modified=False)
			taken.add(ref)
			done += 1
	return {"remapped": done, "unmatched": unmatched}


def execute():
	print(f"remap_protocol_refs: {remap()}")
