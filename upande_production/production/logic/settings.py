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


PAY_ROLES = {"Production Manager", "Production Supervisor", "System Manager", "Avocado Production Manager"}


def can_see_pay() -> bool:
	"""True for Administrator and the pay roles; Production Viewer and others never see rates or pay."""
	return frappe.session.user == "Administrator" or bool(PAY_ROLES & set(frappe.get_roles()))


def get_stale_days() -> int:
	val = frappe.db.get_single_value("Production Settings", "approval_stale_days")
	return int(val or 0) or 2  # unset (or 0) means the default of 2 days


MANAGE_ROLES = {"Production Manager", "System Manager", "Avocado Production Manager"}
SUPERVISE_ROLES = {"Production Supervisor"} | MANAGE_ROLES


def is_manager() -> bool:
	return frappe.session.user == "Administrator" or bool(MANAGE_ROLES & set(frappe.get_roles()))


def is_supervisor() -> bool:
	return frappe.session.user == "Administrator" or bool(SUPERVISE_ROLES & set(frappe.get_roles()))


AVOCADO_MANAGER_ROLE = "Avocado Production Manager"
AVOCADO_CROP_KEYS = {"avocado"}


def avocado_only_crop_keys():
	"""{'avocado'} when the user is limited to avocado, else an empty set (no limit).

	A user is limited when they hold Avocado Production Manager and no other role that already
	sees every crop. Administrator and System Manager are never limited.
	"""
	if frappe.session.user == "Administrator":
		return set()
	roles = set(frappe.get_roles())
	if AVOCADO_MANAGER_ROLE not in roles:
		return set()
	if roles & {"System Manager", "Production Manager", "Production Supervisor", "Production Viewer"}:
		return set()
	return set(AVOCADO_CROP_KEYS)


def crop_allowed(crop) -> bool:
	"""False when the user is avocado-only and `crop` (a Production Crop name) is another crop."""
	only = avocado_only_crop_keys()
	if not only or not crop:
		return True
	return frappe.db.get_value("Production Crop", crop, "crop_key") in only
