"""Idempotent demo seed for the Mutara site. Run:

bench --site mutara.local execute upande_production.production.demo.seed.run
"""

import math
import random
from collections import Counter
from datetime import datetime, time, timedelta

import frappe
from frappe.utils import add_days, getdate, now_datetime, today

from upande_production.production.demo.config import DEMO
from upande_production.production.logic import cycles as cycles_logic, plans, work
from upande_production.production.logic.stages import product_item
from upande_production.production.logic.weeks import iso_of

C = Counter()


def _rng(key):
	return random.Random(f"{DEMO['seed']}:{key}")


def _insert(doc_dict, label=None, submit=False):
	doc = frappe.get_doc(doc_dict)
	doc.insert(ignore_permissions=True)
	if submit:
		doc.submit()
	C[label or doc_dict["doctype"]] += 1
	return doc


def _ensure(doctype, filters, values=None, submit=False):
	name = frappe.db.get_value(doctype, filters)
	if name:
		return name
	data = {"doctype": doctype, **(filters if isinstance(filters, dict) else {"name": filters}), **(values or {})}
	return _insert(data, submit=submit).name


def _monday(d):
	d = getdate(d)
	return d - timedelta(days=d.weekday())


# ---------------------------------------------------------------- sections

def seed_masters():
	company = DEMO["company"]
	farm = DEMO["farm"]
	for uom in DEMO["uoms"]:
		_ensure("UOM", {"uom_name": uom}) if not frappe.db.exists("UOM", uom) else None
	_ensure("Item Group", {"item_group_name": "Products"}, {"parent_item_group": "All Item Groups"})
	for item in DEMO["items"]:
		if not frappe.db.exists("Item", item):
			_insert({"doctype": "Item", "item_code": item, "item_name": item, "item_group": "Products",
				"stock_uom": "Kg", "is_stock_item": 1, "include_item_in_manufacturing": 0})
	for cust in DEMO["customers"]:
		if not frappe.db.exists("Customer", {"customer_name": cust}):
			_insert({"doctype": "Customer", "customer_name": cust, "customer_type": "Company",
				"customer_group": "Commercial", "territory": "Kenya"})
	if not frappe.db.exists("Farm", farm["name"]):
		_insert({"doctype": "Farm", "farm_name": farm["name"], "company": company, "abbreviation": farm["abbr"],
			"area": farm["area"], "farm_type": [{"farm_type": t} for t in ("Has Blocks", "Has Beds", "Has Orchard Trees")]})
	if not frappe.db.get_single_value("Production Settings", "company"):
		frappe.db.set_single_value("Production Settings", "company", company)
	for crop in DEMO["crops"]:
		_ensure("Production Crop", {"crop_name": crop["name"]}, {
			"crop_key": crop["key"], "accent_color": crop["accent"], "icon_key": crop["icon"],
			"parent_unit_label": crop["parent"], "unit_label": crop["unit"], "sub_unit_label": crop["sub"],
			"yield_uom": crop["uom"], "default_cycle_type": crop["cycle_type"], "enabled": 1, "sort_order": crop["sort"],
			"uses_crop_cycles": crop.get("cycles", 1)})
		frappe.db.set_value("Production Crop", {"crop_name": crop["name"]}, "uses_crop_cycles", crop.get("cycles", 1))
	for crop, ops in DEMO["operations"].items():
		for name, uom, rate, cat, harvest in ops:
			if not frappe.db.exists("Production Operation", {"crop": crop, "operation_name": name}):
				_insert({"doctype": "Production Operation", "crop": crop, "operation_name": name,
					"category": cat, "work_uom": uom, "default_rate": rate, "is_harvest": harvest})
	for pname, (crop, item, steps) in DEMO["protocols"].items():
		if frappe.db.exists("Production Protocol", pname):
			continue
		rows = []
		for op, off, every, count, qty in steps:
			rows.append({"operation": frappe.db.get_value("Production Operation", {"crop": crop, "operation_name": op}),
				"day_offset": off, "repeat_every_days": every, "repeat_count": count, "planned_qty": qty})
		_insert({"doctype": "Production Protocol", "protocol_name": pname, "crop": crop, "item": item, "steps": rows})
	frappe.db.commit()


def seed_people():
	company = DEMO["company"]
	for g in ("Male", "Female"):
		if not frappe.db.exists("Gender", g):
			_insert({"doctype": "Gender", "gender": g})
	for et in ("Casual",):
		if not frappe.db.exists("Employment Type", et):
			_insert({"doctype": "Employment Type", "employee_type_name": et})
	for d in ("Value Adder", "Production Supervisor"):
		if not frappe.db.exists("Designation", d):
			_insert({"doctype": "Designation", "designation_name": d})

	def mk(first, last, gender, designation, etype, idx):
		if frappe.db.exists("Employee", {"first_name": first, "last_name": last, "company": company}):
			return
		r = _rng(f"emp:{first}:{last}")
		dob = getdate("1980-01-01") + timedelta(days=r.randint(0, 22 * 365))
		doj = getdate("2023-01-01") + timedelta(days=r.randint(0, 3 * 365 - 120))
		_insert({"doctype": "Employee", "first_name": first, "last_name": last, "gender": gender,
			"date_of_birth": dob, "date_of_joining": doj, "company": company, "status": "Active",
			"designation": designation, "employment_type": etype})

	for i, (f, l, g) in enumerate(DEMO["value_adders"]):
		mk(f, l, g, "Value Adder", "Casual", i)
	for i, (f, l, g) in enumerate(DEMO["supervisors"]):
		mk(f, l, g, "Production Supervisor", "Full-time", i)
	frappe.db.commit()

	if not frappe.db.exists("Role", "Production Manager"):
		_insert({"doctype": "Role", "role_name": "Production Manager"})
	users = ["Administrator"] + [
		u for u in frappe.get_all("User", filters={"enabled": 1}, pluck="name") if u.lower().endswith("@upande.com")]
	for u in users:
		if not frappe.db.exists("Has Role", {"parent": u, "role": "Production Manager", "parenttype": "User"}):
			frappe.get_doc("User", u).add_roles("Production Manager")
			C["Has Role"] += 1
	frappe.db.commit()


def _employees(designation):
	return frappe.get_all("Employee", filters={"designation": designation, "company": DEMO["company"], "status": "Active"},
		pluck="name", order_by="first_name, last_name")


def seed_units_and_cycles():
	company, farm = DEMO["company"], DEMO["farm"]["name"]
	td = getdate(today())
	items = {}

	def unit(name, crop, utype, **kw):
		if not frappe.db.exists("Production Unit", name):
			_insert({"doctype": "Production Unit", "unit_name": name, "crop": crop, "unit_type": utype,
				"farm": farm, "company": company, "status": "Active", **kw})
		return name

	def cycle(u, crop, ctype, item, start_ago, status, protocol, harvest_off=None, plant_count=None, prev=None):
		start = add_days(td, -start_ago)
		name = frappe.db.get_value("Production Crop Cycle", {"unit": u, "start_date": start})
		if name:
			return name
		vals = {"doctype": "Production Crop Cycle", "unit": u, "cycle_type": ctype, "item": item, "start_date": start,
			"status": status, "protocol": protocol, "plant_count": plant_count, "previous_cycle": prev}
		if harvest_off is not None:
			vals["expected_harvest_start"] = add_days(start, harvest_off)
			vals["expected_harvest_end"] = add_days(start, harvest_off + 35)
		return _insert(vals).name

	# avocado
	for b in DEMO["avocado_blocks"]:
		u = unit(b["name"], "Avocado", "Orchard Block", area_ha=b["area"], plant_count=b["trees"], avocado_block_code=b["code"])
		if not frappe.db.exists("Avocado Yield Block", b["code"]):
			_insert({"doctype": "Avocado Yield Block", "block_code": b["code"], "farm": farm, "variety": b["variety"],
				"status": "Active", "area_ha": b["area"], "total_trees": b["trees"], "live_trees": b["trees"],
				"bearing_trees": b["trees"], "planting_year": 2018})
		cycle(u, "Avocado", "Season", b["item"], b["start_ago"], "Harvesting", "Avocado Season", plant_count=b["trees"], harvest_off=80)
	frappe.db.commit()

	# fruits & vegetables
	proto_item = {p: v[1] for p, v in DEMO["protocols"].items()}
	harvest_off = {"Potato": 100, "Cabbage": 85, "Onion": 120, "Passion": 0}
	for pname, area in DEMO["pivots"]:
		unit(pname, "Fruits & Vegetables", "Pivot", is_group=1, area_ha=area)
		n = pname.split()[1]
		for i in range(1, 5):
			bname = f"P{n}-B{i}"
			proto, ago, status, prev_item = DEMO["fv_cycles"][bname]
			plants = int(area / 4 * 1600) if proto == "Passion" else None
			u = unit(bname, "Fruits & Vegetables", "Pivot Block", parent_production_unit=pname, area_ha=area / 4, plant_count=plants)
			prev = None
			if prev_item:
				prev = cycle(u, "Fruits & Vegetables", "Planting", prev_item, ago + 260, "Closed", None, plant_count=None)
			cycle(u, "Fruits & Vegetables", "Season" if proto == "Passion" else "Planting", proto_item[proto], ago,
				status, proto, harvest_off=harvest_off[proto], plant_count=plants, prev=prev)
	frappe.db.commit()

	for pond, ago, status in DEMO["ponds"]:
		unit(pond, "Aquaculture", "Pond", area_ha=0.1)
		# ponds and hives run without crop cycles
	for grp, ago, status in DEMO["hives"]:
		unit(grp, "Apiary", "Hive Group", plant_count=400)
	frappe.db.commit()
	cycles_logic.remove_cycles_for_cycleless_crops()


def _weeks(crop=None):
	"""(year, week, monday, is_current), oldest first. The lead crop reaches further back."""
	mon = _monday(today())
	out = []
	back = DEMO["avocado_history"]["weeks"] - 1 if crop == DEMO["lead_crop"] else 3
	for k in range(back, -1, -1):
		m = mon - timedelta(weeks=k)
		y, w = iso_of(m)
		out.append((y, w, m, k == 0))
	return out


def _fit(dt):
	return min(dt, now_datetime())


def _process_plan(plan_name, current, vas, supers):
	cfg = DEMO["status_mix"]
	td = getdate(today())
	doc = frappe.get_doc("Production Work Plan", plan_name)
	todo = [(t.name, t.protocol_ref, getdate(t.due_date), float(t.planned_qty or 1))
		for t in doc.tasks if t.status == "Open" and not t.done_qty]
	adjust = {}
	for tname, ref, due, planned in todo:
		if due > td:
			continue
		r = _rng(f"task:{ref}")
		roll = r.random()
		if current:
			outcome = "done" if roll < 0.55 else ("prog" if roll < 0.80 else "open")
		else:
			outcome = ("done" if roll < cfg["done"] else "late" if roll < cfg["late"]
				else "partial" if roll < cfg["partial"] else "skipped")
		if outcome == "open":
			continue
		wdate, status, entries = due, "Done", []
		if outcome in ("done", "late", "partial"):
			if outcome == "partial":
				total, status, wdate = planned * r.uniform(0.4, 0.7), "Partly Done", due + timedelta(days=1)
			else:
				total = planned * r.uniform(1.0, 1.08)
				if outcome == "late":
					wdate = due + timedelta(days=r.choice([2, 3]))
			wdate = min(wdate, td)
			n = r.randint(1, 3)
			each = math.ceil(total / n * 100) / 100
			entries = [{"employee": e, "qty": each, "hours": round(each and r.uniform(2, 8), 1)} for e in r.sample(vas, n)]
		elif outcome == "skipped":
			status = "Skipped"
		else:
			status = "In Progress"
		res = work.record_task_work(plan_name, tname, status, entries, work_date=wdate)
		C["Value Adder Work"] += len(res["work"])
		started = datetime.combine(due, time(7, r.randint(0, 59)))
		if status == "In Progress":
			adjust[tname] = (started, None)
		elif outcome == "late":
			adjust[tname] = (started, datetime.combine(wdate, time(15, 30)))
		else:
			adjust[tname] = (started, datetime.combine(wdate, time(13 + r.randint(0, 3), 10)))
	doc = frappe.get_doc("Production Work Plan", plan_name)
	changed = bool(adjust)
	for t in doc.tasks:
		if t.name in adjust:
			s, c = adjust[t.name]
			t.started_at = _fit(s)
			t.completed_at = _fit(c) if c else None
		if not t.supervisor and supers:
			t.supervisor = supers[int(t.idx) % len(supers)]
			changed = True
	if changed:
		doc.save()


def seed_plans():
	farm = DEMO["farm"]["name"]
	vas, supers = _employees("Value Adder"), _employees("Production Supervisor")
	for crop in [c["name"] for c in DEMO["crops"]]:
		pool = _avocado_crew() if crop == DEMO["lead_crop"] else vas
		for y, w, mon, current in _weeks(crop):
			existed = frappe.db.exists("Production Work Plan", {"crop": crop, "farm": farm, "plan_year": y, "plan_week": w})
			doc = plans.get_or_create_plan(crop, farm, y, w)
			if not existed:
				C["Production Work Plan"] += 1
			C["Production Plan Task"] += plans.generate_week(doc.name)
			_process_plan(doc.name, current, pool, supers)
			frappe.db.commit()


def _avocado_crew():
	"""The 12 or so value adders who work the lead crop's blocks (a stable pick, so reruns agree)."""
	crew = _employees("Value Adder")
	return _rng("avocado-crew").sample(crew, min(DEMO["avocado_history"]["crew"], len(crew)))


def _keep_to_crew(crop, crew):
	"""Plan-driven work was keyed with anyone on the farm; a block is worked by a crew, so move entries
	from other people onto the crew (never twice onto one card). A no-op once everything is on the crew."""
	rows = frappe.db.sql(
		"""select name, employee, ifnull(plan_task, concat(unit, '|', operation, '|', work_date)) k
		from `tabValue Adder Work` where crop = %s and docstatus < 2 order by name""", (crop,), as_dict=True)
	on_card = {}
	for r in rows:
		on_card.setdefault(r.k, set()).add(r.employee)
	names = {e: frappe.db.get_value("Employee", e, "employee_name") for e in crew}
	i = 0
	for r in rows:
		if r.employee in crew:
			continue
		for _ in range(len(crew)):
			emp = crew[i % len(crew)]
			i += 1
			if emp not in on_card[r.k]:
				break
		else:
			continue
		on_card[r.k].discard(r.employee)
		on_card[r.k].add(emp)
		frappe.db.sql("update `tabValue Adder Work` set employee = %s, employee_name = %s where name = %s",
			(emp, names[emp], r.name))
		C["VAW moved to avocado crew"] += 1


def seed_avocado_history():
	"""Unplanned work for the lead crop's blocks over the trailing weeks (the plan-driven work only
	covers what the protocol schedules). Entries stay drafts; seed_approvals then approves the old
	ones like the rest. Idempotent: a (block, operation, day) that already has unplanned work is skipped."""
	crop, cfg = DEMO["lead_crop"], DEMO["avocado_history"]
	td = getdate(today())
	crew = _avocado_crew()
	_keep_to_crew(crop, crew)
	last = add_days(td, -cfg["last_day_ago"])
	for b in DEMO["avocado_blocks"]:
		unit = b["name"]
		cycle = frappe.db.get_value("Production Crop Cycle", {"unit": unit, "crop": crop}, "name")
		for k in range(cfg["weeks"], 0, -1):
			mon = _monday(td) - timedelta(weeks=k)
			for op_name, (prob, picks, (lo, hi), step) in cfg["jobs"].items():
				op = frappe.db.get_value("Production Operation", {"crop": crop, "operation_name": op_name}, "name")
				if not op:
					continue
				r = _rng(f"avh:{unit}:{k}:{op_name}")
				if r.random() > prob:
					continue
				days = r.sample(range(0, 6), picks)
				for d in sorted(days):
					day = mon + timedelta(days=d)
					if day > last or frappe.db.exists("Value Adder Work", {
							"unit": unit, "operation": op, "work_date": day, "plan_task": ("is", "not set")}):
						continue
					n = r.randint(*cfg["crew_per_job"])
					entries = []
					for emp in r.sample(crew, n):
						qty = round(r.uniform(lo, hi) / step) * step
						entries.append({"employee": emp, "qty": max(step, qty), "hours": round(r.uniform(*cfg["hours"]), 1)})
					names = work.record_unplanned_work(unit, op, entries, day)
					if cycle:
						frappe.db.sql("update `tabValue Adder Work` set cycle = %s where name in %s", (cycle, tuple(names)))
					C["Value Adder Work (avocado history)"] += len(names)
		frappe.db.commit()


def _backdate(names, created, reviewed=None):
	"""Make demo work look keyed (and reviewed) on the day it was done, not when the seed ran."""
	now = now_datetime()
	created = min(created, now)
	frappe.db.sql("update `tabValue Adder Work` set creation = %s where name in %s", (created, tuple(names)))
	if reviewed:
		frappe.db.sql("update `tabValue Adder Work` set reviewed_at = %s where name in %s",
			(min(reviewed, now), tuple(names)))


def seed_approvals():
	"""Leave a realistic approval mix: old work Approved, recent work a handful Pending (some stale,
	3-4 days old) and one or two Sent Back with a note. Idempotent: skips once a Sent Back entry exists."""
	cfg = DEMO["approval_mix"]
	td = getdate(today())
	users = DEMO["keying_users"]
	rows = frappe.db.sql(
		"""select name, docstatus, approval_status, plan, plan_task, crop, unit, operation, work_date
		from `tabValue Adder Work` where docstatus < 2 order by work_date, name""", as_dict=True)
	groups = {}
	for r in rows:
		groups.setdefault(r.plan_task or f"{r.unit}|{r.operation}|{r.work_date}", []).append(r)
	crops = sorted({r.crop for r in rows})
	touched = set()

	def key_as(g, crop, i):
		user = users[(crops.index(crop) + i) % len(users)]
		frappe.db.sql("update `tabValue Adder Work` set submitted_by = %s where name in %s",
			(user, tuple(r.name for r in g)))

	def approve(g, day):
		for r in g:
			if r.docstatus == 0:
				doc = frappe.get_doc("Value Adder Work", r.name)
				doc.submit()
		names = [r.name for r in g]
		_backdate(names, datetime.combine(day, time(16, 0)), datetime.combine(day + timedelta(days=1), time(9, 30)))
		frappe.db.sql("update `tabValue Adder Work` set reviewed_by = %s where name in %s",
			(users[0], tuple(names)))
		C["VAW approved"] += len(names)

	def demote(g, status, day, note=None):
		names = tuple(r.name for r in g)
		frappe.db.sql(
			"""update `tabValue Adder Work` set docstatus = 0, approval_status = %s, review_note = %s,
			reviewed_by = %s, reviewed_at = %s where name in %s""",
			(status, note, "Administrator" if note else None,
			 now_datetime() - timedelta(hours=5) if note else None, names))
		_backdate(names, datetime.combine(day, time(16, 0)))
		C[f"VAW {status.lower()}"] += len(names)

	mixed = frappe.db.exists("Value Adder Work", {"approval_status": "Sent Back"})
	recent_cut = add_days(td, -cfg["stale_days"][1] - 1)
	by_crop = {}
	for k, g in groups.items():
		by_crop.setdefault(g[0].crop, []).append((k, g))
	for crop, items in by_crop.items():
		for i, (k, g) in enumerate(items):
			key_as(g, crop, i)
			day = getdate(g[0].work_date)
			if day <= recent_cut and any(r.docstatus == 0 and r.approval_status == "Pending" for r in g):
				approve(g, day)
				touched.add((g[0].plan, g[0].plan_task))
	if not mixed:
		# choose the mix from the recent groups, spread across crops, oldest first
		recent = sorted(((g[0].crop, getdate(g[0].work_date), k, g) for items in by_crop.values()
			for k, g in items if getdate(g[0].work_date) > recent_cut), key=lambda x: (x[1], x[0]))
		lo, hi = cfg["stale_days"]
		stale = [x for x in recent if lo <= (td - x[1]).days <= hi]
		fresh = [x for x in recent if (td - x[1]).days < lo]
		picks = {"Pending": [], "Sent Back": []}
		used_crops = {}
		for x in stale:  # at most two stale per crop
			if used_crops.get(x[0], 0) < 2 and len(picks["Pending"]) < cfg["stale_pending"]:
				picks["Pending"].append(x)
				used_crops[x[0]] = used_crops.get(x[0], 0) + 1
		chosen = {x[2] for x in picks["Pending"]}
		sb_crops = set()
		for x in fresh:  # sent back: one per crop, from earlier in the week
			if x[0] not in sb_crops and len(picks["Sent Back"]) < cfg["sent_back"] and (td - x[1]).days >= 1:
				picks["Sent Back"].append(x)
				sb_crops.add(x[0])
		chosen |= {x[2] for x in picks["Sent Back"]}
		fresh_pending = [x for x in fresh if x[2] not in chosen][-cfg["fresh_pending"]:]
		picks["Pending"] += fresh_pending
		chosen |= {x[2] for x in fresh_pending}
		for status, xs in picks.items():
			for n, (crop, day, k, g) in enumerate(xs):
				note = DEMO["sent_back_notes"][n % len(DEMO["sent_back_notes"])] if status == "Sent Back" else None
				demote(g, status, day, note) if g[0].docstatus == 1 else frappe.db.sql(
					"""update `tabValue Adder Work` set approval_status = %s, review_note = %s, reviewed_by = %s,
					reviewed_at = %s where name in %s""",
					(status, note, "Administrator" if note else None,
					 now_datetime() - timedelta(hours=5) if note else None, tuple(r.name for r in g)))
				_backdate([r.name for r in g], datetime.combine(day, time(16, 0)))
		for crop, day, k, g in recent:
			if k not in chosen:
				approve(g, day)
		for crop, day, k, g in recent:
			touched.add((g[0].plan, g[0].plan_task))
	frappe.db.commit()
	for plan, task in touched:
		work.refresh_task_done(plan, task)
	frappe.db.commit()
	_ensure_pending(DEMO["lead_crop"], cfg["lead_pending"], cfg["lead_stale"])


def _ensure_pending(crop, want, stale_n):
	"""The demo leads with `crop`: make sure it has `want` Pending cards, `stale_n` of them stale.
	Idempotent (does nothing once enough Pending cards exist). Takes the latest Approved cards and
	reopens them as the supervisor's draft, aged 1-2 days (fresh) or 4 days (stale)."""
	td = getdate(today())
	rows = frappe.db.sql(
		"""select name, docstatus, approval_status, plan, plan_task, unit, operation, work_date
		from `tabValue Adder Work` where crop = %s and docstatus < 2 order by work_date desc, name""",
		(crop,), as_dict=True)
	groups = {}
	for r in rows:
		groups.setdefault(r.plan_task or f"{r.unit}|{r.operation}|{r.work_date}", []).append(r)
	pending = [g for g in groups.values() if all(r.approval_status == "Pending" for r in g)]
	if len(pending) >= want:
		return
	approved = [g for g in groups.values() if all(r.approval_status == "Approved" for r in g)]
	ages = [DEMO["approval_mix"]["stale_days"][1]] * stale_n + [1, 2, 1, 2, 1]
	ages = ages[:want]
	need = want - len(pending)
	ages = ages[len(pending):][:need]
	users = DEMO["keying_users"]
	touched = set()
	for i, (g, age) in enumerate(zip(approved, ages)):
		names = tuple(r.name for r in g)
		frappe.db.sql(
			"""update `tabValue Adder Work` set docstatus = 0, approval_status = 'Pending', review_note = null,
			reviewed_by = null, reviewed_at = null, submitted_by = %s where name in %s""",
			(users[i % len(users)], names))
		_backdate(names, datetime.combine(add_days(td, -age), time(16, 0)))
		C["VAW pending"] += len(names)
		touched.add((g[0].plan, g[0].plan_task))
	frappe.db.commit()
	for plan, task in touched:
		if plan and task:
			work.refresh_task_done(plan, task)
	frappe.db.commit()


def seed_production_data():
	td = getdate(today())
	mon = _monday(td)
	prices = DEMO["prices"]
	harvest_status = frappe.get_all("Production Crop Cycle", filters={"status": "Harvesting"},
		fields=["name", "unit", "item", "crop"])
	# Ponds and hives have no cycles: their output hangs off the unit alone.
	for unit_name, item in (
		[(p[0], "Tilapia") for p in DEMO["ponds"] if p[2] == "Harvesting"]
		+ [(h[0], "Honey") for h in DEMO["hives"] if h[2] == "Harvesting"]
	):
		if frappe.db.exists("Production Unit", unit_name):
			harvest_status.append(frappe._dict(name=None, unit=unit_name, item=item, crop=None))
	for cy in harvest_status:
		if cy.crop == "Avocado":
			# One source of truth: avocado_seed mirrors the Avocado Harvest Log / forecast into
			# Production Harvest / Production Forecast. Nothing invented here.
			continue
		u = frappe.db.get_value("Production Unit", cy.unit, ["area_ha", "plant_count"], as_dict=True)
		prod = product_item(cy.item)  # varieties keep their product's figures
		y = DEMO["weekly_yield"][prod]
		base = (u.plant_count or 0) * y if prod in ("Hass Avocado", "Fuerte Avocado") else (
			y if prod in ("Tilapia", "Honey") else (u.area_ha or 1) * y)
		# Honey and fish harvests are owned by apiary_seed / aquaculture_seed (from their own logs).
		weeks_back = 0 if prod in ("Tilapia", "Honey") else 6
		for k in range(weeks_back):
			d = mon - timedelta(weeks=k) + timedelta(days=2)
			if d > td:
				d = td
			if frappe.db.exists("Production Harvest", {"unit": cy.unit, "harvest_date": d, "item": cy.item}):
				continue
			r = _rng(f"harvest:{cy.unit}:{d}")
			_insert({"doctype": "Production Harvest", "harvest_date": d, "unit": cy.unit, "cycle": cy.name,
				"item": cy.item, "qty": round(base * r.uniform(0.8, 1.2), 1), "uom": "Kg",
				"grade": "Class 1", "price_per_uom": prices[prod]})
		# forecast: 6 weeks back + 6 forward
		season = mon.year
		if not frappe.db.exists("Production Forecast", {"unit": cy.unit, "season": season}):
			rows = []
			for k in range(-6, 6):
				r = _rng(f"fc:{cy.unit}:{k}")
				sign = r.choice([-1, 1])
				rows.append({"week_start": mon + timedelta(weeks=k),
					"expected_qty": round(base * (1 + sign * r.uniform(0.05, 0.25)), 1)})
			_insert({"doctype": "Production Forecast", "unit": cy.unit, "cycle": cy.name, "season": season,
				"source": "Sample", "uom": "Kg", "weeks": rows})
	frappe.db.commit()

	# yield samples
	cycles = frappe.get_all("Production Crop Cycle", filters={"status": ("in", ["Active", "Harvesting"]), "crop": ("in", ["Avocado", "Fruits & Vegetables"])},
		fields=["unit", "item", "name"])
	for cy in cycles:
		prod = product_item(cy.item)
		basis, size, yld = DEMO["samples"][prod]
		n = 2 if prod in ("Hass Avocado", "Fuerte Avocado") else 3
		for i in range(n):
			d = td - timedelta(days=7 * (i + 1) + 2)
			if frappe.db.exists("Yield Sample", {"unit": cy.unit, "sample_date": d}):
				continue
			r = _rng(f"ys:{cy.unit}:{i}")
			_insert({"doctype": "Yield Sample", "sample_date": d, "unit": cy.unit, "cycle": cy.name,
				"growth_stage": "Fruit bulking" if i == 0 else "Maturing", "sample_basis": basis,
				"sample_size": size, "sampled_yield": round(yld * r.uniform(0.85, 1.15), 1), "uom": "Kg"})
	frappe.db.commit()

	# buyer commitments
	# Avocado commitments are made by avocado_seed, scaled to the mirrored forecast.
	offers = [("Twiga Foods", "Potatoes", 45, 4000), ("Twiga Foods", "Passion Fruit", 110, 900)]
	crop_of = {"Potatoes": "Fruits & Vegetables", "Passion Fruit": "Fruits & Vegetables"}
	for k in range(1, 7):
		ws = mon + timedelta(weeks=k)
		for cust, item, price, qty in offers:
			cname = frappe.db.get_value("Customer", {"customer_name": cust})
			if frappe.db.exists("Buyer Commitment", {"customer": cname, "item": item, "week_start": ws}):
				continue
			r = _rng(f"bc:{cust}:{item}:{k}")
			_insert({"doctype": "Buyer Commitment", "customer": cname, "crop": crop_of[item], "item": item,
				"week_start": ws, "committed_qty": round(qty * r.uniform(0.8, 1.25), -1), "uom": "Kg",
				"price_per_uom": price, "status": "Confirmed" if k <= 3 else "Open"})
	frappe.db.commit()

	# avocado fruit counts + forecasts
	for b in DEMO["avocado_blocks"]:
		code = b["code"]
		for i in range(2):
			d = td - timedelta(days=14 * (i + 1))
			if frappe.db.exists("Avocado Fruit Count", {"orchard_block": code, "count_date": d}):
				continue
			r = _rng(f"afc:{code}:{i}")
			fpt, wt = round(r.uniform(65, 95), 1), round(r.uniform(190, 240))
			_insert({"doctype": "Avocado Fruit Count", "naming_series": "AFC-.YYYY.-.####", "orchard_block": code,
				"count_date": d, "trees_counted": 40, "fruit_per_tree": fpt, "avg_fruit_weight_g": wt,
				"drop_pct": 8, "est_kg_per_tree": round(fpt * wt / 1000, 1), "est_block_kg": round(fpt * wt / 1000 * b["trees"]),
				"bearing_trees": b["trees"]})
		if not frappe.db.exists("Avocado Production Forecast", {"orchard_block": code, "season": mon.year}):
			_insert({"doctype": "Avocado Production Forecast", "naming_series": "APF-.YYYY.-.####", "orchard_block": code,
				"season": mon.year, "crop": "Whole Season", "entry_date": td, "expected_kg": b["trees"] * 60, "price_per_kg": 120})
	frappe.db.commit()


def seed_journals():
	td = getdate(today())
	company = DEMO["company"]
	accts = [a for a in DEMO["journal_accounts"] if frappe.db.exists("Account", a)]
	if not accts:
		accts = frappe.get_all("Account", filters={"company": company, "root_type": "Expense", "is_group": 0}, pluck="name", limit=3)
	blocks = [b["name"] for b in DEMO["avocado_blocks"]] + [
		f"P{n}-B{i}" for n in range(1, 5) for i in range(1, 5)]
	for b in blocks:
		tag = f"production-demo:{b}"
		if frappe.db.exists("Journal Entry", {"user_remark": tag, "docstatus": 1}):
			continue
		cc = frappe.db.get_value("Production Unit", b, "cost_center")
		r = _rng(f"je:{b}")
		total = round(r.uniform(15000, 90000), -2)
		n = r.choice([2, 3])
		cuts = sorted(r.sample(range(10, 90), n - 1))
		parts = [b2 - a for a, b2 in zip([0] + cuts, cuts + [100])]
		lines = []
		amt_sum = 0
		for i, p in enumerate(parts):
			amt = round(total * p / 100, 0) if i < n - 1 else total - amt_sum
			amt_sum += amt
			lines.append({"account": accts[(i + r.randint(0, 3)) % len(accts)], "cost_center": cc, "debit_in_account_currency": amt})
		lines.append({"account": DEMO["cash_account"], "credit_in_account_currency": total})
		_insert({"doctype": "Journal Entry", "voucher_type": "Journal Entry", "company": company,
			"posting_date": td - timedelta(days=r.randint(3, 55)), "user_remark": tag, "accounts": lines}, submit=True)
	frappe.db.commit()


def seed_protocol_versions():
	"""Base protocols are Active v1; Avocado gets a pending v2, Fruits & Vegetables a sent-back draft."""
	frappe.db.sql(
		"""update `tabProduction Protocol` set version = 1, version_status = 'Active', protocol_family = name
		where ifnull(protocol_family, '') = ''"""
	)
	from upande_production.production.logic import protocols as P

	manager = "Administrator"

	def draft_of(crop, tweak):
		base = frappe.db.get_value(
			"Production Protocol", {"crop": crop, "version_status": "Active", "version": 1}, "name", order_by="name asc"
		)
		if not base:
			return None
		fam = frappe.db.get_value("Production Protocol", base, "protocol_family")
		if frappe.db.exists("Production Protocol", {"protocol_family": fam, "version": 2}):
			return None
		frappe.set_user(manager)
		name = P.new_version(base)["name"]
		doc = frappe.get_doc("Production Protocol", name)
		tweak(doc)
		doc.save(ignore_permissions=True)
		return name

	def bump_rate(doc):
		for s in doc.steps:
			if "fert" in (frappe.db.get_value("Production Operation", s.operation, "operation_name") or "").lower():
				s.planned_qty = (s.planned_qty or 1) * 1.2
				s.note = "Fertiliser rate +20% after the leaf analysis"
				return
		if doc.steps:
			doc.steps[0].planned_qty = (doc.steps[0].planned_qty or 1) * 1.2
			doc.steps[0].note = "Rate +20% after the leaf analysis"

	def trim(doc):
		if doc.steps:
			doc.steps[-1].repeat_count = max(int(doc.steps[-1].repeat_count or 1) - 1, 1)
			doc.steps[-1].note = "One pass fewer"

	avo = frappe.db.get_value("Production Crop", {"crop_key": "avocado"}) or "Avocado"
	fv = frappe.db.get_value("Production Crop", {"crop_key": "fruits-vegetables"}) or "Fruits & Vegetables"
	n = draft_of(avo, bump_rate)
	if n:
		P.submit_for_approval(n)
	n = draft_of(fv, trim)
	if n:
		P.submit_for_approval(n)
		P.send_back(n, "Keep the last pass: grading showed late-season quality drops without it.")
	frappe.set_user("Administrator")
	frappe.db.commit()


def run(reset: bool = False) -> dict:
	if reset:
		frappe.throw("reset is not supported by the demo seed")
	C.clear()
	frappe.flags.in_demo_seed = True
	for step in (seed_masters, seed_people, seed_units_and_cycles, seed_plans, seed_avocado_history, seed_approvals, seed_production_data, seed_journals, seed_protocol_versions):
		step()
		print(f"[seed] {step.__name__} done")
	frappe.db.commit()
	out = dict(C)
	print("[seed] created:")
	for k, v in sorted(out.items()):
		print(f"   {k}: {v}")
	return out
