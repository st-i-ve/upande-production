# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class HoneyHarvestLog(Document):
	"""Every honey harvest is mirrored into Production Harvest (crop Apiary, kg) so Overview,
	Forecast and Costs read the same honey as the Honey Harvest page. One source of truth:
	this log is the one people edit; the Production Harvest row follows it."""

	def validate(self):
		self.crop = frappe.db.get_value("Production Unit", self.unit, "crop")
		if flt(self.honey_kg) <= 0:
			frappe.throw(_("Honey kg must be more than zero."))
		if self.moisture_pct and not (5 <= flt(self.moisture_pct) <= 40):
			frappe.throw(_("Moisture % must be between 5 and 40."))
		if flt(self.wax_kg) < 0:
			frappe.throw(_("Wax kg cannot be negative."))

	def on_update(self):
		self.sync_production_harvest()

	def on_trash(self):
		ph = self.production_harvest
		if ph and frappe.db.exists("Production Harvest", ph):
			frappe.delete_doc("Production Harvest", ph, ignore_permissions=True, force=True)

	def sync_production_harvest(self):
		vals = {
			"harvest_date": self.harvest_date, "unit": self.unit, "crop": self.crop,
			"item": "Honey" if frappe.db.exists("Item", "Honey") else None, "qty": flt(self.honey_kg),
			"uom": "Kg", "grade": f"Grade {self.grade}" if self.grade else None,
		}
		cycle = frappe.db.get_value(
			"Production Crop Cycle", {"unit": self.unit, "status": ("not in", ("Closed", "Cancelled"))}, "name"
		)
		if cycle:
			vals["cycle"] = cycle
		if self.production_harvest and frappe.db.exists("Production Harvest", self.production_harvest):
			ph = frappe.get_doc("Production Harvest", self.production_harvest)
			ph.update(vals)
			ph.save(ignore_permissions=True)
		else:
			ph = frappe.get_doc({"doctype": "Production Harvest", **vals}).insert(ignore_permissions=True)
			self.db_set("production_harvest", ph.name, update_modified=False)
