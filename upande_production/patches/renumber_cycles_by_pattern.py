import frappe


def execute():
	"""cycle_no > 1 only along a previous_cycle chain of a repeat-harvest (non-Once) variety; every other
	cycle is cycle 1."""
	rows = frappe.get_all("Production Crop Cycle", fields=["name", "previous_cycle", "variety"])
	by = {r.name: r for r in rows}
	repeat = {v.name for v in frappe.get_all("Production Variety", fields=["name", "harvest_pattern"])
		if (v.harvest_pattern or "Once") != "Once"}

	def number(name):
		n, seen = 1, {name}
		while True:
			r = by[name]
			if not (r.previous_cycle and r.previous_cycle in by and r.previous_cycle not in seen and r.variety in repeat):
				return n
			name = r.previous_cycle
			seen.add(name)
			n += 1

	for r in rows:
		frappe.db.set_value("Production Crop Cycle", r.name, "cycle_no", number(r.name), update_modified=False)
