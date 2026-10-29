"""Idempotent demo chemical and fertiliser stores with a copied product set and opening stock.

bench --site mutara.local execute upande_production.production.demo.stores_seed.run

* "Chemical Store - MUT" and "Fertilizer Store - MUT" under the farm group warehouse (the names SCP's store lookup
  falls back to), mapped on the Mutara Farm (custom_chemical_store / custom_fertilizer_store) when those are empty;
* Item Groups CHEMICALS, Adjuvants (chemical groups) and Foliar Solutions, Fertilizer (foliar groups, which is how SCP
  files fertilisers: category Foliar, issued from the fertiliser store), added to Scouting and Crop Protection Settings
  when missing, so the groups reach the spray plan and the store dashboards;
* items copied from the Kaitet dev site (embedded below, no runtime dependency): stock UOM, Spray Product metadata
  (type, toxicity, re-entry, PHI, rate limits, active ingredients) and the Kaitet valuation rate;
* one Material Receipt per store as opening stock, keyed on its remarks, skipped when it exists.
Item expense defaults use "Chemicals Expense - MUT" when that account exists, otherwise they are left empty.
Kaitet suppliers, prices lists, greenhouse names and BOMs are not copied (SCP builds tank-mix BOMs itself).
"""

import frappe
from frappe.utils import add_days, today

from upande_production.production.logic import harvest as H
from upande_production.production.logic.settings import get_company

# (item code, name, item group, stock uom, valuation rate, opening qty, spray type, toxicity, re-entry hrs,
#  PHI days, lower rate, upper rate, [(active ingredient label, concentration, unit)])
CHEMICALS = [
	('1111112055', 'Metaprop', 'CHEMICALS', 'Kg', 2455.79, 40, 'Fungicide', 'III', 6, 0, 2, 2, [['metalaxyl', 150.0, 'g/kg'], ['Propamocarb hydrochloride [100 g/kg]', 100.0, 'g/kg']]),
	('1110003', 'MELTATOX EC', 'CHEMICALS', 'Litre', 4276.76, 40, 'Fungicide', 'III', 6, 0, 2.5, 2.5, [['dodemorph acetate', 400.0, 'g/L']]),
	('1110005', 'NIMROD 25EC', 'CHEMICALS', 'Litre', 4525.45, 40, 'Fungicide', 'III', 6, 0, 2.5, 2.5, [['bupirimate', 250.0, 'g/L']]),
	('1111101043', 'DAGONIS 125SC', 'CHEMICALS', 'Litre', 9070.9, 40, 'Fungicide', 'III', 6, 0, 0.75, 0.8, [['50g/l Difenoconazole', 50.0, 'g/L'], ['75g/l Fluxapyroxad (Xenium)', 75.0, 'g/L'], ['Difenoconazole [50 g/L]', 50.0, 'g/L'], ['Fluxapyroxad [75 g/L]', 75.0, 'g/L']]),
	('1111112053', 'Orvego', 'CHEMICALS', 'Litre', 9060.41, 40, 'Fungicide', 'I', 12, 0, 0.8, 0.8, [['dimethomorph', 225.0, 'g/L'], ['ametoctradin', 300.0, 'g/L']]),
	('1111111027', 'Revus 250sc', 'CHEMICALS', 'Litre', 8291.44, 40, 'Fungicide', 'III', 6, 0, 0.6, 0.6, [['mandipropamid', 250.0, 'g/L']]),
	('1114001', 'SWITCH 62.5 WG', 'CHEMICALS', 'Kg', 10965.69, 40, 'Fungicide', 'III', 6, 0, 1, 1, [['cyprodinil', 375.0, 'g/kg'], ['Fludioxonil [250 g/kg]', 250.0, 'g/kg']]),
	('1110013', 'THIOVIT JET', 'CHEMICALS', 'Kg', 494.49, 40, 'Fungicide', 'III', 6, 0, 2, 3, [['sulphur', 80.0, '%']]),
	('1114003', 'SCALA 40SC', 'CHEMICALS', 'Litre', 4916.65, 40, 'Fungicide', 'III', 12, 0, 1, 1, [['Pyrimethanil [400 g/L]', 400.0, 'g/L']]),
	('1111133085', 'Gladius 10CS', 'CHEMICALS', 'Litre', 96497.79, 40, 'Insecticide', 'II', 12, 0, 0.75, 0.8, [['flometoquin', 106.0, 'g/L']]),
	('1111122044', 'Levo 2.4SL', 'CHEMICALS', 'Litre', 4766.6, 40, 'Insecticide', 'III', 6, 0, 0.8, 1, [['Oxymatrine [2.4%]', 2.4, '%']]),
	('1111133061', 'Nemguard', 'CHEMICALS', 'Litre', 4500, 40, 'Insecticide', 'IV', 6, 0, 1, 2, []),
	('1111133076', 'EMMARON 300SC', 'CHEMICALS', 'Litre', 7129.47, 40, 'Insecticide', 'II', 12, 0, 0.5, 0.5, [['lufenuron', 20.0, 'g/L'], ['Emamectin [10 g/L]', 10.0, 'g/L']]),
	('1113018', 'MOSPILAN', 'CHEMICALS', 'Kg', 8414.6, 40, 'Insecticide', 'II', 12, 0, 0.25, 0.5, [['acetamiprid', 200.0, 'g/kg']]),
	('1111133073', 'Sivanto Prime', 'CHEMICALS', 'Litre', 7316.94, 40, 'Insecticide', 'II', 12, 0, 1, 1, [['flupyradifurone', 200.0, 'g/L']]),
	('1111133087', 'Thuricide', 'CHEMICALS', 'Kg', 3740.14, 40, 'Insecticide', 'III', 6, 0, 0.5, 0.5, []),
	('4010030041', 'Biopest (Neem Oil)', 'CHEMICALS', 'Litre', 1514.69, 40, 'Insecticide', 'I', 0, 0, 0, 0, []),
	('4010030040', 'Prevail P (Orange Oil)', 'CHEMICALS', 'Litre', 2689.32, 40, 'Insecticide', 'I', 0, 0, 0, 0, []),
	('40100100018', 'Round Up', 'CHEMICALS', 'Litre', 925, 40, '', '', 0, 0, 0, 0, []),
	('4040030065', 'Touchdown Forte 500 SL.', 'CHEMICALS', 'Litre', 1233.33, 40, '', '', 0, 0, 0, 0, []),
	('1111190012', 'Dual Gold', 'CHEMICALS', 'Litre', 1420, 40, '', '', 0, 0, 0, 0, []),
	('1111156005', 'Amisil', 'Adjuvants', 'Kg', 1682.02, 60, 'Adjuvant', 'III', 6, 0, 0.3, 1, [['Organosilicone (group) [800 g/L]', 800.0, 'g/L']]),
	('1115002', 'BB5', 'Adjuvants', 'Litre', 1295.17, 60, 'pH Buffer', 'I', 0, 0, 0, 0, []),
]
FOLIARS = [
	('1010100158', 'Technokel Amino Cab', 'Foliar Solutions', 'Litre', 1744.02, 80, '', '', 4, 0, 1, 1, []),
	('1010100118', 'Tecamin Max', 'Foliar Solutions', 'Litre', 1555.55, 80, 'Insecticide', '', 6, 0, 1, 2, []),
	('1010100117', 'Agriful', 'Foliar Solutions', 'Litre', 1487.84, 80, 'Insecticide', 'I', 0, 0, 5, 5, []),
	('1010100125', 'Agriphyt ZnMn', 'Foliar Solutions', 'Kg', 1682.85, 80, '', '', 0, 0, 1, 2, []),
	('1010030090', 'Easy Grow FF', 'Foliar Solutions', 'Kg', 494.36, 80, '', '', 0, 0, 0, 0, []),
	('1111112044', 'Omex 24-24-18', 'Foliar Solutions', 'Litre', 1430, 80, '', '', 0, 0, 0, 0, []),
	('20100100038', 'Lithovit Boron-10KG', 'Foliar Solutions', 'Kg', 1050.15, 80, '', '', 0, 0, 0, 0, []),
	('10070010018', 'ZINCMAX', 'Foliar Solutions', 'Litre', 836.58, 80, '', '', 0, 0, 0, 0, []),
	('100100330132', 'Crucial - S', 'Foliar Solutions', 'Litre', 1216, 80, '', '', 0, 0, 0, 0, []),
	('20100100010', 'Solubor', 'Foliar Solutions', 'Kg', 484.23, 80, '', '', 0, 0, 0, 0, []),
	('1010100137', 'Ferromax 6% EDDHA', 'Foliar Solutions', 'Kg', 713.53, 80, '', '', 0, 0, 0, 0, []),
]
FERTILISERS = [
	('1010100009', 'MAP', 'Fertilizer', 'Kg', 215.91, 1500, '', '', 0, 0, 0, 0, []),
	('1010100091', 'MKP', 'Fertilizer', 'Kg', 269.1, 1500, '', '', 0, 0, 0, 0, []),
	('1010100127', 'CALCIUM NITRATE', 'Fertilizer', 'Kg', 103.8, 1500, '', '', 0, 0, 0, 0, []),
	('1010100005', 'MAGNESIUM NITRATE', 'Fertilizer', 'Kg', 66.03, 1500, '', '', 0, 0, 0, 0, []),
	('1010100015', 'POTASSIUM SULPHATE', 'Fertilizer', 'Kg', 129.16, 1500, '', '', 0, 0, 0, 0, []),
	('20100100015', 'DAP', 'Fertilizer', 'Kg', 3300.2, 1500, '', '', 0, 0, 0, 0, []),
	('20100100014', 'MOP', 'Fertilizer', 'Kg', 89, 1500, '', '', 0, 0, 0, 0, []),
	('1010100032', 'CAN', 'Fertilizer', 'Kg', 40.07, 1500, '', '', 0, 0, 0, 0, []),
	('1010100057', 'Urea Phosphate', 'Fertilizer', 'Kg', 95.58, 1500, '', '', 0, 0, 0, 0, []),
	('1010100072', 'POTASSIUM NITRATE 13.2.44', 'Fertilizer', 'Kg', 162.18, 1500, '', '', 0, 0, 0, 0, []),
]


DEMO = {
	"parent": "Mutara",
	"chemical_store": "Chemical Store",
	"fertilizer_store": "Fertilizer Store",
	"expense_account": "Chemicals Expense",
	"groups": {"CHEMICALS": "chemical", "Adjuvants": "chemical", "Foliar Solutions": "foliar", "Fertilizer": "foliar"},
	"chemicals": CHEMICALS,
	"foliars": FOLIARS,
	"fertilisers": FERTILISERS,
}
REMARK = "demo-stores:opening:"


def _abbr(company):
	return frappe.db.get_value("Company", company, "abbr")


def seed_stores(company) -> dict:
	"""The two stores, under the farm's group warehouse (or the company root), plus the Farm mapping."""
	abbr = _abbr(company)
	parent = f"{DEMO['parent']} - {abbr}"
	parent = parent if frappe.db.exists("Warehouse", parent) else None
	farm = frappe.db.get_value("Warehouse", parent, "custom_farm") if parent else None
	out = {}
	for key, field in (("chemical_store", "custom_chemical_store"), ("fertilizer_store", "custom_fertilizer_store")):
		name = f"{DEMO[key]} - {abbr}"
		if not frappe.db.exists("Warehouse", name):
			H.new_warehouse(DEMO[key], company, parent=parent, farm=farm)
			out[key + "_created"] = 1
		if farm and frappe.get_meta("Farm").has_field(field) and not frappe.db.get_value("Farm", farm, field):
			frappe.db.set_value("Farm", farm, field, name)
		out[key] = name
	return out


def seed_groups() -> int:
	"""Item Groups and their registration on the crop-protection settings."""
	made = 0
	for group in DEMO["groups"]:
		if not frappe.db.exists("Item Group", group):
			frappe.get_doc({"doctype": "Item Group", "item_group_name": group, "parent_item_group": "All Item Groups",
				"is_group": 0}).insert(ignore_permissions=True)
			made += 1
	settings = frappe.get_doc("Scouting and Crop Protection Settings")
	changed = False
	for group, kind in DEMO["groups"].items():
		table = "chemical_item_groups" if kind == "chemical" else "foliar_item_groups"
		if group not in [r.item_group for r in settings.get(table)]:
			settings.append(table, {"item_group": group})
			changed = True
	if changed:
		settings.flags.ignore_permissions = True
		settings.save()
	return made


def _item(row, company, account):
	code, name, group, uom, rate = row[:5]
	if frappe.db.exists("Item", code):
		# The expense account may appear after the first run: fill a missing default then.
		if account and not frappe.db.get_value("Item Default", {"parent": code, "company": company}, "expense_account"):
			doc = frappe.get_doc("Item", code)
			row = next((d for d in doc.item_defaults if d.company == company), None) or doc.append("item_defaults", {"company": company})
			row.expense_account = account
			doc.save(ignore_permissions=True)
		return 0
	doc = frappe.get_doc({"doctype": "Item", "item_code": code, "item_name": name, "item_group": group,
		"stock_uom": uom, "is_stock_item": 1, "valuation_rate": rate, "standard_rate": rate})
	if account:
		doc.append("item_defaults", {"company": company, "expense_account": account})
	doc.insert(ignore_permissions=True)
	return 1


def _product(row):
	"""The Spray Product (the Item hook may already have made it): fill its metadata, once."""
	code, _name, _group, _uom, _rate, _qty, typ, tox, rei, phi, lo, hi, ingredients = row
	name = frappe.db.get_value("Spray Product", {"item": code}, "name")
	if not name:
		return 0
	doc = frappe.get_doc("Spray Product", name)
	if doc.get("active_ingredients") or doc.type or doc.toxicity or doc.default_upper_rate_limit or doc.reentry_interval_hrs:
		return 0
	if not (typ or tox or rei or phi or lo or hi or ingredients):
		return 0
	doc.type, doc.toxicity = typ or None, tox or None
	doc.reentry_interval_hrs, doc.phi_days = rei, phi
	doc.default_lower_rate_limit, doc.default_upper_rate_limit = lo, hi
	for label, conc, unit in ingredients:
		doc.append("active_ingredients", {"ingredient": label, "concentration": conc, "concentration_unit": unit or None})
	doc.flags.ignore_permissions = True
	doc.save()
	return 1


def _receipt(store, rows, company, remark):
	if frappe.db.exists("Stock Entry", {"remarks": remark, "docstatus": 1}):
		return 0
	items = [{"item_code": r[0], "qty": r[5], "uom": r[3], "t_warehouse": store, "basic_rate": r[4]} for r in rows]
	se = frappe.get_doc({"doctype": "Stock Entry", "stock_entry_type": "Material Receipt", "purpose": "Material Receipt",
		"company": company, "posting_date": add_days(today(), -60), "set_posting_time": 1, "remarks": remark,
		"items": items})
	se.flags.ignore_permissions = True
	se.insert()
	se.submit()
	return sum(r[4] * r[5] for r in rows)


def run(commit=True):
	company = get_company() or frappe.db.get_value("Company", {}, "name")
	out = seed_stores(company)
	out["groups_created"] = seed_groups()
	account = f"{DEMO['expense_account']} - {_abbr(company)}"
	account = account if frappe.db.exists("Account", account) else None
	rows = DEMO["chemicals"] + DEMO["foliars"] + DEMO["fertilisers"]
	out["items_created"] = sum(_item(r, company, account) for r in rows)
	out["products_filled"] = sum(_product(r) for r in rows)
	out["expense_default"] = account or "none (account missing)"
	out["chemical_value"] = _receipt(out["chemical_store"], DEMO["chemicals"], company, REMARK + "chemical")
	out["fertilizer_value"] = _receipt(out["fertilizer_store"], DEMO["foliars"] + DEMO["fertilisers"], company, REMARK + "fertilizer")
	if commit:
		frappe.db.commit()
	print(f"stores seed: {out}")
	return out
