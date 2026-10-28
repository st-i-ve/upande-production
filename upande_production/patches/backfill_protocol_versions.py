import frappe


def execute():
	"""Protocols that existed before versioning are Active v1 of their own family."""
	frappe.db.sql(
		"""update `tabProduction Protocol` set version = 1, version_status = 'Active',
		protocol_family = name where ifnull(protocol_family, '') = ''"""
	)
