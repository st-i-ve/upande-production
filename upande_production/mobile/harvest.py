"""Harvest app endpoints (crates scanned to a team, closed into a Harvest Batch -> Harvesting stock entry).

Ported from the avocado harvest app's server scripts (`upande_avocado.<fn>`): same function names,
same parameters (JSON body or form), same response shapes. The app only swaps the method prefix to
`upande_production.mobile.harvest.`. Like the scripts, a refusal is a 200 carrying `{"error": ...}`
(with a 4xx status where the script set one), never an exception, so the app's `call()` throws it.

Mapping: farm -> Farm; section -> a pivot (group Production Unit) or, for crops without pivots, the
crop itself ("Avocado"); block -> a leaf Production Unit of a crop that harvests in crates; team ->
Harvest Team (the app's `team_id` parameter is the team *number*, a team's document name also works);
crate -> Harvest Crate; Crate Allocation -> Harvest Crate Scan. After "mark ready" the crates are
`Batched` (they count as collected: this app does not collect or receive).
"""

import frappe
from frappe.utils import add_days, flt, now_datetime, today

from upande_production.production.logic import harvest as H
from upande_production.production.logic.analytics import current_cycles

CRATE_SCAN = "Harvest Crate Scan"
COLLECTED = ("Batched",)
MANAGER_ROLES = {"Production Manager", "Production Supervisor", "System Manager"}


# ---------------------------------------------------------------- plumbing

def _err(msg, status=None):
	if status:
		frappe.local.response["http_status_code"] = status
	return {"error": str(msg)}


def _s(v) -> str:
	return str(v or "").strip()


SAVEPOINT = "harvest_api"


def _begin():
	"""Open a savepoint before writing, so a refusal undoes only this call (never the caller's transaction)."""
	frappe.db.savepoint(SAVEPOINT)
	frappe.local.flags.harvest_savepoint = True


def _fail(label, exc):
	"""A validation refusal is the caller's error (200 + {error}); anything else is logged and a 500."""
	if frappe.local.flags.get("harvest_savepoint"):
		frappe.db.rollback(save_point=SAVEPOINT)
	if isinstance(exc, frappe.ValidationError):
		return _err(frappe.utils.strip_html_tags(str(exc)) or exc.__class__.__name__)
	frappe.log_error(title=f"harvest.{label}", message=frappe.get_traceback())
	return _err(exc, 500)


def _list(v) -> list:
	if isinstance(v, str):
		try:
			v = frappe.parse_json(v)
		except Exception:
			v = [x.strip() for x in v.split(",")]
	return v if isinstance(v, (list, tuple)) else []


def _team(team_id: str) -> str | None:
	"""Harvest Team name from the app's team number (or a team name)."""
	team_id = _s(team_id)
	if not team_id:
		return None
	return frappe.db.get_value("Harvest Team", {"team_number": team_id}) or (
		team_id if frappe.db.exists("Harvest Team", team_id) else None)


def _can_scan() -> bool:
	return frappe.has_permission(CRATE_SCAN, "create")


def _is_manager() -> bool:
	return frappe.session.user == "Administrator" or bool(MANAGER_ROLES & set(frappe.get_roles()))


def _period(period: str):
	"""(period, label, start, end) for the manager report."""
	t = today()
	if period == "yesterday":
		y = add_days(t, -1)
		return "yesterday", "Yesterday", y, y
	if period == "week":
		return "week", "Last 7 days", add_days(t, -7), t
	if period == "month":
		return "month", "Last 30 days", add_days(t, -30), t
	return "today", "Today", t, t


# ---------------------------------------------------------------- farm / section / block

def _crate_units(farm=None, crop=None):
	"""Leaf Production Units of crate crops (not retired), with their section and current item."""
	if crop:
		# The crop's name or its crop_key ("Avocado" / "avocado"), resolved to the stored name: the
		# database matches case-insensitively, the list check below does not.
		crop = (frappe.db.get_value("Production Crop", crop, "name")
			or frappe.db.get_value("Production Crop", {"crop_key": crop}, "name") or crop)
	crops = [crop] if crop else H.crate_crops()
	crops = [c for c in crops if c in H.crate_crops()]
	if not crops:
		return []
	filters = {"crop": ("in", crops), "is_group": 0, "status": ("!=", "Retired")}
	if farm:
		filters["farm"] = farm
	return frappe.get_all("Production Unit", filters=filters,
		fields=["name", "unit_name", "crop", "farm", "cost_center", "parent_production_unit"],
		order_by="crop, unit_name", limit_page_length=0)


@frappe.whitelist()
def get_farms(**kw):
	"""[{name, farm_name, farm_code}] - farms that have blocks to harvest."""
	try:
		farms = sorted({u.farm for u in _crate_units() if u.farm})
		rows = frappe.get_all("Farm", filters={"name": ("in", farms or [""])},
			fields=["name", "farm_name", "abbreviation"], order_by="farm_name asc")
		return [{"name": r.name, "farm_name": r.farm_name or r.name, "farm_code": r.abbreviation or r.name} for r in rows]
	except Exception as e:
		return _fail("get_farms", e)


@frappe.whitelist()
def get_crops(**kw):
	"""[{name, crop_key, label}] - crops that harvest in crates (Configure's crop picker)."""
	try:
		return [{"name": c.name, "crop_key": c.crop_key, "label": c.crop_name} for c in frappe.get_all(
			"Production Crop", filters={"name": ("in", H.crate_crops() or [""])},
			fields=["name", "crop_key", "crop_name"], order_by="sort_order, crop_name")]
	except Exception as e:
		return _fail("get_crops", e)


@frappe.whitelist()
def get_sections(farm=None, crop=None, **kw):
	"""[{name, label, crop}] - a pivot (group unit) holding blocks, or the crop itself when its
	blocks sit directly under the farm (avocado)."""
	try:
		farm_name = H.resolve_farm(farm)
		out, seen = [], set()
		for u in _crate_units(farm_name, _s(crop) or None):
			if u.parent_production_unit:
				key, label = u.parent_production_unit, u.parent_production_unit
			else:
				key = label = u.crop
			if key not in seen:
				seen.add(key)
				out.append({"name": key, "label": label, "crop": u.crop})
		return out
	except Exception as e:
		return _fail("get_sections", e)


@frappe.whitelist()
def get_blocks(farm=None, section=None, crop=None, **kw):
	"""[{name, label, ...}] - blocks of the farm (and section / crop when given). Only crates crops.
	Extra keys beyond name/label: crop, section, item, cost_center."""
	try:
		farm_name = H.resolve_farm(farm)
		if not _s(farm):
			return _err("farm is required")
		section = _s(section)
		items = {}
		out = []
		for u in _crate_units(farm_name, _s(crop) or None):
			sec = u.parent_production_unit or u.crop
			if section and sec != section:
				continue
			if u.crop not in items:
				items[u.crop] = {k: v.item for k, v in current_cycles(u.crop).items()}
			out.append({"name": u.name, "label": u.unit_name, "crop": u.crop, "section": sec,
				"item": items[u.crop].get(u.name), "cost_center": u.cost_center})
		return out
	except Exception as e:
		return _fail("get_blocks", e)


# ---------------------------------------------------------------- teams

@frappe.whitelist()
def get_team_leaders(**kw):
	"""[{employee_code, name, team_number, block, label}]"""
	try:
		out = []
		for t in frappe.get_all("Harvest Team", fields=["team_leader", "team_number", "unit"], order_by="team_number asc"):
			emp = frappe.db.get_value("Employee", t.team_leader, ["employee_name", "name"], as_dict=True)
			if emp:
				out.append({"employee_code": emp.name, "name": emp.employee_name, "team_number": t.team_number,
					"block": t.unit, "label": f"{emp.employee_name} — {t.team_number}"})
		return out
	except Exception as e:
		return _fail("get_team_leaders", e)


@frappe.whitelist()
def get_harvestors(**kw):
	"""[{employee_code, name, team_number, team_id, block, label}] - every picker of every team."""
	try:
		out = []
		for team in frappe.get_all("Harvest Team", fields=["name", "team_number", "unit"], order_by="team_number asc"):
			for m in frappe.get_all("Harvest Team Member", filters={"parent": team.name, "parenttype": "Harvest Team"},
					fields=["employee", "employee_name"], order_by="idx asc"):
				nm = m.employee_name or (m.employee and frappe.db.get_value("Employee", m.employee, "employee_name")) or m.employee
				out.append({"employee_code": m.employee or "", "name": nm or "", "team_number": team.team_number,
					"team_id": team.name, "block": team.unit, "label": f"{nm or ''} — Team {team.team_number}"})
		return out
	except Exception as e:
		return _fail("get_harvestors", e)


# ---------------------------------------------------------------- harvesting state

def _today_start() -> str:
	return f"{today()} 00:00:00"


@frappe.whitelist()
def get_harvesting_state(block=None, **kw):
	"""{totals:{total,filling,full,in_transit,batches,not_collected}, by_harvestor[], batches[], not_collected[]}
	for the block today. `batches` are today's Harvest Batches (`delivery_note` carries the stock entry)."""
	try:
		block = _s(block)
		if not block:
			return _err("block is required", 400)
		crates = frappe.get_all(CRATE_SCAN, filters={"block_ref": block, "creation": (">=", _today_start())},
			fields=["crate_id", "harvestor", "status", "allocated_at"], order_by="allocated_at asc")
		names = {}
		for c in crates:
			if c.harvestor and c.harvestor not in names:
				names[c.harvestor] = frappe.db.get_value("Employee", c.harvestor, "employee_name") or c.harvestor
		by = {}
		for c in crates:
			d = by.setdefault(c.harvestor or "unknown", {"total": 0, "filling": 0, "full": 0, "in_transit": 0})
			d["total"] += 1
			if c.status == "Filling":
				d["filling"] += 1
			elif c.status == "Full":
				d["full"] += 1
		by_harvestor = sorted(
			[{"employee_code": k, "name": names.get(k, k), **v} for k, v in by.items()], key=lambda r: (-r["total"], r["name"]))
		not_collected = [{"crate_id": c.crate_id, "harvestor": c.harvestor or "", "harvestor_name": names.get(c.harvestor, c.harvestor or ""),
			"status": c.status, "allocated_at": str(c.allocated_at) if c.allocated_at else None}
			for c in crates if c.status in H.OPEN_STATUSES]
		batches = frappe.get_all("Harvest Batch", filters={"unit": block, "docstatus": 1, "creation": (">=", _today_start())},
			fields=["name", "stock_entry", "status", "team", "creation", "crate_count", "estimated_kg"], order_by="creation desc")
		return {
			"totals": {"total": len(crates), "filling": sum(c.status == "Filling" for c in crates),
				"full": sum(c.status == "Full" for c in crates), "in_transit": 0, "batches": len(batches),
				"not_collected": len(not_collected)},
			"by_harvestor": by_harvestor,
			"batches": [{"batch_id": b.name, "delivery_note": b.stock_entry, "status": b.status, "team_id": b.team,
				"creation": str(b.creation), "stock_entry": b.stock_entry, "crates": b.crate_count,
				"estimated_kg": b.estimated_kg} for b in batches],
			"not_collected": not_collected,
		}
	except Exception as e:
		return _fail("get_harvesting_state", e)


# ---------------------------------------------------------------- scanning

def _scan_one(crate_id: str, team: str, block: str, harvestor: str | None):
	"""One scan. Returns (scan doc or None, error text or None, extra dict for the single-scan reply)."""
	crate = frappe.db.get_value("Harvest Crate", crate_id, ["name", "status"], as_dict=True)
	if not crate:
		return None, "Not in registry", {}
	if crate.status and crate.status != "Active":
		return None, f"Crate is {crate.status}", {"crate_status": crate.status}
	if frappe.db.exists(CRATE_SCAN, {"crate_id": crate_id, "status": ("in", H.OPEN_STATUSES)}):
		return None, "Crate already in use", {"in_use": True}
	doc = frappe.get_doc({"doctype": CRATE_SCAN, "crate_id": crate_id, "team_id": team, "status": "Filling",
		"allocated_at": now_datetime(), "block_ref": block or None, "harvestor": harvestor or None})
	doc.insert(ignore_permissions=True)
	return doc, None, {}


def _check_scan_inputs(block, harvestor):
	if block:
		try:
			H.crate_unit(block)
		except frappe.ValidationError as e:
			return str(e)
	if harvestor and not frappe.db.exists("Employee", harvestor):
		return f"Picker {harvestor} not found"
	return None


@frappe.whitelist()
def scan_crate(crate_id=None, team_id=None, block=None, harvestor=None, **kw):
	"""{crate_id, status:'Filling', team_id, allocation}. `harvestor` (Employee) optional."""
	try:
		_begin()
		crate_id, team_number, block, harvestor = _s(crate_id), _s(team_id), _s(block), _s(harvestor)
		if not crate_id or not team_number:
			return _err("crate_id and team_id are required")
		if not _can_scan():
			return _err("Not permitted to scan crates", 403)
		team = _team(team_number)
		if not team:
			return _err(f"Team {team_number} not found")
		bad = _check_scan_inputs(block, harvestor)
		if bad:
			return _err(bad)
		doc, error, extra = _scan_one(crate_id, team, block, harvestor)
		if error:
			return _err(f"Crate '{crate_id}' not in registry" if error == "Not in registry" else error) | extra
		return {"crate_id": crate_id, "status": "Filling", "team_id": team, "allocation": doc.name}
	except Exception as e:
		return _fail("scan_crate", e)


@frappe.whitelist()
def scan_crates_bulk(crate_ids=None, team_id=None, block=None, harvestor=None, **kw):
	"""{results:[{crate_id, ok, error, allocation?}], ok_count, fail_count, team_id}.
	`harvestor` (Employee) optional: the picker credited with all the crates in this call."""
	try:
		_begin()
		ids, team_number, block, harvestor = _list(crate_ids), _s(team_id), _s(block), _s(harvestor)
		if not ids or not team_number:
			return _err("crate_ids and team_id are required")
		if not _can_scan():
			return _err("Not permitted to scan crates", 403)
		team = _team(team_number)
		if not team:
			return _err(f"Team {team_number} not found")
		bad = _check_scan_inputs(block, harvestor)
		if bad:
			return _err(bad)
		results, seen = [], set()
		for raw in ids:
			cid = _s(raw)
			row = {"crate_id": cid, "ok": False, "error": None}
			if not cid:
				row["error"] = "Empty crate id"
			elif cid in seen:
				row["error"] = "Duplicate in this batch"
			else:
				seen.add(cid)
				doc, error, _extra = _scan_one(cid, team, block, harvestor)
				if error:
					row["error"] = error
				else:
					row["ok"], row["allocation"] = True, doc.name
			results.append(row)
		ok = sum(r["ok"] for r in results)
		return {"results": results, "ok_count": ok, "fail_count": len(results) - ok, "team_id": team}
	except Exception as e:
		return _fail("scan_crates_bulk", e)


@frappe.whitelist()
def mark_ready_for_collection(block=None, team_id=None, warehouse=None, **kw):
	"""Close the team's open crates for the block into a Harvest Batch and post the Harvesting stock entry.
	{team_id, team_number, resolved_team, block, crate_count, crates_marked, + batch, stock_entry, item,
	estimated_kg, avg_kg_per_crate, production_harvest, warehouse, work}. crate_count 0 and no batch when nothing was open.
	`warehouse` is the store the fruit is received into (from get_stores); default = the farm's last store."""
	try:
		_begin()
		block, team_number = _s(block), _s(team_id)
		if not block or not team_number:
			return {"error": "block and team_id are required", "got_block": block, "got_team": team_number}
		if not _can_scan():
			return _err("Not permitted to close a harvest batch", 403)
		team = _team(team_number)
		if not team:
			return _err(f"Team {team_number} not found")
		batch = H.close_batch(team, block, warehouse=_s(warehouse) or None)
		res = {"team_id": team, "team_number": frappe.db.get_value("Harvest Team", team, "team_number"),
			"resolved_team": team, "block": block, "crate_count": 0, "crates_marked": []}
		if batch:
			res.update({
				"crate_count": batch.crate_count, "crates_marked": [r.crate_id for r in batch.crates],
				"batch": batch.name, "stock_entry": batch.stock_entry, "item": batch.item,
				"estimated_kg": batch.estimated_kg, "avg_kg_per_crate": batch.avg_kg_per_crate,
				"production_harvest": batch.production_harvest, "warehouse": batch.warehouse,
				"work": frappe.get_all("Value Adder Work", filters={"harvest_batch": batch.name}, pluck="name"),
			})
		return res
	except Exception as e:
		return _fail("mark_ready_for_collection", e)


@frappe.whitelist()
def get_stores(block=None, **kw):
	"""{data: [{name, label}], default} - stores a batch can be received into (not block warehouses);
	`default` is the block's farm's last store, else the harvest warehouse in settings."""
	try:
		block = _s(block)
		row = frappe.db.get_value("Production Unit", block, ["farm", "company"], as_dict=True) if block else None
		try:
			default = H.default_store(row.farm if row else None)
		except frappe.ValidationError:  # no last store and no harvest warehouse in settings: the user picks
			frappe.local.message_log = []
			default = ""
		return {"data": H.stores(row.company if row else None), "default": default}
	except Exception as e:
		return _fail("get_stores", e)


# ---------------------------------------------------------------- tallies

@frappe.whitelist()
def get_team_harvest_today(team_id=None, **kw):
	"""{team_id, total, filling, full, ready, in_transit, received} - `ready` = crates already batched."""
	try:
		team_id = _s(team_id)
		if not team_id:
			return _err("team_id is required")
		team = _team(team_id) or team_id
		rows = frappe.get_all(CRATE_SCAN, filters={"team_id": team, "creation": (">=", _today_start())}, fields=["status"])
		n = lambda s: sum(r.status == s for r in rows)  # noqa: E731
		return {"team_id": team_id, "total": len(rows), "filling": n("Filling"), "full": n("Full"),
			"ready": n("Batched"), "in_transit": 0, "received": 0}
	except Exception as e:
		return _fail("get_team_harvest_today", e)


@frappe.whitelist()
def get_harvest_kpis(team_id=None, **kw):
	"""Crate counts today: all, the team's and the caller's; "collected" = batched, "not collected" = still open."""
	try:
		team_id = _s(team_id)
		since = _today_start()
		base = {"creation": (">=", since)}
		c = frappe.db.count
		out = {"total_today": c(CRATE_SCAN, base), "team_total_today": 0, "team_not_collected": 0, "team_collected": 0}
		if team_id:
			team = _team(team_id) or team_id
			out["team_total_today"] = c(CRATE_SCAN, {**base, "team_id": team})
			out["team_not_collected"] = c(CRATE_SCAN, {**base, "team_id": team, "status": ("in", H.OPEN_STATUSES)})
			out["team_collected"] = c(CRATE_SCAN, {**base, "team_id": team, "status": ("in", COLLECTED)})
		me = {**base, "owner": frappe.session.user}
		out.update({"me_total_today": c(CRATE_SCAN, me),
			"me_not_collected": c(CRATE_SCAN, {**me, "status": ("in", H.OPEN_STATUSES)}),
			"me_collected": c(CRATE_SCAN, {**me, "status": ("in", COLLECTED)}),
			"team_id": team_id, "user": frappe.session.user, "date": today()})
		return out
	except Exception as e:
		return _fail("get_harvest_kpis", e)


@frappe.whitelist()
def get_session_info(**kw):
	"""{user, full_name, roles, is_loading_clerk, is_packhouse_receiver, is_farm_manager}. The collecting and
	receiving flags are always false here; `is_farm_manager` replaces the app's 'Farm Manager Lokitela' role test."""
	try:
		user = frappe.session.user
		return {"user": user, "full_name": frappe.db.get_value("User", user, "full_name") or user,
			"roles": frappe.get_roles(user), "is_loading_clerk": False, "is_packhouse_receiver": False,
			"is_farm_manager": _is_manager()}
	except Exception as e:
		return _fail("get_session_info", e)


# ---------------------------------------------------------------- farm manager

def _plan_total(start, end) -> int:
	"""Crates the work plans schedule for the period (tasks of a crate harvest operation)."""
	row = frappe.db.sql(
		"""select sum(t.planned_qty) from `tabProduction Plan Task` t
		join `tabField Activity` o on o.name = t.operation
		where o.is_harvest = 1 and t.uom = 'Crate' and t.due_date between %s and %s""", (start, end))
	return int(flt(row[0][0]) if row and row[0] else 0)


@frappe.whitelist()
def farm_manager_report(period=None, **kw):
	"""Team performance and per-block totals (shape of the avocado script). Mapping of the stages the
	script tracked: in_field = open crates, at_packhouse = crates closed into a batch (stock), on_road
	and returned = 0. Extra: totals.estimated_kg, totals.batches, teams[].estimated_kg."""
	try:
		period, label, start, end = _period(_s(period) or "today")
		ca = "date(ca.allocated_at) between %(s)s and %(e)s"
		args = {"s": start, "e": end}
		agg = ("count(*) as harvested, sum(ca.status in ('Filling','Full')) as in_field, "
			"sum(ca.status = 'Batched') as at_packhouse")
		t = frappe.db.sql(f"select {agg} from `tabHarvest Crate Scan` ca where {ca}", args, as_dict=True)[0]
		team_rows = frappe.db.sql(
			f"""select ca.team_id, tm.team_number, e.employee_name as leader_name, {agg}
			from `tabHarvest Crate Scan` ca
			left join `tabHarvest Team` tm on tm.name = ca.team_id
			left join `tabEmployee` e on e.name = tm.team_leader
			where {ca} and ifnull(ca.team_id, '') != ''
			group by ca.team_id, tm.team_number, e.employee_name""", args, as_dict=True)
		scans = frappe.db.sql(
			f"select ca.team_id, ca.block_ref as block, ca.allocated_at, ca.owner from `tabHarvest Crate Scan` ca "
			f"where {ca} and ifnull(ca.team_id, '') != ''", args, as_dict=True)
		kg_by_team = {r.team: flt(r.kg) for r in frappe.db.sql(
			"select team, sum(estimated_kg) kg from `tabHarvest Batch` where docstatus = 1 and harvest_date between %s and %s group by team",
			(start, end), as_dict=True)}
		meta, users = {}, set()
		for r in scans:
			m = meta.setdefault(r.team_id, {"blocks": {}, "last_at": None, "last_block": None, "last_user": None})
			blk = r.block or "(unknown)"
			m["blocks"][blk] = m["blocks"].get(blk, 0) + 1
			if not m["last_at"] or (r.allocated_at and r.allocated_at > m["last_at"]):
				m["last_at"], m["last_block"], m["last_user"] = r.allocated_at, blk, r.owner
			if r.owner:
				users.add(r.owner)
		names = {u: frappe.db.get_value("User", u, "full_name") or u for u in users}
		plan_total = _plan_total(start, end)
		active = len(team_rows)
		per_team = int(round(plan_total / active)) if active and plan_total > 0 else 0

		teams, changes = [], []
		for r in team_rows:
			h, ap = int(r.harvested or 0), int(r.at_packhouse or 0)
			m = meta.get(r.team_id) or {"blocks": {}, "last_block": None, "last_user": None, "last_at": None}
			blocks = sorted([{"block": b, "crates": n} for b, n in m["blocks"].items()], key=lambda x: -x["crates"])
			lu = m["last_user"] or ""
			entry = {
				"team_id": r.team_id, "team_number": r.team_number or "?", "leader_name": r.leader_name or "",
				"harvested": h, "in_field": int(r.in_field or 0), "on_road": 0, "at_packhouse": ap, "returned": 0,
				"delivery_rate_pct": round(ap / h * 100, 1) if h else None, "target": per_team,
				"progress_pct": round(h / per_team * 100, 1) if per_team else None, "blocks": blocks,
				"block_change": len(blocks) > 1, "current_block": m["last_block"] or "", "last_user": lu,
				"last_user_name": names.get(lu, lu) if lu else "", "last_at": str(m["last_at"]) if m["last_at"] else "",
				"estimated_kg": kg_by_team.get(r.team_id, 0.0),
			}
			teams.append(entry)
			if entry["block_change"]:
				changes.append({k: entry[k] for k in ("team_id", "team_number", "leader_name", "blocks", "current_block",
					"last_user", "last_user_name", "last_at")})

		def order(x):
			p = x["progress_pct"]
			return (2, 0) if p is None else ((1, -p) if p >= 100 else (0, -p))
		teams.sort(key=order)

		blk_rows = frappe.db.sql(
			f"""select ca.block_ref as block, count(*) as harvested, sum(ca.status = 'Batched') as at_packhouse,
			count(distinct ca.team_id) as teams_active from `tabHarvest Crate Scan` ca
			where {ca} and ifnull(ca.block_ref, '') != '' group by ca.block_ref order by harvested desc""", args, as_dict=True)
		blocks = [{"block": r.block, "harvested": int(r.harvested or 0), "at_packhouse": int(r.at_packhouse or 0),
			"delivery_rate_pct": round(int(r.at_packhouse or 0) / int(r.harvested) * 100, 1) if r.harvested else None,
			"teams_active": int(r.teams_active or 0)} for r in blk_rows]
		th, tap = int(t.harvested or 0), int(t.at_packhouse or 0)
		bt = frappe.db.sql("select count(*), sum(estimated_kg) from `tabHarvest Batch` where docstatus = 1 and harvest_date between %s and %s", (start, end))[0]
		return {
			"period": period, "label": label, "plan_total": plan_total, "per_team_target": per_team,
			"active_team_count": active,
			"totals": {"harvested": th, "in_field": int(t.in_field or 0), "on_road": 0, "at_packhouse": tap, "returned": 0,
				"delivery_rate_pct": round(tap / th * 100, 1) if th else None,
				"batches": int(bt[0] or 0), "estimated_kg": flt(bt[1])},
			"teams": teams, "blocks": blocks, "block_changes": changes,
		}
	except Exception as e:
		return _fail("farm_manager_report", e)


@frappe.whitelist()
def lookup_crate_for_fix(crate_id=None, **kw):
	"""{crate_id, doc_name, block, status, team_id, team_number, leader_name, allocated_at, batch_id} - the crate's latest scan."""
	try:
		crate_id = _s(crate_id)
		if not crate_id:
			return _err("crate_id is required", 400)
		s = frappe.db.get_value(CRATE_SCAN, {"crate_id": crate_id},
			["name", "crate_id", "block_ref", "status", "team_id", "harvestor", "allocated_at", "batch_id_ref"],
			order_by="creation desc", as_dict=True)
		if not s:
			return _err(f"Crate {crate_id} not found", 404)
		number = leader = ""
		if s.team_id:
			t = frappe.db.get_value("Harvest Team", s.team_id, ["team_number", "team_leader"], as_dict=True)
			if t:
				number = t.team_number or ""
				leader = (t.team_leader and frappe.db.get_value("Employee", t.team_leader, "employee_name")) or ""
		return {"crate_id": s.crate_id, "doc_name": s.name, "block": s.block_ref or "", "status": s.status or "",
			"team_id": s.team_id or "", "team_number": number, "leader_name": leader,
			"allocated_at": str(s.allocated_at or ""), "batch_id": s.batch_id_ref or ""}
	except Exception as e:
		return _fail("lookup_crate_for_fix", e)


@frappe.whitelist()
def update_crate_block(crate_id=None, new_block=None, **kw):
	"""{ok, crate_id, old_block, new_block, changed_by}. Managers only; a crate already closed into a
	batch cannot move (cancel the batch first)."""
	try:
		_begin()
		crate_id, new_block = _s(crate_id), _s(new_block)
		if not crate_id or not new_block:
			return _err("crate_id and new_block are required", 400)
		if not _is_manager():
			return _err("Permission denied - requires a Production Manager or Supervisor role", 403)
		name = frappe.db.get_value(CRATE_SCAN, {"crate_id": crate_id}, "name", order_by="creation desc")
		if not name:
			return _err(f"Crate {crate_id} not found", 404)
		old, batch = frappe.db.get_value(CRATE_SCAN, name, ["block_ref", "batch_id_ref"])
		if batch:
			return _err(f"Crate {crate_id} is already in batch {batch}; cancel the batch to move it", 409)
		try:
			H.crate_unit(new_block)
		except frappe.ValidationError as e:
			return _err(e, 400)
		frappe.db.set_value(CRATE_SCAN, name, "block_ref", new_block)
		return {"ok": True, "crate_id": crate_id, "old_block": old or "", "new_block": new_block, "changed_by": frappe.session.user}
	except Exception as e:
		return _fail("update_crate_block", e)


@frappe.whitelist()
def bulk_create_crates(count=None, farm=None, prefix=None, width=None, **kw):
	"""{created, first, last, crate_ids}. Ids are PREFIX-00001...; prefix defaults to <farm abbr>-CR."""
	try:
		_begin()
		count = int(count or 0)
		if count <= 0 or count > 2000:
			return _err("count must be between 1 and 2000", 400)
		if not _is_manager():
			return _err("Permission denied - requires a Production Manager or Supervisor role", 403)
		farm = H.resolve_farm(farm) if _s(farm) else None
		prefix = _s(prefix)
		if not prefix:
			prefix = (str(frappe.db.get_value("Farm", farm, "abbreviation") or farm).upper() + "-CR") if farm else "CR"
		width = int(width or 5)
		last = frappe.db.sql("select crate_id from `tabHarvest Crate` where crate_id like %s order by serial_no desc limit 1",
			prefix + "-%", as_dict=True)
		nxt = 1
		if last:
			try:
				nxt = int(str(last[0].crate_id).split("-")[-1]) + 1
			except ValueError:
				nxt = 1
		ids = []
		for i in range(count):
			seq = nxt + i
			cid = f"{prefix}-{str(seq).zfill(width)}"
			frappe.get_doc({"doctype": "Harvest Crate", "crate_id": cid, "serial_no": seq, "status": "Active",
				"farm": farm}).insert(ignore_permissions=True)
			ids.append(cid)
		return {"created": len(ids), "first": ids[0], "last": ids[-1], "crate_ids": ids}
	except Exception as e:
		return _fail("bulk_create_crates", e)
