# Self-check for the Avocado Production Manager role definition and the app's role gates.
#
# Run: env/bin/python -m upande_production.tests.test_avocado_role   (no site needed)

from upande_production.production.logic import avocado_role as ar
from upande_production.production.logic import settings

ROLE = "Avocado Production Manager"


def test_perms_table():
	seen = set()
	for names, rights, level1 in ar.PERMS:
		assert names and not (set(names) & seen), names
		seen |= set(names)
		assert "read" in rights, names
		if {"submit", "cancel"} & set(rights):
			assert {"submit", "cancel", "amend", "write", "create"} <= set(rights), names
		if level1:
			assert set(level1) <= {"read", "write"}, names
	flat = {n for names, _, _ in ar.PERMS for n in names}
	# transactions the harvest flow posts, and the masters it only reads
	for need in ("Production Crop Cycle", "Harvest Batch", "Stock Entry", "Stock Ledger Entry", "Bin",
				 "Production Crop", "Production Unit", "Warehouse", "Avocado Fruit Count"):
		assert need in flat, need
	by = {n: r for names, r, _ in ar.PERMS for n in names}
	assert {"submit", "cancel"} <= set(by["Stock Entry"])
	assert by["Production Crop"] == ar.READ and "write" not in by["Warehouse"]
	# a casual labour doctype is listed under both its current and its former name
	assert {"Casual Labour Work", "Value Adder Work"} <= flat


def test_role_gates():
	from upande_production.api import avocado, production
	from upande_production.mobile import harvest

	for s in (settings.MANAGE_ROLES, settings.PAY_ROLES, production.MANAGE_ROLES, harvest.MANAGER_ROLES,
			  avocado.READ_ROLES, avocado.WRITE_ROLES):
		assert ROLE in s
	assert ROLE in settings.SUPERVISE_ROLES


def test_crop_limit():
	import frappe

	roles = {"v": []}
	user = {"v": "maina@x"}
	frappe.session = type("S", (), {"user": property(lambda s: user["v"])})()
	frappe.get_roles = lambda *a, **k: roles["v"]
	roles["v"] = [ROLE, "Farm Manager"]
	assert settings.avocado_only_crop_keys() == {"avocado"}
	for other in ("Production Manager", "System Manager", "Production Supervisor"):
		roles["v"] = [ROLE, other]
		assert settings.avocado_only_crop_keys() == set(), other
	roles["v"] = ["Farm Manager"]
	assert settings.avocado_only_crop_keys() == set()
	user["v"] = "Administrator"
	roles["v"] = [ROLE]
	assert settings.avocado_only_crop_keys() == set()


if __name__ == "__main__":
	test_perms_table()
	test_role_gates()
	test_crop_limit()
	print("avocado role: ok")
