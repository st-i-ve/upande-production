# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from upande_production.production.logic.cycles import crop_uses_cycles
from upande_production.production.logic import cycle_chain, cycle_requests, cycle_setup, field_crops
from upande_production.production.logic.stages import apply_variety_defaults


CYCLE_DT = "Production Crop Cycle"
REQUEST_DT = "Production Cycle Change Request"


def recorded_in(cycle) -> list:
	"""The doctypes with a record that links to `cycle` (harvests, plan tasks, labour, samples ...), other than
	cycles and change requests: rows of child tables count (a Work Plan Task row), and so do links added by Custom
	Fields."""
	links = frappe.get_all("DocField", filters={"fieldtype": "Link", "options": CYCLE_DT, "parent": ("not in", (CYCLE_DT, REQUEST_DT))},
		fields=["parent", "fieldname"])
	links += frappe.get_all("Custom Field", filters={"fieldtype": "Link", "options": CYCLE_DT, "dt": ("not in", (CYCLE_DT, REQUEST_DT))},
		fields=["dt as parent", "fieldname"])
	return [df.parent for df in links if frappe.db.table_exists(df.parent) and frappe.db.exists(df.parent, {df.fieldname: cycle})]


def _recorded_against(cycle) -> bool:
	"""True when any record other than a cycle or a change request links to `cycle`."""
	return bool(recorded_in(cycle))


class ProductionCropCycle(Document):
	def validate(self):
		cycle_requests.guard(self)
		if self.unit:
			self.crop = frappe.db.get_value("Production Unit", self.unit, "crop")
		if self.crop and not crop_uses_cycles(self.crop):
			frappe.throw(f"{self.crop} does not use crop cycles.")
		self.set_field_crop()
		if self.is_new() or self.has_value_changed("previous_cycle") or not self.cycle_no:
			self.cycle_no = cycle_chain.cycle_number(self)
		cycle_chain.sync_actuals(self)
		apply_variety_defaults(self)
		if self.protocol and (self.is_new() or self.has_value_changed("protocol")) and not frappe.flags.in_demo_seed:
			if frappe.db.get_value("Production Protocol", self.protocol, "version_status") != "Active":
				frappe.throw(_("Only an Active protocol can be used for a cycle."), frappe.ValidationError)
		cycle_chain.set_flags(self)
		cycle_setup.warn_overlap(self)
		self.title = f"{self.unit} · {self.item or self.crop}"

	def on_update(self):
		if not self.proposed_next_cycle:
			cycle_chain.propose_next(self)

	def on_trash(self):
		"""A cycle and the next one proposed from it point at each other, so neither could be deleted. The proposed
		next cycle goes with this one while it is still only Planned and nothing records against it; otherwise it
		stays, as a first cycle. A cycle that proposed this one forgets it, so it can propose again."""
		nxt = self.proposed_next_cycle
		if nxt and frappe.db.exists(CYCLE_DT, nxt):
			frappe.db.set_value(CYCLE_DT, self.name, "proposed_next_cycle", None, update_modified=False)
			if frappe.db.get_value(CYCLE_DT, nxt, "status") == "Planned" and not _recorded_against(nxt):
				frappe.db.set_value(CYCLE_DT, nxt, "previous_cycle", None, update_modified=False)
				frappe.delete_doc(CYCLE_DT, nxt, ignore_permissions=True)
		for name in frappe.get_all(CYCLE_DT, filters={"previous_cycle": self.name}, pluck="name"):
			frappe.db.set_value(CYCLE_DT, name, "previous_cycle", None, update_modified=False)
		for name in frappe.get_all(CYCLE_DT, filters={"proposed_next_cycle": self.name}, pluck="name"):
			frappe.db.set_value(CYCLE_DT, name, "proposed_next_cycle", None, update_modified=False)

	def set_field_crop(self):
		"""The cycle's crop is its variety's; with no variety (an existing cycle given by item) it is the item's."""
		fc = field_crops.from_variety(self.variety) if self.variety else None
		if self.variety and not self.is_new() and self.has_value_changed("variety") and not self.has_value_changed("field_crop"):
			# the variety was changed on a saved cycle: crop and sub-crop follow the new variety
			self.field_crop = fc
			self.sub_crop = frappe.db.get_value("Production Variety", self.variety, "sub_crop")
		if not fc and not self.variety and not self.field_crop:
			fc = field_crops.from_item(self.item, self.crop)
		if not fc and not self.field_crop:
			fc = field_crops.only_crop(self.crop)  # a single-crop section (Avocado) fills its crop silently
		if fc and not self.field_crop:
			self.field_crop = fc  # a crop given that the variety disagrees with is refused below
		if self.variety and not self.sub_crop:
			self.sub_crop = frappe.db.get_value("Production Variety", self.variety, "sub_crop")
		field_crops.check_variety(self)
		if not frappe.flags.in_demo_seed:
			field_crops.require_on_cycle(self)
