"""Make the Production apps-screen tile a same-tab Workspace Sidebar icon.

Frappe's desktop.js get_route() only builds a relative /desk/<workspace>?sidebar=<label> route (no
target="_blank") for an App icon whose link_type is "Workspace Sidebar" and whose label matches the
sidebar name; an External icon is turned into an absolute URL and opened in a new tab. Idempotent.
"""

import frappe


def execute():
	if not frappe.db.exists("Desktop Icon", "Production"):
		return
	frappe.db.set_value("Desktop Icon", "Production", {
		"icon_type": "App", "link_type": "Workspace Sidebar", "link_to": "Production", "link": None,
		"label": "Production",
	})
