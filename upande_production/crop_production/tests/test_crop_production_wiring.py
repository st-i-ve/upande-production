"""The old upande_agriculture paths keep resolving, and the ownership patch is safe."""

import importlib

import frappe
from frappe.tests.utils import FrappeTestCase

from upande_production import hooks


def _resolve(path: str):
	module, _, name = path.rpartition(".")
	return getattr(importlib.import_module(module), name)


class TestOldPathsResolve(FrappeTestCase):
	def test_every_override_target_is_a_whitelisted_function(self):
		overrides = {k: v for k, v in hooks.override_whitelisted_methods.items()
		             if k.startswith("upande_agriculture.")}
		self.assertGreaterEqual(len(overrides), 40)
		for old, new in overrides.items():
			fn = _resolve(new)
			self.assertIn(fn, frappe.whitelisted, f"{old} -> {new} is not whitelisted")

	def test_hooked_handlers_import(self):
		for events in hooks.doc_events.values():
			for handlers in events.values():
				for path in ([handlers] if isinstance(handlers, str) else handlers):
					_resolve(path)
		for path in hooks.scheduler_events["daily"]:
			_resolve(path)
		_resolve(hooks.override_doctype_dashboards["Stock Entry"])

	def test_production_never_imports_planning_or_propagation(self):
		import os
		root = frappe.get_app_path("upande_production")
		offenders = []
		for base, dirs, files in os.walk(root):
			dirs[:] = [d for d in dirs if d not in ("node_modules", "__pycache__", "public")]
			for f in files:
				if not f.endswith(".py"):
					continue
				with open(os.path.join(base, f)) as fh:
					for line in fh:
						s = line.strip()
						if s.startswith(("import ", "from ")) and (
							"upande_crop_material_planning" in s or "upande_propagation" in s
						):
							offenders.append(f"{f}: {s}")
		self.assertEqual(offenders, [])


class TestOwnershipPatch(FrappeTestCase):
	def test_flips_agriculture_module_and_is_a_noop_otherwise(self):
		from upande_production.patches import take_over_from_upande_agriculture as p

		before = frappe.db.get_value("DocType", "Crop Cycle", "module")
		p.execute()  # already Crop Production: untouched
		self.assertEqual(frappe.db.get_value("DocType", "Crop Cycle", "module"), before)

		frappe.db.set_value("DocType", "Cut Stage", "module", "Upande Agriculture", update_modified=False)
		frappe.db.set_value("DocType", "Crop Type", "module", "Upande Propagation", update_modified=False)
		p.execute()
		self.assertEqual(frappe.db.get_value("DocType", "Cut Stage", "module"), "Crop Production")
		self.assertEqual(frappe.db.get_value("DocType", "Crop Type", "module"), "Crop Production")
