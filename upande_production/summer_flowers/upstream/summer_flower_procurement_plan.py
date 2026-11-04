"""Forwards to the sibling app that owns summer_flower_procurement_plan (see upstream/__init__)."""

from upande_production.summer_flowers.upstream import make_getattr

__getattr__ = make_getattr(['upande_crop_material_planning.upande_crop_material_planning.doctype.summer_flower_procurement_plan.summer_flower_procurement_plan'], "summer_flower_procurement_plan")
