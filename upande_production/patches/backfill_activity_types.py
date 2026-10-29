import frappe

COLORS = ["#2F7D5B", "#C2410C", "#2563EB", "#9333EA", "#CA8A04", "#0E7490", "#BE185D", "#65A30D", "#B45309",
	"#4F46E5", "#0F766E", "#DC2626"]


def execute():
	"""Set activity_type (Harvesting / Planting / Cultural) and a distinct colour on operations that have none."""
	frappe.reload_doctype("Field Activity")
	ops = frappe.get_all("Field Activity", fields=["name", "operation_name", "category", "is_harvest",
		"activity_type", "color"], order_by="creation asc")
	used = {o.color for o in ops if o.color}
	free = [c for c in COLORS if c not in used]
	i = 0
	for o in ops:
		vals = {}
		if o.activity_type in (None, "", "Cultural"):
			name = (o.operation_name or "").lower()
			if o.is_harvest or o.category == "Harvesting":
				vals["activity_type"] = "Harvesting"
			elif "plant" in name and "pruning" not in name:
				vals["activity_type"] = "Planting"
			else:
				vals["activity_type"] = "Cultural"
		if not o.color:
			vals["color"] = free[i % len(free)] if free else COLORS[i % len(COLORS)]
			i += 1
		if vals:
			frappe.db.set_value("Field Activity", o.name, vals, update_modified=False)
