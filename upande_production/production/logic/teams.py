"""Manager teams: an assistant manager belongs to the manager their Employee reports to.

An assistant's tasks and checked work go to that manager's queue. Work with no team (the assigner has no
manager, or is not an assistant) goes to every manager. Another manager may still act on a team's work
after confirming.
"""
import frappe
from frappe import _

from upande_production.production.logic import settings


class OtherTeam(frappe.ValidationError):
	"""Acting on another manager's team without confirming; the desk and phone ask first."""

	needs_confirm = True


def _cache() -> dict:
	if not hasattr(frappe.local, "mteams_cache"):
		frappe.local.mteams_cache = {}
	return frappe.local.mteams_cache


def clear_cache():
	frappe.local.mteams_cache = {}


def manager_of(user) -> str | None:
	"""The user of the Employee the user's Employee reports to, if that user is a manager."""
	if not user:
		return None
	c = _cache().setdefault("manager_of", {})
	if user not in c:
		out = None
		boss = frappe.db.get_value("Employee", {"user_id": user}, "reports_to")
		boss_user = frappe.db.get_value("Employee", boss, "user_id") if boss else None
		if boss_user and boss_user != user and settings.is_manager_user(boss_user):
			out = boss_user
		c[user] = out
	return c[user]


def team_of(manager_user) -> set[str]:
	"""Assistant manager users whose manager is this user."""
	c = _cache().setdefault("team_of", {})
	if manager_user not in c:
		mine = frappe.get_all("Employee", filters={"user_id": manager_user}, pluck="name")
		rows = frappe.get_all("Employee", filters={"reports_to": ("in", mine or [""]), "user_id": ("is", "set")},
			pluck="user_id") if mine else []
		c[manager_user] = {u for u in rows if settings.is_assistant_manager(u) and manager_of(u) == manager_user}
	return c[manager_user]


def team_manager(assigned_by) -> str | None:
	"""Whose team an item assigned by this user belongs to; None when it has no team (every manager's)."""
	if not assigned_by or not settings.is_assistant_manager(assigned_by):
		return None
	return manager_of(assigned_by)


def scoped(me=None, all_teams=False) -> bool:
	"""True when the user is a manager whose queues are narrowed to their team (Administrator sees everything)."""
	me = me or frappe.session.user
	return not all_teams and me != "Administrator" and settings.is_manager_user(me)


def is_mine(assigned_by, me=None) -> bool:
	"""In the manager's queue by default: their team's items plus the ones with no team."""
	me = me or frappe.session.user
	owner = team_manager(assigned_by)
	return owner is None or owner == me


def other_team_manager(assigned_by, me=None) -> str | None:
	"""The manager whose team the item belongs to when that is not the session manager (Administrator: none)."""
	me = me or frappe.session.user
	if me == "Administrator":
		return None
	owner = team_manager(assigned_by)
	return owner if owner and owner != me else None


def require_confirm(assigned_bys, confirm_other_team=0, me=None):
	"""Refuse when any item belongs to another manager's team and the caller has not confirmed."""
	if frappe.utils.cint(confirm_other_team):
		return
	for by in dict.fromkeys(assigned_bys):
		owner = other_team_manager(by, me)
		if owner:
			name = frappe.db.get_value("User", owner, "full_name") or owner
			frappe.throw(_("This belongs to {0}'s team. Confirm to approve it anyway.").format(name), OtherTeam)


def assistants_without_manager() -> list[dict]:
	"""Enabled assistant managers whose Employee reports to nobody, or to someone who is not a manager."""
	users = frappe.get_all("Has Role", filters={"role": settings.ASSISTANT_ROLE, "parenttype": "User"}, pluck="parent")
	out = []
	for u in sorted(set(users)):
		if not settings.is_assistant_manager(u) or manager_of(u):
			continue
		emp = frappe.db.get_value("Employee", {"user_id": u}, ["name", "employee_name", "reports_to"], as_dict=True)
		out.append({"user": u, "full_name": frappe.db.get_value("User", u, "full_name") or u,
			"employee": emp.name if emp else None, "reports_to": emp.reports_to if emp else None,
			"reason": "no_employee" if not emp else "no_reports_to" if not emp.reports_to else "reports_to_not_manager"})
	return out
