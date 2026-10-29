import frappe


def execute():
	"""Give every site the default KPI bands once; a manager edits them in Settings > Bands."""
	frappe.reload_doc("production", "doctype", "production_band")
	frappe.reload_doc("production", "doctype", "production_settings")
	from upande_production.production.demo import bands_seed

	bands_seed.run(commit=False)
