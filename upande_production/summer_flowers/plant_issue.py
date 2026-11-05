"""Whitelisted entry points for issuing plants to a planting.

The work lives in upande_propagation (it owns the plant stock). The desk buttons call these
production-level paths; each forwards to that app and says so plainly when it is not installed.
"""

import frappe
from frappe import _


def _forward(name, *args, **kwargs):
	from upande_production.summer_flowers.upstream import plant_issue as _pi

	try:
		fn = getattr(_pi, name)
	except ImportError:
		frappe.throw(_("Issuing plants needs the Upande Propagation app, which is not installed on this site."))
	return fn(*args, **kwargs)


@frappe.whitelist()
def issue_plants(planting, qty=None, on_date=None):
	return _forward("issue_plants", planting, qty=qty, on_date=on_date)


@frappe.whitelist()
def dispatch_to_block(planting, qty=None, on_date=None):
	return _forward("dispatch_to_block", planting, qty=qty, on_date=on_date)
