"""The "Avocado Production Manager" role: full production transactions on avocado, nothing else.

The role only carries document rights. "Avocado only" comes from User Permissions on the user
(Production Crop = Avocado, Farm, Company); the app also limits the crop switcher for a user whose
only production role is this one (see settings.avocado_only_crop_keys).

Rights are applied as Custom DocPerm (the doctype's standard rows are copied first, so no other role
loses anything). A doctype that was renamed is listed under every
name it has had; the first one that exists on the site is used.
"""

import frappe

ROLE = "Avocado Production Manager"
ROLE_PROFILE = "Avocado Production Manager Profile"

FULL = ("read", "write", "create", "delete", "report", "export", "print", "email", "share")
SUBMIT = FULL + ("submit", "cancel", "amend")
READ = ("read",)
READ_REPORT = ("read", "report", "export", "print")
LEVEL1 = ("read", "write")  # permlevel 1 fields on plans, field operations and casual labour

# (doctype names it has had, rights at permlevel 0, rights at permlevel 1)
PERMS = [
	# production transactions
	(("Production Crop Cycle",), FULL, None),
	(("Production Work Plan",), FULL, LEVEL1),
	(("Field Operation", "Field Activity"), FULL, LEVEL1),
	(("Casual Labour Work", "Value Adder Work"), SUBMIT, LEVEL1),
	(("Production Harvest",), FULL, None),
	(("Harvest Batch",), SUBMIT, None),
	(("Harvest Crate",), FULL, None),
	(("Harvest Crate Scan",), FULL, None),
	(("Harvest Grading Log",), FULL, None),
	(("Harvest Team",), FULL, None),
	(("Yield Sample",), FULL, None),
	(("Dry Matter Test",), FULL, None),
	(("Buyer Commitment",), FULL, None),
	(("Dry Matter Fruit Tag",), FULL, None),
	(("Crop Forecast", "Production Forecast"), FULL, None),
	(("Block Establishment Cost",), SUBMIT, None),
	(("Block Opening Balance",), FULL, None),
	(("Production Protocol",), FULL, None),
	(("Production Activity Rule",), FULL, None),
	(("Pivot Irrigation Run",), FULL, None),
	# the avocado yield module
	(("Avocado Harvest Log",), FULL, None),
	(("Avocado Production Forecast",), FULL, None),
	(("Avocado Production Budget",), FULL, None),
	(("Avocado Yield Block",), FULL, None),
	(("Avocado Yield History",), FULL, None),
	(("Avocado Maturity Test",), FULL, None),
	(("Avocado Ripening Test",), FULL, None),
	(("Avocado Fruit Count",), FULL, None),
	# the stock the harvest flow posts
	(("Stock Entry",), SUBMIT, None),
	(("Stock Ledger Entry",), READ_REPORT, None),
	(("Bin",), READ_REPORT, None),
	(("Stock Entry Type",), READ, None),
	# reference data
	(("Production Crop",), READ, None),
	(("Production Variety",), READ, None),
	(("Production Unit",), READ_REPORT, None),
	(("Production Settings",), READ, None),
	(("Production Band",), READ, None),
	(("Production Grade",), READ, None),
	(("Production Capital Account",), READ, None),
	(("Production Crop Count Size",), READ, None),
	(("Farm",), READ, None),
	(("Item",), READ, None),
	(("Item Group",), READ, None),
	(("Warehouse",), READ, None),
	(("Employee",), READ, None),
	(("UOM",), READ, None),
	(("Cost Center",), READ, None),
	(("Company",), READ, None),
]


def doctype_for(names):
	for n in names:
		if frappe.db.exists("DocType", n):
			return n
	return None


def ensure_role():
	if not frappe.db.exists("Role", ROLE):
		frappe.get_doc({"doctype": "Role", "role_name": ROLE, "desk_access": 1}).insert(ignore_permissions=True)


def ensure_role_profile():
	"""A Role Profile with the role, so a user's profile-driven role sync keeps it (a bare Has Role row
	is dropped whenever a user with a role profile is saved). Add it to the user's role profiles."""
	if not frappe.db.exists("Role Profile", ROLE_PROFILE):
		frappe.get_doc({"doctype": "Role Profile", "role_profile": ROLE_PROFILE, "roles": [{"role": ROLE}]}).insert(
			ignore_permissions=True
		)


def _ensure_custom_perms(dt):
	"""Copy the doctype's standard rows to Custom DocPerm once (Frappe then ignores the standard rows).

	Done by hand rather than with frappe.permissions.add_permission, which validates the whole doctype's
	permission table and refuses a doctype that already carries an invalid row (Avocado Production
	Forecast has an Import flag on a non-importable doctype)."""
	if frappe.db.exists("Custom DocPerm", {"parent": dt}):
		return
	for d in frappe.get_all("DocPerm", fields="*", filters={"parent": dt}):
		frappe.new_doc("Custom DocPerm").update(d).insert(ignore_permissions=True)


def ensure_permissions():
	"""Create or top up the role's Custom DocPerm rows. Idempotent. Returns the doctypes touched."""
	done = []
	for names, rights, level1 in PERMS:
		dt = doctype_for(names)
		if not dt:
			continue
		for permlevel, rs in ((0, rights), (1, level1)):
			if not rs:
				continue
			_ensure_custom_perms(dt)
			key = {"parent": dt, "role": ROLE, "permlevel": permlevel, "if_owner": 0}
			name = frappe.db.get_value("Custom DocPerm", key)
			if not name:
				name = frappe.get_doc(
					{**key, "doctype": "Custom DocPerm", "parenttype": "DocType", "parentfield": "permissions", "read": 1}
				).insert(ignore_permissions=True).name
			row = frappe.get_doc("Custom DocPerm", name)
			for ptype in rs:
				row.set(ptype, 1)
			row.save(ignore_permissions=True)
		done.append(dt)
	return done


def setup():
	ensure_role()
	ensure_role_profile()
	return ensure_permissions()
