"""Test helper: run a test class with Labour mode "Built-in only".

Labour mode defaults to Automatic, so on a site where the Work Management app is installed production hands
its labour to WM (production/logic/wm_bridge.py). Classes that test production's own labour flow - plans,
tick-offs, approvals, pay runs - switch to built-in for their run and put the mode back after. Both writes are
committed: the API envelope rolls back on an error, which would otherwise undo the switch mid-class.
"""

import frappe


def set_labour_mode(mode):
	frappe.db.set_single_value("Production Settings", "labour_mode", mode)
	frappe.clear_document_cache("Production Settings", "Production Settings")
	frappe.db.commit()


def restore_labour_mode(mode):
	"""Class cleanup. unittest runs it before IntegrationTestCase's own rollback cleanup, so roll back first:
	committing the restore must not commit the fixtures a class leaves to that rollback."""
	frappe.db.rollback()
	set_labour_mode(mode)


_ORIGINAL = []


def current_labour_mode():
	"""The site's own mode, read once per test process: the runner does not always restore one class before
	the next one starts, so "the mode right now" can be another class's switch."""
	if not _ORIGINAL:
		_ORIGINAL.append(frappe.db.get_single_value("Production Settings", "labour_mode", cache=False))
	return _ORIGINAL[0]


def use_builtin_labour(cls):
	"""Call from setUpClass (after super().setUpClass(), which has just committed)."""
	original = current_labour_mode()
	set_labour_mode("Built-in only")
	cls.addClassCleanup(restore_labour_mode, original)
