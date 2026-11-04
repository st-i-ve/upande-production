"""Forwards to the sibling app that owns trough_plan (see upstream/__init__)."""

from upande_production.summer_flowers.upstream import make_getattr

__getattr__ = make_getattr(['upande_propagation.trough_plan', 'upande_crop_material_planning.summer_flowers.trough_plan'], "trough_plan")
