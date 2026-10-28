# Copyright (c) 2026, Upande and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from upande_production.production.logic import establishment


class BlockEstablishmentCost(Document):
	def validate(self):
		establishment.split(self)
