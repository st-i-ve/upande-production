# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

LOCKED = ("Active", "Superseded", "Pending Approval", "Rejected")


def _row(r, key):
	return r.get(key) if hasattr(r, "get") else getattr(r, key, None)


def _types(rows):
	ops = {_row(r, "operation") for r in rows if _row(r, "operation")}
	if not ops:
		return {}
	return dict(frappe.get_all("Production Operation", filters={"name": ["in", list(ops)]},
		fields=["name", "activity_type"], as_list=True))


def validate_tables(doc) -> None:
	"""Check the key, cultural and capital tables (the old `steps` table is not checked)."""
	err = lambda msg: frappe.throw(msg, frappe.ValidationError)
	key = doc.get("key_activities") or []
	cultural = doc.get("cultural_activities") or []
	capital = doc.get("capital_activities") or []
	types = _types(list(key) + list(cultural) + list(capital))

	prev = None
	for i, r in enumerate(key, 1):
		week = cint(_row(r, "week"))
		if week < 1:
			err(_("Key activities row {0}: week must be 1 or more").format(i))
		if prev and week < prev[1]:
			err(_("Row {0} (week {1}) comes after row {2} (week {3}). List key activities in the order of their week.")
				.format(i, week, prev[0], prev[1]))
		prev = (i, week)
		if types.get(_row(r, "operation")) == "Capital":
			err(_("Key activities row {0}: {1} is a Capital activity").format(i, _row(r, "operation")))

	for i, r in enumerate(cultural, 1):
		interval = cint(_row(r, "interval_weeks"))
		if _row(r, "schedule") == "Interval" and interval < 1:
			err(_("Cultural activities row {0}: an Interval activity needs Interval (weeks)").format(i))
		if _row(r, "schedule") == "As needed" and interval:
			err(_("Cultural activities row {0}: an As needed activity cannot have an interval").format(i))
		if types.get(_row(r, "operation")) == "Capital":
			err(_("Cultural activities row {0}: {1} is a Capital activity").format(i, _row(r, "operation")))

	for i, r in enumerate(capital, 1):
		op = _row(r, "operation")
		if op in types and types[op] != "Capital":
			err(_("Capital activities row {0}: {1} is not a Capital activity").format(i, op))


class ProductionProtocol(Document):
	def validate(self):
		validate_tables(self)
		if not self.protocol_family:
			self.protocol_family = self.protocol_name
		if self.is_new() and frappe.flags.in_demo_seed and not self.previous_version:
			self.version_status = "Active"  # the demo's base protocols are v1 Active
		if self.variety:
			vcrop, vitem = frappe.db.get_value("Production Variety", self.variety, ["crop", "item"]) or (None, None)
			if vcrop and self.crop and vcrop != self.crop:
				frappe.throw(_("Variety {0} belongs to {1}, not {2}").format(self.variety, vcrop, self.crop),
					frappe.ValidationError)
			if not self.item:
				self.item = vitem
		if not self.version:
			self.version = 1
		if self.is_new():
			return
		# Only Drafts are editable; status moves are made by production/logic/protocols.py.
		if frappe.flags.in_patch or frappe.flags.in_demo_seed or self.flags.protocol_transition:
			return
		before = self.get_doc_before_save()
		if before and before.version_status in LOCKED:
			frappe.throw(
				_("{0} is {1} and cannot be edited. Create a new version instead.").format(
					self.name, before.version_status
				),
				frappe.ValidationError,
			)

