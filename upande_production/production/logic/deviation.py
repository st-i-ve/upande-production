from datetime import timedelta

from frappe.utils import get_datetime, getdate


def task_deviation(status, due_date, completed_at, planned_qty, done_qty, tolerance_days) -> str:
	"""Return "", "Late", "Partial" or "Skipped" for a plan task."""
	if status == "Skipped":
		return "Skipped"
	if status not in ("Done", "Partly Done"):
		return ""
	planned = float(planned_qty or 0)
	done = float(done_qty or 0)
	if status == "Partly Done" or (planned > 0 and done < planned):
		return "Partial"
	if due_date and completed_at:
		done_on = get_datetime(completed_at).date()
		if done_on > getdate(due_date) + timedelta(days=int(tolerance_days or 0)):
			return "Late"
	return ""
