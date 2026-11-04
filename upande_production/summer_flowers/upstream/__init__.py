"""Forwarders to code that lives in a sibling app but is reached from production.

Production sits below planning (upande_crop_material_planning) and propagation (upande_propagation) in the
dependency chain and never imports them at module load. The few production paths that need something
those apps own (the root line asks for sourcing and TC supply, delivery confirmation builds the propagation
plan) go through this package: each module forwards attribute access, lazily, to the first sibling that has
it, and raises an ImportError naming where it looked when neither is installed.
"""

import importlib


def make_getattr(candidates, label):
	cache = {}

	def __getattr__(attr):
		if attr.startswith("__"):
			raise AttributeError(attr)
		if "mod" not in cache:
			last = None
			for path in candidates:
				try:
					cache["mod"] = importlib.import_module(path)
					break
				except ModuleNotFoundError as exc:
					if exc.name and not path.startswith(exc.name) and exc.name != path:
						raise
					last = exc
			else:
				raise ImportError(f"{label} is provided by a sibling app ({', '.join(candidates)}); none is installed") from last
		return getattr(cache["mod"], attr)

	return __getattr__


PLAN = "upande_crop_material_planning.summer_flowers"
PLAN_DT = "upande_crop_material_planning.upande_crop_material_planning.doctype"
PROP = "upande_propagation"
PROP_DT = "upande_propagation.upande_propagation.doctype"
