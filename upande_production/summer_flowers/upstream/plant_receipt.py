"""Forwards to the sibling app that owns plant_receipt (see upstream/__init__)."""

from upande_production.summer_flowers.upstream import make_getattr

__getattr__ = make_getattr(['upande_propagation.plant_receipt'], "plant_receipt")
