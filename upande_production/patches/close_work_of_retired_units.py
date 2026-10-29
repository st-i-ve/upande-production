import frappe


def execute():
	"""Close the open cycles and skip the open plan tasks of every unit already Retired."""
	from upande_production.production.logic.units import close_open_work, retired_units

	for unit in retired_units():
		close_open_work(unit)
