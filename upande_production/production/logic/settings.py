import frappe


def get_company() -> str | None:
	company = frappe.db.get_single_value("Production Settings", "company")
	if company:
		return company
	company = frappe.defaults.get_global_default("company")
	if company:
		return company
	companies = frappe.get_all("Company", pluck="name", limit=2)
	return companies[0] if len(companies) == 1 else (companies[0] if companies else None)


def get_tolerance_days() -> int:
	val = frappe.db.get_single_value("Production Settings", "late_tolerance_days")
	return 1 if val is None or val == "" else int(val)


PAY_ROLES = {"Production Manager", "Production Supervisor", "System Manager"}


def can_see_pay() -> bool:
	"""True for Administrator and the pay roles; Production Viewer and others never see rates or pay."""
	return frappe.session.user == "Administrator" or bool(PAY_ROLES & set(frappe.get_roles()))
