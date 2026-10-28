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
from upande_production.production.logic import plans, work
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
			"yield_uom": crop["uom"], "default_cycle_type": crop["cycle_type"], "enabled": 1, "sort_order": crop["sort"]})
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
		u = unit(pond, "Aquaculture", "Pond", area_ha=0.1)
		cycle(u, "Aquaculture", "Pond Cycle", "Tilapia", ago, status, "Pond Cycle", harvest_off=180)
	for grp, ago, status in DEMO["hives"]:
		u = unit(grp, "Apiary", "Hive Group", plant_count=400)
		cycle(u, "Apiary", "Hive Season", "Honey", ago, status, "Hive Season", harvest_off=90)
	frappe.db.commit()


def _weeks():
	"""(year, week, monday, is_current), oldest first."""
	mon = _monday(today())
	out = []
	for k in (3, 2, 1, 0):
		m = mon - timedelta(weeks=k)
		y, w = iso_of(m)
		out.append((y, w, m, k == 0))
	return out


def _fit(dt):
	return min(dt, now_datetime())


def _process_plan(plan_name, current, vas, supers):
	cfg = DEMO["status_mix"]
	td = getdate(today())
	doc = frappe.get_doc("Production Plan", plan_name)
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
	doc = frappe.get_doc("Production Plan", plan_name)
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
		for y, w, mon, current in _weeks():
			existed = frappe.db.exists("Production Plan", {"crop": crop, "farm": farm, "plan_year": y, "plan_week": w})
			doc = plans.get_or_create_plan(crop, farm, y, w)
			if not existed:
				C["Production Plan"] += 1
			C["Production Plan Task"] += plans.generate_week(doc.name)
			_process_plan(doc.name, current, vas, supers)
			frappe.db.commit()


def seed_production_data():
	td = getdate(today())
	mon = _monday(td)
	prices = DEMO["prices"]
	harvest_status = frappe.get_all("Production Crop Cycle", filters={"status": "Harvesting"},
		fields=["name", "unit", "item", "crop"])
	for cy in harvest_status:
		u = frappe.db.get_value("Production Unit", cy.unit, ["area_ha", "plant_count"], as_dict=True)
		y = DEMO["weekly_yield"][cy.item]
		base = (u.plant_count or 0) * y if cy.item in ("Hass Avocado", "Fuerte Avocado") else (
			y if cy.item in ("Tilapia", "Honey") else (u.area_ha or 1) * y)
		weeks_back = 3 if cy.crop == "Avocado" else 6
		for k in range(weeks_back):
			d = mon - timedelta(weeks=k) + timedelta(days=2)
			if d > td:
				d = td
			if frappe.db.exists("Production Harvest", {"unit": cy.unit, "harvest_date": d, "item": cy.item}):
				continue
			r = _rng(f"harvest:{cy.unit}:{d}")
			_insert({"doctype": "Production Harvest", "harvest_date": d, "unit": cy.unit, "cycle": cy.name,
				"item": cy.item, "qty": round(base * r.uniform(0.8, 1.2), 1), "uom": "Kg",
				"grade": "Class 1", "price_per_uom": prices[cy.item]})
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
		basis, size, yld = DEMO["samples"][cy.item]
		n = 2 if cy.item in ("Hass Avocado", "Fuerte Avocado") else 3
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
	offers = [("Twiga Foods", "Potatoes", 45, 4000), ("Kakuzi Export", "Hass Avocado", 120, 2500), ("Twiga Foods", "Passion Fruit", 110, 900)]
	crop_of = {"Potatoes": "Fruits & Vegetables", "Hass Avocado": "Avocado", "Passion Fruit": "Fruits & Vegetables"}
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


def run(reset: bool = False) -> dict:
	if reset:
		frappe.throw("reset is not supported by the demo seed")
	C.clear()
	frappe.flags.in_demo_seed = True
	for step in (seed_masters, seed_people, seed_units_and_cycles, seed_plans, seed_production_data, seed_journals):
		step()
		print(f"[seed] {step.__name__} done")
	frappe.db.commit()
	out = dict(C)
	print("[seed] created:")
	for k, v in sorted(out.items()):
		print(f"   {k}: {v}")
	return out
