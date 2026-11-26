"""Who may use which mobile screen. One map, used by every mobile endpoint guard and by get_session_info."""
import frappe

MANAGERS = ("Production Manager", "Avocado Production Manager", "System Manager")
SUPERVISORS = ("Production Supervisor",)
VIEWERS = ("Production Viewer",)
ASSISTANTS = ("Production Assistant Manager",)  # settings.ASSISTANT_ROLE

CAPABILITIES = {
	"farm_report": MANAGERS,
	"plan_view": MANAGERS + ASSISTANTS + SUPERVISORS + VIEWERS,
	"plan_tick_off": MANAGERS + SUPERVISORS,
	"plan_manage": MANAGERS + ASSISTANTS,
	"plan_check": ASSISTANTS,  # vouch for work on tasks they assigned
	"plan_approve": MANAGERS,  # approve work, forward awaiting tasks
	"harvest": MANAGERS + SUPERVISORS,
	"crate_admin": MANAGERS + SUPERVISORS,
}


def has_capability(cap: str, user: str | None = None) -> bool:
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	return bool(set(CAPABILITIES[cap]) & set(frappe.get_roles(user)))


def capabilities(user: str | None = None) -> dict:
	caps = {c: has_capability(c, user) for c in CAPABILITIES}
	caps["any"] = any(caps.values())
	return caps
