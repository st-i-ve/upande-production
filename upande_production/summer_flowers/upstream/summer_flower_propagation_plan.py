"""Forwards to the sibling app that owns summer_flower_propagation_plan (see upstream/__init__)."""

from upande_production.summer_flowers.upstream import make_getattr

__getattr__ = make_getattr(['upande_propagation.upande_propagation.doctype.summer_flower_propagation_plan.summer_flower_propagation_plan'], "summer_flower_propagation_plan")
