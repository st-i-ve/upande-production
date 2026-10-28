from upande_production.patches import renumber_cycles_by_pattern


def execute():
	"""cycle_no along the previous_cycle chain, only for repeat-harvest varieties (see renumber_cycles_by_pattern)."""
	renumber_cycles_by_pattern.execute()
