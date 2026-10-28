import frappe


def get_context(context):
	"""Harvest calendar page — login-gated, never cached.

	Same shape as the other avocado pages: the CSRF token is handed over so the
	page's POSTs are accepted, and caching is off because a calendar cached from
	last week dates picks against last week's dry matter.
	"""
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/avocado-calendar"
		raise frappe.Redirect
	context.no_cache = 1
	context.csrf_token = frappe.sessions.get_csrf_token()
	if getattr(frappe.local, "response_headers", None) is not None:
		frappe.local.response_headers["Cache-Control"] = "no-store, must-revalidate"
