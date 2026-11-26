from frappe.model.document import Document


class ProductionUnitType(Document):
	"""A kind of block or group (Pivot, Greenhouse, Pond ...): the pick-list for crop labels and a unit's type."""


# Shipped as a fixture too; the patch inserts any that are missing so it works before fixtures sync.
STANDARD = [
	("Farm", "A whole farm; holds pivots or blocks."),
	("Pivot", "A centre-pivot irrigation circle; holds pivot blocks."),
	("Pivot Block", "A block cut out of a pivot circle."),
	("Block", "A planted block of one crop."),
	("Orchard Block", "A block of trees in an orchard."),
	("Bed", "A planted bed inside a block."),
	("Row", "A single row inside a block."),
	("Greenhouse", "A greenhouse that holds beds."),
	("Pond", "A fish pond."),
	("Hive Group", "A group of beehives at one site."),
	("Hive", "A single beehive."),
	("Other", "Anything that does not fit the other types."),
	("Field", "An open field planted to one crop."),
]
