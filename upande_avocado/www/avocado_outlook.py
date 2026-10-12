import frappe

from upande_avocado.api.avocadoapi import biennial_factor


def get_context(context):
	"""Season outlook page — login-gated, never cached.

	Same shape as the other avocado pages: the CSRF token is handed over so the
	page's POSTs are accepted, and caching is off because a forecast read off
	yesterday's counts is worse than waiting a second for today's.
	"""
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/avocado-outlook"
		raise frappe.Redirect
	context.no_cache = 1
	context.csrf_token = frappe.sessions.get_csrf_token()
	if getattr(frappe.local, "response_headers", None) is not None:
		frappe.local.response_headers["Cache-Control"] = "no-store, must-revalidate"


@frappe.whitelist()
def get_years():
	"""Kilograms actually delivered, per season, from the harvest history.

	Only what the doctype holds — no gap filling, no smoothing. A season the
	estate has no rows for simply is not in the list, because a missing season
	and a bad season look identical once you draw a zero bar for both.

	`on_year` comes from the forecast's own biennial rule rather than a second
	copy of it here, so the bars and the forecast can never disagree about which
	years are on.
	"""
	rows = frappe.db.sql(
		"""select year, sum(kg_harvested) as kg, count(distinct block_code) as blocks
		   from `tabAvocado Yield History`
		   where ifnull(year, 0) > 0
		   group by year order by year""",
		as_dict=True,
	)
	return {
		"rows": [
			{
				"year": int(r.year),
				"kg": round(float(r.kg or 0), 0),
				"blocks": int(r.blocks or 0),
				"on_year": biennial_factor(r.year) == 1.0,
			}
			for r in rows
		],
		"source": "Avocado Yield History",
	}
