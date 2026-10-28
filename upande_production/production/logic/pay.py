def pay_value(qty, rate) -> float:
	return round(float(qty or 0) * float(rate or 0), 2)
