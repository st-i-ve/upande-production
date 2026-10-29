"""Desk API for Settings, Crop model: a crop's model parameters, read from and written to Production Crop.

The editor is driven by the doctype itself: every section of Production Crop after the identity fields
becomes a group, its fields and child tables are described from the meta, and the values come from the
record. A parameter added to the doctype shows up here without a code change. Writes need a Production
Manager (the doctype also lets a supervisor edit a crop; this screen does not).
"""

import re

import frappe
from frappe import _
from frappe.utils import cint, flt

from upande_production.api.envelope import as_dict, run
from upande_production.api.production import MANAGE_ROLES, _need

# Identity and layout fields of the crop: edited on the Production Crop form, not here.
SKIP = {"crop_name", "crop_key", "accent_color", "icon_key", "parent_unit_label", "unit_label", "sub_unit_label",
	"yield_uom", "uses_crop_cycles", "default_cycle_type", "enabled", "sort_order"}
LAYOUT = {"Section Break", "Column Break", "Tab Break"}
EDITABLE_TYPES = {"Data", "Int", "Float", "Currency", "Check", "Select", "Percent", "Small Text"}
INTRO_GROUP = "Harvest"


def _crop_visible(depends_on, crop_key):
	"""A section's `eval:doc.crop_key=='x'` rule; anything else is visible."""
	m = re.fullmatch(r"eval:doc\.crop_key\s*==\s*'([^']+)'", depends_on or "")
	return not m or m.group(1) == crop_key


def _is_manager():
	return frappe.session.user == "Administrator" or bool(MANAGE_ROLES & set(frappe.get_roles()))


def _field(f, doc):
	v = doc.get(f.fieldname)
	return {"fieldname": f.fieldname, "label": f.label or f.fieldname, "fieldtype": f.fieldtype,
		"options": f.options if f.fieldtype == "Select" else None, "description": f.description or None,
		"depends_on": f.depends_on if f.depends_on and re.fullmatch(r"\w+", f.depends_on) else None,
		"value": cint(v) if f.fieldtype == "Check" else (flt(v) if f.fieldtype in ("Int", "Float", "Currency", "Percent") and v is not None else v)}


def _table(f, doc):
	child = frappe.get_meta(f.options)
	cols = [{"fieldname": c.fieldname, "label": c.label or c.fieldname, "fieldtype": c.fieldtype,
		"options": c.options if c.fieldtype == "Select" else None}
		for c in child.fields if c.fieldtype in EDITABLE_TYPES]
	rows = [{c["fieldname"]: r.get(c["fieldname"]) for c in cols} for r in doc.get(f.fieldname) or []]
	return {"fieldname": f.fieldname, "label": f.label or f.fieldname, "description": f.description or None,
		"columns": cols, "rows": rows}


def _layout(doc):
	"""[{label, fields, tables}] of the crop's model sections, plus the child doctype of each table."""
	meta = frappe.get_meta("Production Crop")
	groups = [{"label": INTRO_GROUP, "fields": [], "tables": []}]
	current, visible = groups[0], True
	for f in meta.fields:
		if f.fieldtype == "Section Break":
			visible = _crop_visible(f.depends_on, doc.crop_key)
			current = {"label": f.label or f.fieldname, "fields": [], "tables": []}
			groups.append(current)
		elif f.fieldname in SKIP or f.fieldtype in LAYOUT or not visible:
			continue
		elif f.fieldtype == "Table":
			current["tables"].append(_table(f, doc))
		elif f.fieldtype in EDITABLE_TYPES:
			current["fields"].append(_field(f, doc))
	return [g for g in groups if g["fields"] or g["tables"]]


@frappe.whitelist(methods=["POST"])
@run
def get_crop_model(crop):
	"""{crop, crop_key, can_edit, groups: [{label, fields: [...], tables: [...]}]} of the crop's model parameters."""
	_need("Production Crop")
	doc = frappe.get_doc("Production Crop", crop)
	return {"crop": doc.name, "crop_key": doc.crop_key, "can_edit": _is_manager(), "groups": _layout(doc)}


@frappe.whitelist(methods=["POST"])
@run
def save_crop_model(crop, data):
	"""Save field values and replace table rows. `data` is {fieldname: value | [row, ...]}; only the fields
	get_crop_model describes are accepted."""
	if not _is_manager():
		frappe.throw(_("Only a Production Manager can change the crop model."), frappe.PermissionError)
	doc = frappe.get_doc("Production Crop", crop)
	data = dict(as_dict(data) or {})
	allowed = {f["fieldname"]: f for g in _layout(doc) for f in g["fields"]}
	tables = {t["fieldname"]: t for g in _layout(doc) for t in g["tables"]}
	for k, v in data.items():
		if k in tables:
			cols = [c["fieldname"] for c in tables[k]["columns"]]
			doc.set(k, [])
			for r in v or []:
				doc.append(k, {c: r.get(c) for c in cols if c in r})
		elif k in allowed:
			doc.set(k, v)
		else:
			frappe.throw(_("{0} is not a crop model setting.").format(k), frappe.ValidationError)
	doc.save()
	return {"crop": doc.name, "groups": _layout(doc)}
