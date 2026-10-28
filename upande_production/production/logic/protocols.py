"""Protocol versions and manager approval.

Draft -> Pending Approval -> Active (previous Active of the family becomes Superseded), or the manager
sends it back (Draft, with a note) or rejects it outright (Rejected). Active protocols are never edited
in place: `new_version` copies the Active one to a Draft with version + 1. Only Active protocols are
offered for new cycles and plan generation; cycles keep the version they were started with.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

from upande_production.production.logic.settings import is_manager, is_supervisor

DT = "Production Protocol"
STATUSES = ("Draft", "Pending Approval", "Active", "Superseded", "Rejected")
STEP_FIELDS = ("operation", "day_offset", "repeat_every_days", "repeat_count", "planned_qty", "note")
HEAD_FIELDS = ("protocol_name", "item")


def _need_manager():
	if not is_manager():
		frappe.throw(_("Only a Production Manager can approve protocols."), frappe.PermissionError)


def _need_supervisor():
	if not is_supervisor():
		frappe.throw(_("You do not have permission to change protocols."), frappe.PermissionError)


def _doc(name):
	frappe.has_permission(DT, "read", throw=True)
	return frappe.get_doc(DT, name)


def _move(doc, status, **fields):
	doc.flags.protocol_transition = True
	doc.version_status = status
	doc.update(fields)
	doc.save(ignore_permissions=True)


def _steps(doc):
	return [{k: doc.steps[i].get(k) for k in STEP_FIELDS} for i in range(len(doc.steps))]


def _norm(field, v):
	if field in ("operation", "note"):
		return v or ""
	return float(v or 0)


def _row(doc) -> dict:
	return {
		"name": doc.name, "protocol_name": doc.protocol_name, "crop": doc.crop, "item": doc.item,
		"version": doc.version, "version_status": doc.version_status, "protocol_family": doc.protocol_family,
		"previous_version": doc.previous_version, "submitted_by": doc.submitted_by,
		"submitted_at": doc.submitted_at, "approved_by": doc.approved_by, "approved_at": doc.approved_at,
		"review_note": doc.review_note, "steps": _steps(doc),
	}


def list_protocols(crop) -> dict:
	"""Families (one per protocol) with their versions, newest first, for a crop."""
	frappe.has_permission(DT, "read", throw=True)
	names = frappe.get_all(DT, filters={"crop": crop}, pluck="name")
	fams = {}
	for n in names:
		d = frappe.get_doc(DT, n)
		fams.setdefault(d.protocol_family or d.name, []).append(_row(d))
	families = []
	for fam, versions in fams.items():
		versions.sort(key=lambda v: v["version"] or 0, reverse=True)
		cur = next((v for v in versions if v["version_status"] == "Active"), None)
		head = cur or versions[0]
		families.append({
			"family": fam, "label": versions[-1]["protocol_name"] if versions else fam, "crop": crop,
			"item": head["item"], "active": cur["name"] if cur else None,
			"has_pending": any(v["version_status"] == "Pending Approval" for v in versions),
			"versions": versions,
		})
	families.sort(key=lambda f: f["label"].lower())
	return {"families": families}


def new_version(name) -> dict:
	_need_supervisor()
	src = _doc(name)
	if src.version_status != "Active":
		frappe.throw(_("Only the Active version can be copied to a new version."), frappe.ValidationError)
	fam = src.protocol_family or src.name
	if frappe.db.exists(DT, {"protocol_family": fam, "version_status": ("in", ["Draft", "Pending Approval"])}):
		frappe.throw(_("This protocol already has a version in progress."), frappe.ValidationError)
	top = max(frappe.get_all(DT, filters={"protocol_family": fam}, pluck="version") or [1])
	base = frappe.db.get_value(DT, fam, "protocol_name") or src.protocol_name.rsplit(" v", 1)[0]
	doc = frappe.get_doc({
		"doctype": DT, "protocol_name": f"{base} v{top + 1}", "crop": src.crop, "item": src.item,
		"version": top + 1, "version_status": "Draft", "protocol_family": fam, "previous_version": src.name,
		"steps": [{k: s.get(k) for k in STEP_FIELDS} for s in src.steps],
	})
	doc.insert(ignore_permissions=True)
	return {"name": doc.name, "version": doc.version}


def submit_for_approval(name) -> dict:
	_need_supervisor()
	doc = _doc(name)
	if doc.version_status != "Draft":
		frappe.throw(_("Only a Draft can be submitted for approval."), frappe.ValidationError)
	if not doc.steps:
		frappe.throw(_("Add at least one step before submitting."), frappe.ValidationError)
	_move(doc, "Pending Approval", submitted_by=frappe.session.user, submitted_at=now_datetime())
	return {"name": doc.name, "version_status": doc.version_status}


def _pending(name):
	doc = _doc(name)
	if doc.version_status != "Pending Approval":
		frappe.throw(_("{0} is {1}, not Pending Approval.").format(name, doc.version_status),
			frappe.ValidationError)
	return doc


def approve(name) -> dict:
	_need_manager()
	doc = _pending(name)
	fam = doc.protocol_family or doc.name
	for old in frappe.get_all(DT, filters={"protocol_family": fam, "version_status": "Active", "name": ("!=", doc.name)},
			pluck="name"):
		_move(frappe.get_doc(DT, old), "Superseded")
	_move(doc, "Active", approved_by=frappe.session.user, approved_at=now_datetime(), review_note=None)
	return {"name": doc.name, "version_status": "Active"}


def _note(note):
	note = (note or "").strip()
	if not note:
		frappe.throw(_("A note is required."), frappe.ValidationError)
	return note


def send_back(name, note) -> dict:
	_need_manager()
	note = _note(note)
	doc = _pending(name)
	_move(doc, "Draft", review_note=note)
	return {"name": doc.name, "version_status": "Draft"}


def reject(name, note) -> dict:
	_need_manager()
	note = _note(note)
	doc = _pending(name)
	_move(doc, "Rejected", review_note=note)
	return {"name": doc.name, "version_status": "Rejected"}


def diff(name) -> dict:
	"""Differences of a version against its previous version: head fields and step by step."""
	doc = _doc(name)
	prev = frappe.get_doc(DT, doc.previous_version) if doc.previous_version else None
	op_names = dict(frappe.get_all("Production Operation", fields=["name", "operation_name"], as_list=True))
	out = {"name": doc.name, "previous": prev.name if prev else None, "fields": [], "steps": []}
	if not prev:
		out["steps"] = [{"change": "added", "operation": s["operation"],
			"operation_name": op_names.get(s["operation"], s["operation"]), "after": s} for s in _steps(doc)]
		return out
	for f in HEAD_FIELDS:
		a, b = prev.get(f), doc.get(f)
		if f == "protocol_name":
			continue  # versions are named v1, v2, ... on purpose
		if (a or None) != (b or None):
			out["fields"].append({"field": f, "before": a, "after": b})

	def keyed(p):
		seen, m = {}, {}
		for s in _steps(p):
			n = seen[s["operation"]] = seen.get(s["operation"], 0) + 1
			m[(s["operation"], n)] = s
		return m

	old, new = keyed(prev), keyed(doc)
	for key in list(new) + [k for k in old if k not in new]:
		a, b = old.get(key), new.get(key)
		base = {"operation": key[0], "operation_name": op_names.get(key[0], key[0])}
		if a and not b:
			out["steps"].append({**base, "change": "removed", "before": a})
		elif b and not a:
			out["steps"].append({**base, "change": "added", "after": b})
		else:
			ch = [{"field": f, "before": a[f], "after": b[f]} for f in STEP_FIELDS if _norm(f, a[f]) != _norm(f, b[f])]
			if ch:
				out["steps"].append({**base, "change": "changed", "changes": ch, "before": a, "after": b})
	return out


def pending_list(crop=None) -> dict:
	"""Pending Approval versions (with their diffs) for the Approvals page."""
	frappe.has_permission(DT, "read", throw=True)
	filters = {"version_status": "Pending Approval"}
	if crop:
		filters["crop"] = crop
	rows = []
	for n in frappe.get_all(DT, filters=filters, pluck="name", order_by="submitted_at asc"):
		d = frappe.get_doc(DT, n)
		users = frappe.db.get_value("User", d.submitted_by, "full_name") if d.submitted_by else None
		rows.append({**_row(d), "submitted_by_name": users or d.submitted_by, "diff": diff(n)})
	return {"rows": rows}


def pending_counts() -> dict:
	"""{crop: n} of Pending Approval versions."""
	rows = frappe.db.sql(
		"select crop, count(*) from `tabProduction Protocol` where version_status = 'Pending Approval' group by crop"
	)
	return {c: n for c, n in rows}


def save_draft(data) -> dict:
	"""Edit a Draft's item and steps. Anything not a Draft is refused."""
	import json

	_need_supervisor()
	if isinstance(data, str):
		data = json.loads(data or "{}")
	doc = _doc(data.get("name"))
	if doc.version_status != "Draft":
		frappe.throw(_("Only a Draft can be edited."), frappe.ValidationError)
	if "item" in data:
		doc.item = data["item"] or None
	if "steps" in data:
		doc.set("steps", [{k: s.get(k) for k in STEP_FIELDS} for s in data["steps"] or []])
	doc.save(ignore_permissions=True)
	return {"name": doc.name}
