"""Tagged-fruit dry matter monitoring (avocado): tag a fruit on a tree, record it again and again.

Read and write use the same role gates as the other avocado endpoints (api/avocado.py READ_ROLES / WRITE_ROLES:
Production Manager, Avocado Production Manager, System Manager, Agriculture Manager / User; reads also
Production Supervisor / Viewer). The mobile endpoints in mobile/api.py share the logic but gate on document rights.
"""

import frappe
from frappe import _

from upande_production.api.avocado import READ_ROLES, WRITE_ROLES
from upande_production.api.envelope import as_dict, run
from upande_production.production.logic import drymatter_monitor as mon


def _need(roles, what):
	if frappe.session.user == "Administrator" or roles & set(frappe.get_roles()):
		return
	frappe.throw(_("You are not permitted to {0} avocado dry matter readings.").format(what), frappe.PermissionError)


def _tag_of(doc):
	return mon.tag_row(doc, mon.crop_window(doc.crop)[0])


@frappe.whitelist(methods=["POST"])
@run
def get_monitor(crop, farm=None, unit=None):
	"""Blocks, tagged fruit with readings, fruit/tree/block series (weekly for tree and block), lab points, crop target and max."""
	_need(READ_ROLES, "see")
	return mon.monitor(crop, farm or None, unit or None)


@frappe.whitelist(methods=["POST"])
@run
def save_tag(data):
	"""Tag a fruit: {unit, tree_label, fruit_tag, tagged_on?, notes?, reading?: {first reading}}."""
	_need(WRITE_ROLES, "record")
	return _tag_of(mon.create_tag(as_dict(data) or {}, ignore_permissions=True))


@frappe.whitelist(methods=["POST"])
@run
def add_reading(tag, data):
	"""A reading on a tagged fruit: {reading_date, fresh_g?, dish_g?, dry_g?, machine_pct?, instrument?, notes?}."""
	_need(WRITE_ROLES, "record")
	return _tag_of(mon.add_reading(tag, as_dict(data) or {}, ignore_permissions=True))


@frappe.whitelist(methods=["POST"])
@run
def delete_reading(tag, reading):
	"""Remove a mistaken reading (`reading` is the row name)."""
	_need(WRITE_ROLES, "change")
	return _tag_of(mon.delete_reading(tag, reading, ignore_permissions=True))


@frappe.whitelist(methods=["POST"])
@run
def update_tag(tag, status=None, notes=None):
	"""Mark a fruit Harvested / Lost / Active again, or change its notes."""
	_need(WRITE_ROLES, "change")
	return _tag_of(mon.update_tag(tag, status, notes, ignore_permissions=True))
