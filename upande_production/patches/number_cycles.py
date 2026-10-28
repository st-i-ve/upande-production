import frappe


def execute():
	"""cycle_no along the previous_cycle chain (no chain -> 1)."""
	rows = frappe.get_all("Production Crop Cycle", fields=["name", "previous_cycle"])
	prev = {r.name: r.previous_cycle for r in rows}

	def number(name):
		n, seen = 1, {name}
		while prev.get(name) and prev[name] in prev and prev[name] not in seen:
			name = prev[name]
			seen.add(name)
			n += 1
		return n

	for r in rows:
		frappe.db.set_value("Production Crop Cycle", r.name, "cycle_no", number(r.name), update_modified=False)
