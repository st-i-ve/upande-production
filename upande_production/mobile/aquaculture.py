"""Mobile (field capture) endpoints for aquaculture supervisors. Same style as mobile/api.py:
payload via request JSON, result in frappe.response['data'].
"""
import frappe
from frappe.utils import add_days, nowdate

from upande_production.api import aquaculture as desk
from upande_production.production.logic import aquaculture as logic
from upande_production.mobile.api import _denied, _fail, _payload, _require, _run


@frappe.whitelist()
def aquacultureListPonds():
	"""Ponds with their growing batch, latest water reading and the last 7 days of feed and mortality."""
	if _denied(("Production Unit", "read"), ("Pond Stocking", "read")):
		return

	def go():
		out = []
		since = add_days(nowdate(), -6)
		for u in desk._pond_units():
			st = frappe.db.get_value("Pond Stocking", {"pond": u.name, "status": "Growing"},
				["name", "species", "stocking_date", "fingerlings_count"], as_dict=True)
			wq = frappe.get_all("Water Quality Reading", filters={"pond": u.name}, order_by="reading_datetime desc",
				limit_page_length=1, fields=["name", "reading_datetime", "out_of_band", "flag_notes", "measured", *desk.READING_FIELDS])
			feed = frappe.get_all("Pond Feeding Log", filters={"pond": u.name, "feed_date": (">=", since)}, pluck="kg_fed", limit_page_length=0)
			dead = frappe.get_all("Fish Mortality Log", filters={"pond": u.name, "mortality_date": (">=", since)}, pluck="dead_count", limit_page_length=0)
			out.append({"unit": u.name, "unit_name": u.unit_name, "stocking": st, "latest_reading": ({**wq[0], **logic.measured_values(wq[0], desk.READING_FIELDS)} if wq else None),
				"feed_7d_kg": round(sum(feed), 1), "dead_7d": sum(dead)})
		return out

	_run("aquacultureListPonds", go)


def _write(name, doctype, fn, required):
	if _denied((doctype, "create")):
		return
	data = _payload()
	err = _require(data, *required)
	if err:
		return _fail(err)
	_run(name, lambda: fn(data))


@frappe.whitelist()
def aquacultureSaveWaterReading():
	_write("aquacultureSaveWaterReading", "Water Quality Reading", desk.save_water_reading.__wrapped__, ["pond"])


@frappe.whitelist()
def aquacultureSaveFeeding():
	_write("aquacultureSaveFeeding", "Pond Feeding Log", desk.save_feeding.__wrapped__, ["pond", "kg_fed"])


@frappe.whitelist()
def aquacultureSaveMortality():
	_write("aquacultureSaveMortality", "Fish Mortality Log", desk.save_mortality.__wrapped__, ["pond", "dead_count"])


@frappe.whitelist()
def aquacultureSaveSampling():
	_write("aquacultureSaveSampling", "Fish Sampling Log", desk.save_sampling.__wrapped__, ["pond", "sample_date", "sample_size", "avg_weight_g"])
