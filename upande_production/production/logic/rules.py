"""Activity rule engine: which operations a crop's stage or calendar forbids (Block) or frowns on (Warn).

Rules are Production Activity Rule rows scoped by crop (required), variety and stage (optional) and
apply to one operation or to every operation of a category. `check()` returns the breaches an
operation on a date would cause; `enforce()` turns them into a refusal (Block), a demand for an
override reason (Warn) or the fields to stamp on the task / work (rule_status, rule_notes,
override_reason). The evaluation core is pure over a small context so the protocol version check can
reuse it for steps that have no cycle yet.
"""

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate

NOT_IN, ONLY_IN = "Not in stage", "Only in stage"
BEFORE, AFTER = "Not within days before harvest", "Not within days after operation"

CATEGORIES = ("Spraying", "Weeding", "Fertilising", "Irrigation", "Harvesting", "Pruning", "Feeding", "Other")


class RuleBreach(frappe.ValidationError):
	"""A Block (refused) or an unexplained Warn (needs an override reason)."""

	def __init__(self, message, breaches=None, rule_status="Block"):
		super().__init__(message)
		self.breaches = breaches or []
		self.rule_status = rule_status


# -- helpers -------------------------------------------------------------------


def _has(doctype, field) -> bool:
	try:
		return bool(frappe.get_meta(doctype).has_field(field))
	except Exception:
		return False


def _doc_exists(doctype) -> bool:
	return bool(frappe.db.exists("DocType", doctype))


def op_info(operation) -> dict:
	"""{name, label, categories} of an operation; categories is the set of rule categories it belongs to."""
	if not operation:
		return {"name": None, "label": "", "categories": set()}
	row = frappe.db.get_value("Production Operation", operation, ["operation_name", "category"], as_dict=True)
	if not row:
		return {"name": operation, "label": operation, "categories": set()}
	cats = {row.category} if row.category else set()
	return {"name": operation, "label": row.operation_name or operation, "categories": cats}


def _matches(op: dict, operation, category) -> bool:
	if operation and op["name"] == operation:
		return True
	return bool(category) and category in op["categories"]


_RULE_FIELDS = ["name", "crop", "variety", "stage", "operation", "operation_category", "rule_type", "days",
	"other_operation", "other_category", "enforcement", "reason"]


def _crop_rules(crop) -> list:
	if not (crop and _doc_exists("Production Activity Rule")):
		return []
	return frappe.get_all("Production Activity Rule", filters={"crop": crop, "enabled": 1}, fields=_RULE_FIELDS,
		order_by="creation asc")


def _specificity(r) -> tuple:
	return (1 if r.get("variety") else 0, 1 if r.get("operation") else 0, 1 if r.get("stage") else 0)


def _applies_to_variety(r, variety) -> bool:
	return not r.get("variety") or r.get("variety") == variety


def rules_for(crop, variety, operation) -> list:
	"""Enabled rules that govern `operation` on `crop` / `variety`. All matching rules apply, but of rules
	that say the same thing (same type, stage and other operation) only the most specific stays: a
	variety rule beats a crop rule, an operation rule beats a category rule."""
	op = op_info(operation)
	best = {}
	for r in _crop_rules(crop):
		if not _applies_to_variety(r, variety) or not _matches(op, r.operation, r.operation_category):
			continue
		key = (r.rule_type, r.stage or "", r.other_operation or "", r.other_category or "")
		if key not in best or _specificity(r) > _specificity(best[key]):
			best[key] = r
	return list(best.values())


def _reverse_rules(crop, variety, operation) -> list:
	"""'After operation' rules where `operation` is the other side: doing it too close BEFORE the guarded one."""
	op = op_info(operation)
	return [
		r for r in _crop_rules(crop)
		if r.rule_type == AFTER and _applies_to_variety(r, variety)
		and _matches(op, r.other_operation, r.other_category)
		and not _matches(op, r.operation, r.operation_category)
	]


# -- evaluation core -----------------------------------------------------------


def _breach(r, message) -> dict:
	text = message + (f" {r['reason'].strip()}" if r.get("reason") and r["reason"].strip() else "")
	return {"rule": r["name"], "rule_type": r["rule_type"], "enforcement": r["enforcement"], "message": text}


def evaluate(rules, reverse_rules, op, on_date, stage=None, harvest_start=None, others=None, stage_known=True) -> list:
	"""Breaches of `op` (an op_info dict) on `on_date`. `others` is a list of {operation, date, label}
	for work already planned or recorded on the same unit."""
	on_date = getdate(on_date)
	out = []
	for r in rules:
		t = r["rule_type"]
		if t == NOT_IN and stage and stage == r.get("stage"):
			out.append(_breach(r, _("{0} is not allowed in the {1} stage.").format(op["label"], stage)))
		elif t == ONLY_IN and stage_known and stage and stage != r.get("stage"):
			out.append(_breach(r, _("{0} is only allowed in the {1} stage; this block is in {2}.").format(
				op["label"], r.get("stage"), stage)))
		elif t == BEFORE and harvest_start and cint(r.get("days")) > 0:
			hs = getdate(harvest_start)
			if on_date >= add_days(hs, -cint(r["days"])):
				out.append(_breach(r, _("{0} is not allowed within {1} day(s) before harvest (harvest starts {2}).").format(
					op["label"], cint(r["days"]), hs)))
		elif t == AFTER and cint(r.get("days")) > 0:
			for o in others or []:
				if not _matches(o["_info"], r.get("other_operation"), r.get("other_category")):
					continue
				gap = (on_date - getdate(o["date"])).days
				if 0 <= gap < cint(r["days"]):
					out.append(_breach(r, _("{0} is not allowed within {1} day(s) after {2} ({3}).").format(
						op["label"], cint(r["days"]), o["label"], getdate(o["date"]))))
					break
	for r in reverse_rules:
		days = cint(r.get("days"))
		for o in others or []:
			if not _matches(o["_info"], r.get("operation"), r.get("operation_category")):
				continue
			gap = (getdate(o["date"]) - on_date).days
			if 0 <= gap < days:
				out.append(_breach(r, _("{0} on {1} would put {2} ({3}) within {4} day(s) after it.").format(
					op["label"], on_date, o["label"], getdate(o["date"]), days)))
				break
	return out


def worst(breaches) -> str:
	if any(b["enforcement"] == "Block" for b in breaches or []):
		return "Block"
	return "Warn" if breaches else "OK"


# -- context from the database --------------------------------------------------


def _stages_mod():
	try:
		from upande_production.production.logic import stages

		return stages
	except Exception:
		return None


def _cycle_for_unit(unit, on_date):
	if not unit:
		return None
	rows = frappe.get_all("Production Crop Cycle", filters={"unit": unit, "status": ("in", ["Active", "Harvesting"])},
		fields=["name", "start_date"], order_by="start_date desc")
	for r in rows:
		if not r.start_date or getdate(r.start_date) <= getdate(on_date):
			return r.name
	return rows[0].name if rows else None


def _stocking_for_unit(unit, on_date):
	"""The pond's stocking (batch) a date belongs to: the latest started, not yet harvested."""
	if not (unit and _doc_exists("Pond Stocking")):
		return None
	fields = ["name", "stocking_date", "target_harvest_date", "status"]
	if _has("Pond Stocking", "strain"):
		fields.append("strain")
	rows = frappe.get_all("Pond Stocking", filters={"pond": unit, "stocking_date": ("<=", getdate(on_date))},
		fields=fields, order_by="stocking_date desc", limit=1)
	return rows[0] if rows and rows[0].status != "Harvested" else None


def _context(cycle, unit, on_date) -> dict:
	"""crop, variety, stage, harvest_start and the unit for a cycle and/or unit on a date."""
	ctx = {"crop": None, "variety": None, "stage": None, "harvest_start": None, "unit": unit, "cycle": cycle,
		"stage_known": False}
	if not cycle and unit:
		cycle = _cycle_for_unit(unit, on_date)
		ctx["cycle"] = cycle
	if cycle and frappe.db.exists("Production Crop Cycle", cycle):
		cols = ["unit", "crop", "expected_harvest_start"] + (["variety"] if _has("Production Crop Cycle", "variety") else [])
		cy = frappe.db.get_value("Production Crop Cycle", cycle, cols, as_dict=True)
		ctx["unit"] = unit = unit or cy.unit
		ctx["crop"] = cy.crop
		ctx["variety"] = cy.get("variety")
		ctx["harvest_start"] = cy.expected_harvest_start
		st = _stages_mod()
		if st and hasattr(st, "stage_on"):
			try:
				info = st.stage_on(cycle, on_date)
				if info:
					ctx["stage"] = info.get("stage")
					ctx["stage_known"] = bool(info.get("stage"))
			except Exception:
				pass
		if st and hasattr(st, "harvest_start"):
			try:
				ctx["harvest_start"] = st.harvest_start(cycle) or ctx["harvest_start"]
			except Exception:
				pass
	if unit and not ctx["crop"]:
		ctx["crop"] = frappe.db.get_value("Production Unit", unit, "crop")
	if not ctx["cycle"] and unit:
		stk = _stocking_for_unit(unit, on_date)
		if stk:
			ctx["variety"] = stk.get("strain")
			ctx["harvest_start"] = stk.target_harvest_date
			st = _stages_mod()
			if st and ctx["variety"]:  # stages anchored on the stocking date
				try:
					doc = frappe.get_doc("Pond Stocking", stk.name)
					info = st.stage_on(doc, on_date)
					ctx["stage"] = info.get("stage")
					ctx["stage_known"] = bool(info.get("stage"))
					ctx["harvest_start"] = st.harvest_start(doc) or ctx["harvest_start"]
				except Exception:
					pass
	return ctx


def _others(unit, window_from, window_to, exclude_work=None, exclude_task=None) -> list:
	"""Approved + pending work and open planned tasks on a unit in a date window."""
	if not unit:
		return []
	out = []
	vaw = frappe.get_all("Value Adder Work",
		filters={"unit": unit, "docstatus": ("<", 2), "work_date": ("between", [window_from, window_to])},
		fields=["name", "operation", "work_date", "approval_status", "plan_task", "docstatus"])
	for w in vaw:
		if w.name == exclude_work or (w.docstatus == 0 and w.approval_status == "Sent Back"):
			continue
		out.append({"operation": w.operation, "date": w.work_date, "key": w.operation})
	tasks = frappe.get_all("Production Plan Task",
		filters={"parenttype": "Production Work Plan", "unit": unit, "status": ("in", ["Open", "In Progress"]),
			"due_date": ("between", [window_from, window_to])},
		fields=["name", "operation", "due_date"])
	for t in tasks:
		if t.name == exclude_task:
			continue
		out.append({"operation": t.operation, "date": t.due_date, "key": t.operation})
	seen, res = set(), []
	for o in out:
		k = (o["operation"], str(o["date"]))
		if k in seen:
			continue
		seen.add(k)
		info = op_info(o["operation"])
		res.append({**o, "label": info["label"], "_info": info})
	return res


def check(cycle=None, unit=None, operation=None, on_date=None, exclude_work=None, exclude_task=None) -> list:
	"""Breaches `operation` would cause on `on_date` for a cycle and/or unit:
	[{rule, rule_type, enforcement, message}]. Crops without cycles (ponds, hives) get the rules that need no
	stage; ponds use their stocking's strain and target harvest date."""
	if not operation or frappe.flags.get("skip_activity_rules"):
		return []
	on_date = getdate(on_date) if on_date else getdate()
	ctx = _context(cycle, unit, on_date)
	if not ctx["crop"]:
		return []
	rules = rules_for(ctx["crop"], ctx["variety"], operation)
	rev = _reverse_rules(ctx["crop"], ctx["variety"], operation)
	if not (rules or rev):
		return []
	span = max([cint(r.get("days")) for r in rules + rev] + [0]) + 1
	others = _others(ctx["unit"], add_days(on_date, -span), add_days(on_date, span), exclude_work, exclude_task)
	return evaluate(rules, rev, op_info(operation), on_date, ctx["stage"], ctx["harvest_start"], others,
		ctx["stage_known"])


# -- enforcement ----------------------------------------------------------------


def stamp(breaches, override_reason=None) -> dict:
	"""rule_status / rule_notes / override_reason to store on a task or work."""
	status = worst(breaches)
	return {
		"rule_status": status,
		"rule_notes": "\n".join(b["message"] for b in breaches) or None,
		"override_reason": (override_reason or "").strip() or None if status == "Warn" else None,
	}


def enforce(breaches, override_reason=None) -> dict:
	"""Block -> RuleBreach. Warn without a reason -> RuleBreach asking for one. Otherwise the stamp."""
	status = worst(breaches)
	if status == "Block":
		msgs = [b["message"] for b in breaches if b["enforcement"] == "Block"]
		raise RuleBreach(" ".join(msgs), breaches, "Block")
	if status == "Warn" and not (override_reason or "").strip():
		msgs = " ".join(b["message"] for b in breaches)
		raise RuleBreach(
			_("{0} Give a reason (override reason) to go ahead anyway.").format(msgs), breaches, "Warn")
	return stamp(breaches, override_reason)


def breach_payload(e) -> dict:
	return {"breaches": getattr(e, "breaches", []), "rule_status": getattr(e, "rule_status", None),
		"needs_override_reason": getattr(e, "rule_status", None) == "Warn"}


# -- protocol version check -----------------------------------------------------

_BASE = getdate("2000-01-03")


def _timeline(variety) -> tuple[list, int | None]:
	"""[(stage, start_day, end_day_exclusive)] and the day the harvest starts, from the variety's stages."""
	if not (variety and _doc_exists("Production Variety")):
		return [], None
	doc = frappe.get_doc("Production Variety", variety)
	segs, harvest = [], None
	for s in doc.get("stages") or []:
		start = cint(s.start_day)
		segs.append((s.stage, start, start + max(cint(s.length_days), 1)))
		if s.is_harvest and harvest is None:
			harvest = start
	if harvest is None and cint(doc.get("days_to_first_harvest")):
		harvest = cint(doc.days_to_first_harvest)
	return segs, harvest


def _stage_at(segs, day):
	for name, a, b in segs:
		if a <= day < b:
			return name
	return None


def rule_check(protocol) -> list:
	"""Activities of a protocol version that would land in a forbidden stage or window for its variety:
	[{operation, operation_name, repeat, day, stage, rule_status, breaches}]. Days count from the cycle
	start (week N starts on day (N-1)*7); the harvest day is the variety's harvest stage start, else the
	protocol's first harvest activity."""
	proto = frappe.get_doc("Production Protocol", protocol) if isinstance(protocol, str) else protocol
	variety = proto.get("variety") if _has("Production Protocol", "variety") else None
	segs, harvest_day = _timeline(variety)
	steps = []
	for r in proto.get("key_activities") or []:
		steps.append({"operation": r.operation, "k": 0, "day": (max(cint(r.week), 1) - 1) * 7,
			"info": op_info(r.operation)})
	for r in proto.get("cultural_activities") or []:
		if r.schedule != "Interval" or cint(r.interval_weeks) < 1:
			continue
		first = cint(r.establishment_period_weeks) * 7
		horizon = max(harvest_day or 0, 182)
		for k in range(0, 60):
			day = first + k * cint(r.interval_weeks) * 7
			if day > horizon:
				break
			steps.append({"operation": r.operation, "k": k, "day": day, "info": op_info(r.operation)})
	if harvest_day is None:
		hs = [s["day"] for s in steps if frappe.db.get_value("Production Operation", s["operation"], "is_harvest")]
		harvest_day = min(hs) if hs else None
	harvest_start = _BASE + timedelta(days=harvest_day) if harvest_day is not None else None
	out = []
	for s in steps:
		rules = rules_for(proto.crop, variety, s["operation"])
		rev = _reverse_rules(proto.crop, variety, s["operation"])
		if not (rules or rev):
			continue
		others = [
			{"operation": o["operation"], "date": _BASE + timedelta(days=o["day"]), "label": o["info"]["label"],
				"_info": o["info"]}
			for o in steps if o is not s
		]
		stage = _stage_at(segs, s["day"])
		br = evaluate(rules, rev, s["info"], _BASE + timedelta(days=s["day"]), stage, harvest_start, others,
			bool(segs))
		# dates in these messages are synthetic: say "day N" instead
		for b in br:
			b["message"] = _daywise(b["message"])
		if br:
			out.append({"operation": s["operation"], "operation_name": s["info"]["label"],
				"repeat": s["k"] + 1, "day": s["day"], "stage": stage, "rule_status": worst(br), "breaches": br})
	return out


def _daywise(message: str) -> str:
	import re

	def sub(m):
		return f"day {(getdate(m.group(0)) - _BASE).days}"

	return re.sub(r"\d{4}-\d{2}-\d{2}", sub, message)
