# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

from frappe.utils.nestedset import NestedSet


class ProductionCropGroup(NestedSet):
	nsm_parent_field = "parent_production_crop_group"
