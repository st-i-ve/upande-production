"""Who may use which mobile screen. One map, used by every mobile endpoint guard and by get_session_info."""
import frappe

MANAGERS = ("Production Manager", "Avocado Production Manager", "System Manager")
SUPERVISORS = ("Production Supervisor",)
VIEWERS = ("Production Viewer",)

CAPABILITIES = {
	"farm_report": MANAGERS,
	"plan_view": MANAGERS + SUPERVISORS + VIEWERS,
	"plan_tick_off": MANAGERS + SUPERVISORS,
	"plan_manage": MANAGERS,
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
