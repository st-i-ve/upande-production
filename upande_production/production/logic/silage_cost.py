"""Silage cycle cost maths. Pure: no Frappe, no database, so it is tested without a site.

A cycle's cost has four kinds, each read from records elsewhere (see logic/silage.py):

* inputs        - seed, fertiliser, inoculant, sheeting issued from stock against the cycle (stock ledger value)
* diesel        - diesel cost of submitted Production Asset Allocations whose reference is the cycle
* labour        - the cycle's own activity rows (workers x day rate, or an amount typed in)
* casual_labour - approved Casual Labour Work on the cycle's field during the cycle

Silage is received into the pit at total cost / ensiled kg.
"""

KINDS = ("inputs", "diesel", "labour", "casual_labour")
KIND_LABELS = {"inputs": "Inputs", "diesel": "Diesel", "labour": "Activity labour", "casual_labour": "Casual labour"}


def _num(v) -> float:
	try:
		return float(v or 0)
	except (TypeError, ValueError):
		return 0.0


def activity_labour(workers=None, day_rate=None, labour_cost=None) -> float:
	"""Labour of one activity row: workers x day rate when both are given, else the amount typed in."""
	w, r = _num(workers), _num(day_rate)
	if w > 0 and r > 0:
		return round(w * r, 2)
	return round(max(_num(labour_cost), 0.0), 2)


def cycle_cost(inputs=0, diesel=0, labour=0, casual_labour=0) -> dict:
	"""{inputs, diesel, labour, casual_labour, total}, each rounded to 2 places."""
	parts = {"inputs": _num(inputs), "diesel": _num(diesel), "labour": _num(labour), "casual_labour": _num(casual_labour)}
	out = {k: round(v, 2) for k, v in parts.items()}
	out["total"] = round(sum(parts.values()), 2)
	return out


def cost_per_kg(total, kg):
	"""total / kg, or None when nothing has been ensiled (no kilos to spread the cost over)."""
	kg = _num(kg)
	if kg <= 0:
		return None
	return _num(total) / kg


def by_kind(cost: dict) -> list[dict]:
	"""[{kind, label, amount, share_pct}] for the cost kinds, in a fixed order; share_pct None when the total is 0."""
	total = _num(cost.get("total"))
	return [{
		"kind": k, "label": KIND_LABELS[k], "amount": round(_num(cost.get(k)), 2),
		"share_pct": round(_num(cost.get(k)) * 100 / total, 1) if total > 0 else None,
	} for k in KINDS]


def summarise(cycles: list[dict]) -> dict:
	"""Totals over cycles ({cost: {...}, ensiled_kg}). The cost per kg is weighted: cost of the cycles
	that ensiled anything over the kilos they ensiled (an open cycle's cost does not inflate it)."""
	totals = {k: 0.0 for k in KINDS}
	kg = costed = 0.0
	for c in cycles:
		cost = c.get("cost") or {}
		for k in KINDS:
			totals[k] += _num(cost.get(k))
		ckg = _num(c.get("ensiled_kg"))
		if ckg > 0:
			kg += ckg
			costed += _num(cost.get("total"))
	out = cycle_cost(**totals)
	return {"cost": out, "ensiled_kg": round(kg, 3), "cost_per_kg": cost_per_kg(costed, kg), "cycles": len(cycles)}
