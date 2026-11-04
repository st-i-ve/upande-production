"""Forwards to the sibling app that owns planning_api (see upstream/__init__)."""

from upande_production.summer_flowers.upstream import make_getattr

__getattr__ = make_getattr(['upande_crop_material_planning.summer_flowers.planning_api'], "planning_api")
