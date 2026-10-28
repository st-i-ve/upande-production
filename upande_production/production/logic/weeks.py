from datetime import date, timedelta

from frappe.utils import getdate


def iso_week_bounds(year: int, week: int) -> tuple[date, date]:
	"""Monday and Sunday of the ISO week."""
	monday = date.fromisocalendar(int(year), int(week), 1)
	return monday, monday + timedelta(days=6)


def iso_of(d) -> tuple[int, int]:
	"""(iso_year, iso_week) of a date or date string."""
	iso = getdate(d).isocalendar()
	return iso[0], iso[1]
