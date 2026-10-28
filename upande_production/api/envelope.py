"""Endpoint envelope: desk endpoints return {"error": msg} instead of raising."""

import functools
import json

import frappe
from frappe import _


def as_dict(v):
	"""json.loads a str (as sent by fetch); pass dicts/lists through."""
	if isinstance(v, str):
		try:
			return json.loads(v or "{}")
		except Exception:
			return {}
	return v if v is not None else {}


def run(fn):
	"""Decorator: never raise to the browser; return {"error": message}."""

	@functools.wraps(fn)
	def wrapper(*args, **kwargs):
		try:
			return fn(*args, **kwargs)
		except frappe.PermissionError as e:
			return {"error": str(e) or _("Not permitted.")}
		except frappe.ValidationError as e:
			frappe.db.rollback()
			out = {"error": str(e) or _("Operation failed.")}
			if hasattr(e, "breaches"):  # an activity rule: the desk shows the breaches and asks for a reason
				out.update({"breaches": e.breaches, "rule_status": e.rule_status,
					"needs_override_reason": e.rule_status == "Warn"})
			return out
		except Exception as e:
			frappe.db.rollback()
			frappe.log_error(title=f"upande_production: {fn.__name__}")
			return {"error": str(e) or _("Operation failed.")}

	return wrapper
