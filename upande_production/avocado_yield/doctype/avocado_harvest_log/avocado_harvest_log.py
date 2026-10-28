# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

# One day's picking off one block: kilograms, trees picked, pickers on the line and
# the grade split after packing. This is the record the age curve, the Grade 1
# share and the measured kg-per-picker-day are read from (see api/avocadoapi.py and
# api/avocadolabour.py, which already query it by these field names).
#
# On a site that also has the avocado_production app, that app owns a doctype of the
# same name and this one should not be installed beside it.

from frappe.model.document import Document


class AvocadoHarvestLog(Document):
	pass
