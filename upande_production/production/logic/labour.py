"""Labour & Pay settings (Production Settings, section "Labour & Pay") and the Work Management switch."""

import frappe

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

DEFAULTS = {
	"labour_mode": "Automatic",
	"pay_period": "Weekly",
	"pay_week_starts_on": "Monday",
	"pay_day": "Friday",
	"daily_wage": 0,
	"duplicate_rule": "Block",
	"multiple_jobs_per_day": "Warn",
	"attendance_required": 0,
	"attendance_source": "Production",
	"max_backdate_days": 0,
	"pay_reference_prefix": "PAY",
}

OPTIONS = {
	"labour_mode": ("Automatic", "Built-in only"),
	"pay_period": ("Weekly", "Fortnightly", "Monthly"),
	"pay_week_starts_on": tuple(WEEKDAYS),
	"pay_day": tuple(WEEKDAYS),
	"duplicate_rule": ("Block", "Warn", "Off"),
	"multiple_jobs_per_day": ("Allow", "Warn", "Block"),
	"attendance_source": ("Production", "HRMS Attendance", "Both"),
}


def labour_settings() -> dict:
	"""Every Labour & Pay value, with the documented default where the settings were never keyed in."""
	doc = frappe.get_cached_doc("Production Settings")
	out = {}
	for key, default in DEFAULTS.items():
		val = doc.get(key)
		out[key] = default if val is None or val == "" else val
	out["daily_wage"] = float(out["daily_wage"] or 0)
	out["max_backdate_days"] = int(out["max_backdate_days"] or 0)
	out["attendance_required"] = 1 if int(out["attendance_required"] or 0) else 0
	return out


def setting(key):
	return labour_settings()[key]


def wm_installed() -> bool:
	return "work_management" in frappe.get_installed_apps()


def wm_active() -> bool:
	"""True only when the Work Management app is installed and the mode is Automatic."""
	return wm_installed() and setting("labour_mode") == "Automatic"
