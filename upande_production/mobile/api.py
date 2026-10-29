"""Mobile (field capture) API. Payload via request JSON, result in frappe.response['data']."""
import frappe
from frappe.utils import cint, getdate, today

from upande_production.production.logic import analytics, approvals, plans, rules, work
from upande_production.production.logic.settings import can_see_pay
from upande_production.production.logic.weeks import iso_of, iso_week_bounds

TASK_FIELDS = [
	"name", "unit", "cycle", "operation", "operation_name", "planned_qty", "done_qty", "pending_qty", "uom",
	"rate", "due_date", "supervisor", "status", "deviation", "note", "rule_status", "rule_notes", "override_reason",
]


def _payload() -> dict:
	return frappe.request.get_json() or {}


def _s(data, key) -> str:
	return str(data.get(key) or "").strip()


def _fail(msg: str, exc: Exception | None = None):
	if exc is not None:
		frappe.db.rollback()
		frappe.log_error(f"{msg}: {exc}")
		frappe.response["data"] = {"error": str(exc)}
	else:
		frappe.response["data"] = {"error": msg}


def _denied(*checks) -> bool:
	"""checks are (doctype, ptype) pairs. On refusal sets the error response and returns True."""
	for doctype, ptype in checks:
		if not frappe.has_permission(doctype, ptype):
			_fail("You do not have permission to do this.")
			return True
	return False


def _strip_pay(rows, *keys):
	if can_see_pay():
		return rows
	for r in rows if isinstance(rows, list) else [rows]:
		for k in keys:
			if k in r:
				r[k] = None
	return rows


def _require(data, *keys) -> str | None:
	for k in keys:
		if not data.get(k) or (isinstance(data.get(k), str) and not data[k].strip()):
			return f"{k.replace('_', ' ').capitalize()} is required."
	return None


def _run(name, fn):
	try:
		frappe.response["data"] = fn()
	except frappe.ValidationError as e:
		frappe.db.rollback()
		frappe.response["data"] = {"error": frappe.utils.strip_html(str(e))}
		if hasattr(e, "breaches"):  # activity rule: Block = cannot save, Warn = send override_reason
			frappe.response["data"].update(rules.breach_payload(e))
	except Exception as e:
		_fail(name + " error", e)


def _stage_info(units, crop=None) -> dict:
	"""{unit: {variety, current_stage, stage_day, days_to_harvest, pre_harvest_days, in_pre_harvest}} from
	each unit's open cycle. stage_day = days into the stage; pre_harvest_days = the longest "not within N
	days before harvest" rule for the variety; in_pre_harvest = harvest is that close (or under way)."""
	out = {}
	if not units:
		return out
	meta = frappe.get_meta("Production Crop Cycle")
	if not meta.has_field("variety"):
		return out
	from upande_production.production.logic import rules, stages

	rows = frappe.get_all(
		"Production Crop Cycle", filters={"unit": ("in", list(units)), "status": ("in", ["Active", "Harvesting"])},
		fields=["name", "unit", "variety", "crop"], order_by="start_date desc",
	)
	crop_of = {r.name: r.crop for r in rows}
	for r in rows:
		if r.unit in out:
			continue
		info = dict(_NO_STAGE, variety=r.variety or None)
		if r.variety:
			try:
				st = stages.stage_on(r.name)
				info["current_stage"] = st["stage"]
				if st["stage"] and st["start"]:
					info["stage_day"] = (getdate(today()) - getdate(st["start"])).days
				hs = stages.harvest_start(r.name)
				if hs:
					info["days_to_harvest"] = (getdate(hs) - getdate(today())).days
				window = max((cint(x.days) for x in rules._crop_rules(crop_of.get(r.name))
					if x.rule_type == rules.BEFORE and rules._applies_to_variety(x, r.variety)), default=0)
				info["pre_harvest_days"] = window or None
				if window and info["days_to_harvest"] is not None:
					info["in_pre_harvest"] = info["days_to_harvest"] <= window
			except Exception:
				frappe.log_error(title="productionStageInfo")
		out[r.unit] = info
	return out


_NO_STAGE = {"variety": None, "current_stage": None, "stage_day": None, "days_to_harvest": None,
	"pre_harvest_days": None, "in_pre_harvest": False}


def _with_stage(row: dict, info: dict) -> dict:
	row.update(info.get(row.get("unit") or row.get("name")) or dict(_NO_STAGE))
	return row


@frappe.whitelist()
def productionListCrops():
	if _denied(("Production Crop", "read")):
		return
	_run("productionListCrops", lambda: frappe.get_all(
		"Production Crop", filters={"enabled": 1},
		fields=["name", "crop_name", "crop_key", "accent_color", "icon_key", "unit_label",
			"sub_unit_label", "yield_uom"],
		order_by="sort_order asc, crop_name asc",
	))


@frappe.whitelist()
def productionListUnits():
	if _denied(("Production Unit", "read")):
		return
	data = _payload()
	err = _require(data, "crop")
	if err:
		return _fail(err)
	def go():
		rows = frappe.get_all(
			"Production Unit", filters={"crop": _s(data, "crop"), "status": "Active"},
			fields=["name", "unit_name", "unit_type", "farm", "is_group", "parent_production_unit",
				"area_ha", "plant_count"],
			order_by="unit_name asc",
		)
		info = _stage_info([r.name for r in rows])
		return [_with_stage(r, info) for r in rows]

	_run("productionListUnits", go)


@frappe.whitelist()
def productionGetWeekPlan():
	if _denied(("Production Work Plan", "read")):
		return
	data = _payload()
	err = _require(data, "crop")
	if err:
		return _fail(err)

	def go():
		crop, farm = _s(data, "crop"), _s(data, "farm")
		cur_year, cur_week = iso_of(today())
		year = cint(data.get("year")) or cur_year
		week = cint(data.get("week")) or cur_week
		start, end = iso_week_bounds(year, week)
		filters = {"crop": crop, "plan_year": year, "plan_week": week}
		filters["farm"] = farm if farm else ("in", ["", None])
		name = frappe.db.get_value("Production Work Plan", filters)
		tasks = []
		if name:
			tasks = frappe.get_all(
				"Production Plan Task", filters={"parent": name, "parenttype": "Production Work Plan"},
				fields=TASK_FIELDS, order_by="due_date asc, idx asc",
			)
			_strip_pay(tasks, "rate")
		return {
			"plan": name, "farm": farm or None, "crop": crop, "year": year, "week": week,
			"week_start": str(start), "week_end": str(end), "tasks": tasks,
		}

	_run("productionGetWeekPlan", go)


@frappe.whitelist()
def productionUpdateTask():
	if _denied(("Production Work Plan", "write")):
		return
	data = _payload()
	err = _require(data, "plan", "task", "status")
	if err:
		return _fail(err)
	if _s(data, "status") not in work.STATUSES:
		return _fail("Status must be one of " + ", ".join(work.STATUSES) + ".")
	if data.get("entries") and _denied(("Value Adder Work", "create")):
		return

	def go():
		res = work.record_task_work(
			_s(data, "plan"), _s(data, "task"), _s(data, "status"),
			data.get("entries") or [], note=_s(data, "note"), work_date=_s(data, "work_date") or None,
			override_reason=_s(data, "override_reason") or None,
		)
		frappe.db.commit()
		task = res["task"]
		return {
			"status": "success", "task": _strip_pay({k: task.get(k) for k in TASK_FIELDS}, "rate"),
			"entries": _task_entries(_s(data, "plan")).get(_s(data, "task"), []),
			"work": res["work"], "approval_status": "Pending" if res["work"] else None,
			"message": f"{task.get('operation_name') or 'Task'} marked {task.get('status')}."
				+ (" Work awaits manager approval." if res["work"] else ""),
		}

	_run("productionUpdateTask", go)


@frappe.whitelist()
def productionRecordUnplannedWork():
	if _denied(("Value Adder Work", "create")):
		return
	data = _payload()
	err = _require(data, "unit", "operation", "entries")
	if err:
		return _fail(err)

	def go():
		names = work.record_unplanned_work(
			_s(data, "unit"), _s(data, "operation"), data.get("entries") or [],
			_s(data, "work_date") or None, _s(data, "note"), override_reason=_s(data, "override_reason") or None,
		)
		frappe.db.commit()
		return {
			"status": "success", "work": names, "approval_status": "Pending",
			"message": f"{len(names)} work record(s) saved, awaiting manager approval.",
		}

	_run("productionRecordUnplannedWork", go)


@frappe.whitelist()
def productionListSentBack():
	"""Work the manager sent back for correction. Supervisors see their own; managers see all."""
	if _denied(("Value Adder Work", "read")):
		return
	data = _payload()

	def go():
		me = None if approvals.is_manager() else frappe.session.user
		res = approvals.list_approvals(
			crop=_s(data, "crop") or None, status="Sent Back", supervisor=me,
			from_date=_s(data, "from_date") or None, to_date=_s(data, "to_date") or None,
		)
		return {"groups": res["groups"], "count": res["counts"]["Sent Back"]}

	_run("productionListSentBack", go)


@frappe.whitelist()
def productionResubmitWork():
	if _denied(("Value Adder Work", "write")):
		return
	data = _payload()
	err = _require(data, "names")
	if err:
		return _fail(err)

	def go():
		res = approvals.resubmit(data.get("names"), data.get("entries") or None)
		frappe.db.commit()
		return {"status": "success", "approval_status": "Pending", "work": res["resubmitted"],
			"message": f"{len(res['resubmitted'])} work record(s) resubmitted for approval."}

	_run("productionResubmitWork", go)


@frappe.whitelist()
def productionRecordHarvest():
	if _denied(("Production Harvest", "create")):
		return
	data = _payload()
	err = _require(data, "unit", "qty")
	if err:
		return _fail(err)
	if float(data.get("qty") or 0) <= 0:
		return _fail("Quantity must be greater than zero.")

	def go():
		unit = _s(data, "unit")
		crop = frappe.db.get_value("Production Unit", unit, "crop")
		uom = _s(data, "uom") or (frappe.db.get_value("Production Crop", crop, "yield_uom") if crop else None)
		doc = frappe.get_doc({
			"doctype": "Production Harvest", "unit": unit, "crop": crop,
			"cycle": _s(data, "cycle") or None, "item": _s(data, "item") or None,
			"qty": float(data.get("qty")), "uom": uom, "grade": _s(data, "grade") or None,
			"harvest_date": _s(data, "harvest_date") or today(),
		})
		doc.insert()
		frappe.db.commit()
		return {"status": "success", "name": doc.name, "value": doc.value, "message": "Harvest recorded."}

	_run("productionRecordHarvest", go)


@frappe.whitelist()
def productionRecordSample():
	if _denied(("Yield Sample", "create")):
		return
	data = _payload()
	err = _require(data, "unit", "sample_basis", "sample_size", "sampled_yield")
	if err:
		return _fail(err)

	def go():
		unit = _s(data, "unit")
		crop = frappe.db.get_value("Production Unit", unit, "crop")
		doc = frappe.get_doc({
			"doctype": "Yield Sample", "unit": unit, "crop": crop,
			"cycle": _s(data, "cycle") or None, "sample_basis": _s(data, "sample_basis"),
			"sample_size": float(data.get("sample_size")),
			"sampled_yield": float(data.get("sampled_yield")),
			"growth_stage": _s(data, "growth_stage") or None,
			"sample_date": _s(data, "sample_date") or today(),
		})
		doc.insert()
		frappe.db.commit()
		return {
			"status": "success", "name": doc.name, "est_unit_yield": doc.est_unit_yield,
			"message": "Sample recorded.",
		}

	_run("productionRecordSample", go)


@frappe.whitelist()
def productionListValueAdders():
	if _denied(("Value Adder Work", "create")):
		return
	data = _payload()

	def go():
		filters = {"status": "Active", "designation": "Value Adder"}
		search = _s(data, "search")
		or_filters = {"employee_name": ("like", f"%{search}%"), "name": ("like", f"%{search}%")} if search else None
		return frappe.get_all(
			"Employee", filters=filters, or_filters=or_filters, fields=["name", "employee_name"],
			order_by="employee_name asc", limit=cint(data.get("limit")) or 0,
		)

	_run("productionListValueAdders", go)


@frappe.whitelist()
def productionListOperations():
	if _denied(("Production Operation", "read")):
		return
	data = _payload()
	err = _require(data, "crop")
	if err:
		return _fail(err)
	_run("productionListOperations", lambda: _strip_pay(frappe.get_all(
		"Production Operation", filters={"crop": _s(data, "crop")},
		fields=["name", "operation_name", "category", "work_uom", "default_rate", "is_harvest", "activity_type", "color"],
		order_by="operation_name asc",
	), "default_rate"))


@frappe.whitelist()
def productionDryMatterTests():
	if _denied(("Dry Matter Test", "read")):
		return
	data = _payload()
	err = _require(data, "crop")
	if err:
		return _fail(err)

	def go():
		from upande_production.api import drymatter

		res = drymatter.list_tests(_s(data, "crop"), _s(data, "unit") or None)
		return res if "error" in res else res["rows"]

	_run("productionDryMatterTests", go)


# -- supervisor planning -------------------------------------------------------

PLAN_TASK_FIELDS = TASK_FIELDS + ["protocol_ref", "started_at", "completed_at"]


def _week_args(data):
	cur_year, cur_week = iso_of(today())
	year, week = cint(data.get("year")) or cur_year, cint(data.get("week")) or cur_week
	try:
		start, end = iso_week_bounds(year, week)
	except ValueError:
		frappe.throw("Not a valid ISO week.", frappe.ValidationError)
	return year, week, start, end


def _find_plan(crop, farm, year, week):
	"""The plan of a week. Without a farm: the farm-less plan, else the crop's only plan for that week."""
	filters = {"crop": crop, "plan_year": year, "plan_week": week}
	if farm:
		return frappe.db.get_value("Production Work Plan", {**filters, "farm": farm})
	rows = frappe.get_all("Production Work Plan", filters=filters, fields=["name", "farm"], order_by="creation asc")
	return next((r.name for r in rows if not r.farm), rows[0].name if rows else None)


def _crop_farm(crop):
	"""The crop's farm when all its units sit on one (Mutara today), so a phone that sends no farm
	still lands on the same week plan as the desk instead of a farm-less one."""
	farms = {f for f in frappe.get_all("Production Unit", filters={"crop": crop}, pluck="farm") if f}
	return farms.pop() if len(farms) == 1 else None


def _plan_for_edit(crop, farm, year, week):
	farm = farm or _crop_farm(crop)
	name = _find_plan(crop, farm, year, week)
	if name:
		return frappe.get_doc("Production Work Plan", name)
	if not frappe.has_permission("Production Work Plan", "create"):
		frappe.throw("You do not have permission to create a plan.", frappe.PermissionError)
	return plans.get_or_create_plan(crop, farm, year, week)


def _my_employee() -> str | None:
	"""The Employee linked to the logged-in user (Employee.user_id), or None."""
	return frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"}, "name")


def _mine(data) -> bool:
	return cint(data.get("mine")) == 1 or str(data.get("mine")).lower() == "true"


def _is_late(t) -> bool:
	if t.deviation == "Late":
		return True
	return t.status in ("Open", "In Progress") and bool(t.due_date) and getdate(t.due_date) < getdate(today())


def _counts(tasks) -> dict:
	return {
		"tasks_total": len(tasks),
		"tasks_open": sum(1 for t in tasks if t.status in ("Open", "In Progress")),
		"tasks_done": sum(1 for t in tasks if t.status in ("Done", "Partly Done", "Skipped")),
		"tasks_pending_approval": sum(1 for t in tasks if (t.pending_qty or 0) > 0),
		"tasks_late": sum(1 for t in tasks if _is_late(t)),
	}


def _task_entries(plan) -> dict:
	"""plan_task -> crew entries recorded so far (drafts, sent back and approved)."""
	pay = can_see_pay()
	by_task = {}
	for w in frappe.get_all(
		"Value Adder Work", filters={"plan": plan, "docstatus": ("<", 2)},
		fields=["name", "plan_task", "employee", "employee_name", "qty", "uom", "hours", "work_date",
			"pay_value", "approval_status", "review_note"],
		order_by="creation asc",
	):
		if not pay:
			w["pay_value"] = None
		by_task.setdefault(w.pop("plan_task"), []).append(w)
	return by_task


@frappe.whitelist()
def productionListWeekPlans():
	"""Plans (weeks) of a crop, newest week first, with task counts. Also says which week is current."""
	if _denied(("Production Work Plan", "read")):
		return
	data = _payload()
	err = _require(data, "crop")
	if err:
		return _fail(err)

	def go():
		crop, farm = _s(data, "crop"), _s(data, "farm")
		cur_year, cur_week = iso_of(today())
		filters = {"crop": crop}
		if farm:
			filters["farm"] = farm
		if cint(data.get("year")):
			filters["plan_year"] = cint(data.get("year"))
		rows = frappe.get_all(
			"Production Work Plan", filters=filters,
			fields=["name", "farm", "plan_year", "plan_week", "week_start", "week_end"],
			order_by="plan_year desc, plan_week desc", limit=cint(data.get("limit")) or 26,
		)
		task_filters = {"parenttype": "Production Work Plan", "parent": ("in", [r.name for r in rows] or [""])}
		mine = _mine(data)
		emp = _my_employee() if mine else None
		if mine:
			task_filters["supervisor"] = emp or "\0no-employee"
		tasks = frappe.get_all(
			"Production Plan Task", filters=task_filters,
			fields=["parent", "status", "deviation", "due_date", "pending_qty"],
		)
		by_plan = {}
		for t in tasks:
			by_plan.setdefault(t.parent, []).append(t)
		for r in rows:
			r.update(_counts(by_plan.get(r.name, [])))
			r["is_current"] = (r.plan_year, r.plan_week) == (cur_year, cur_week)
		return {
			"crop": crop, "current_year": cur_year, "current_week": cur_week, "plans": rows,
			"mine": mine, "employee": emp,
			"current_plan": next((r.name for r in rows if r["is_current"]), None),
		}

	_run("productionListWeekPlans", go)


@frappe.whitelist()
def productionGetPlanDetail():
	"""One week's plan for a crop (optionally one block): tasks grouped by block, each with its crew entries."""
	if _denied(("Production Work Plan", "read")):
		return
	data = _payload()
	err = _require(data, "crop")
	if err:
		return _fail(err)

	def go():
		crop, farm, unit = _s(data, "crop"), _s(data, "farm"), _s(data, "unit")
		year, week, start, end = _week_args(data)
		name = _find_plan(crop, farm, year, week)
		out = {
			"plan": name, "crop": crop, "farm": (frappe.db.get_value("Production Work Plan", name, "farm") if name else farm) or None,
			"year": year, "week": week, "week_start": str(start), "week_end": str(end), "unit": unit or None,
			"tasks_total": 0, "tasks_open": 0, "tasks_done": 0, "tasks_pending_approval": 0,
			"tasks_late": 0, "blocks": [],
		}
		if not name:
			return out
		filters = {"parent": name, "parenttype": "Production Work Plan"}
		if unit:
			filters["unit"] = unit
		mine = _mine(data)
		emp = _my_employee() if mine else None
		out["mine"], out["employee"] = mine, emp
		if mine:
			# only the logged-in supervisor's own tasks (nothing when the user has no Employee link)
			filters["supervisor"] = emp or "\0no-employee"
		tasks = frappe.get_all("Production Plan Task", filters=filters, fields=PLAN_TASK_FIELDS,
			order_by="due_date asc, idx asc")
		crew = _task_entries(name)
		sup = [t.supervisor for t in tasks if t.supervisor]
		sup_names = dict(frappe.get_all("Employee", filters={"name": ("in", sup)},
			fields=["name", "employee_name"], as_list=True)) if sup else {}
		unit_names = dict(frappe.get_all("Production Unit", filters={"crop": crop},
			fields=["name", "unit_name"], as_list=True))
		out.update(_counts(tasks))
		blocks = {}
		for t in tasks:
			row = {k: t.get(k) for k in PLAN_TASK_FIELDS}
			row.update({
				"supervisor_name": sup_names.get(t.supervisor), "is_late": _is_late(t),
				"deviation": t.deviation or None, "entries": crew.get(t.name, []),
				"from_protocol": bool(t.protocol_ref),
			})
			_strip_pay(row, "rate")
			b = blocks.setdefault(t.unit, {"unit": t.unit, "unit_name": unit_names.get(t.unit) or t.unit, "tasks": []})
			b["tasks"].append(row)
		for b in blocks.values():
			b.update(_counts([t for t in tasks if t.unit == b["unit"]]))
		info = _stage_info(list(blocks))
		for b in blocks.values():
			_with_stage(b, info)
			for t in b["tasks"]:
				t.update({k: b[k] for k in _NO_STAGE})
		out["blocks"] = sorted(blocks.values(), key=lambda b: b["unit_name"])
		return out

	_run("productionGetPlanDetail", go)


@frappe.whitelist()
def productionAddTask():
	"""Assign work: add a planned task to a crop's week plan (the plan is created when the week has none)."""
	if _denied(("Production Work Plan", "write")):
		return
	data = _payload()
	err = _require(data, "crop", "unit", "operation", "planned_qty")
	if err:
		return _fail(err)

	def go():
		crop, farm = _s(data, "crop"), _s(data, "farm")
		year, week, start, end = _week_args(data)
		unit, operation = _s(data, "unit"), _s(data, "operation")
		qty = float(data.get("planned_qty") or 0)
		if qty <= 0:
			frappe.throw("Planned quantity must be greater than zero.", frappe.ValidationError)
		if frappe.db.get_value("Production Unit", unit, "crop") != crop:
			frappe.throw("That block does not belong to this crop.", frappe.ValidationError)
		op = frappe.db.get_value("Production Operation", operation, ["crop", "work_uom", "default_rate"], as_dict=True)
		if not op or op.crop != crop:
			frappe.throw("That operation does not belong to this crop.", frappe.ValidationError)
		due = getdate(_s(data, "due_date") or start)
		if not (start <= due <= end):
			frappe.throw(f"Due date must fall in week {week} ({start} to {end}).", frappe.ValidationError)
		supervisor = _s(data, "supervisor") or None
		if supervisor and not frappe.db.exists("Employee", supervisor):
			frappe.throw("Unknown supervisor.", frappe.ValidationError)
		cycle = None
		from upande_production.production.logic.cycles import crop_uses_cycles

		if crop_uses_cycles(crop):
			cycle = frappe.db.get_value("Production Crop Cycle",
				{"unit": unit, "status": ("in", ["Active", "Harvesting"])}, "name")
		stamp = rules.enforce(rules.check(cycle=cycle, unit=unit, operation=operation, on_date=due),
			_s(data, "override_reason"))
		plan = _plan_for_edit(crop, farm, year, week)
		plan.append("tasks", {
			"unit": unit, "cycle": cycle, "operation": operation, "planned_qty": qty, "uom": op.work_uom,
			"rate": op.default_rate, "due_date": due, "supervisor": supervisor, "status": "Open",
			"note": _s(data, "note"), **stamp,
		})
		plan.save()
		frappe.db.commit()
		task = plan.tasks[-1]
		return {
			"status": "success", "plan": plan.name,
			"task": _strip_pay({
				**{k: task.get(k) for k in PLAN_TASK_FIELDS}, "done_qty": task.done_qty or 0,
				"pending_qty": task.pending_qty or 0, "deviation": task.deviation or None,
			}, "rate"),
			"message": f"{task.operation_name or 'Task'} added to week {week}.",
		}

	_run("productionAddTask", go)


@frappe.whitelist()
def productionGeneratePlan():
	"""Generate the week's tasks from the cycles' protocols. Idempotent: steps already planned are skipped."""
	if _denied(("Production Work Plan", "write")):
		return
	data = _payload()
	err = _require(data, "crop")
	if err:
		return _fail(err)

	def go():
		crop, farm = _s(data, "crop"), _s(data, "farm")
		year, week, _start, _end = _week_args(data)
		plan = _plan_for_edit(crop, farm, year, week)
		res = plans.generate_week_detail(plan.name)
		created, skipped = res["created"], res["skipped"]
		frappe.db.commit()
		reason = None
		if not created:
			from upande_production.production.logic.cycles import crop_uses_cycles

			reason = ("This crop does not run in crop cycles, so there are no protocol steps to generate."
				if not crop_uses_cycles(crop) else "Nothing new to generate: every protocol step due this week is already planned.")
		return {
			"status": "success", "plan": plan.name, "created": created, "reason": reason, "skipped": skipped,
			"message": f"{created} task(s) generated from protocols." if created else reason,
		}

	_run("productionGeneratePlan", go)


@frappe.whitelist()
def productionProtocolCheck():
	"""Protocol steps due in a week per block: done / partial / late / skipped / pending_approval / open /
	not_planned. Params: crop, year, week (default: this week), optional unit (block)."""
	if _denied(("Production Work Plan", "read")):
		return
	data = _payload()
	err = _require(data, "crop")
	if err:
		return _fail(err)

	def go():
		year, week, _s0, _e0 = _week_args(data)
		res = analytics.protocol_check(_s(data, "crop"), year, week, _s(data, "unit") or None)
		info = _stage_info([b["unit"] for b in res.get("blocks", [])])
		for b in res.get("blocks", []):
			_with_stage(b, info)
		return res

	_run("productionProtocolCheck", go)
