# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

from frappe.utils.nestedset import NestedSet


class ProductionUnit(NestedSet):
	nsm_parent_field = "parent_production_unit"
