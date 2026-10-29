"""Idempotent demo data for block warehouses, input issues and an ERP budget.

bench --site mutara.local execute upande_production.production.demo.blocks_seed.run

* every leaf block gets `warehouse` = the warehouse named exactly like its cost centre (created under a
  "Production Blocks" group when it does not exist), so SCP's chemical plan charges the block's cost centre;
* each avocado block gets a fertiliser and a chemical issue (Material Issue from the farm store, cost
  centre = the block), stocked first by a receipt when the store is short;
* Avocado Block A gets one ERPNext Budget on its cost centre for the current fiscal year.
Skipped with a printed note when the company has no fiscal year or the needed accounts. Every invented
figure is in DEMO.
"""

import frappe
from frappe.utils import add_days, flt, getdate, today

from upande_production.production.logic import blockcost
from upande_production.production.logic import harvest as H
from upande_production.production.logic.settings import get_company

DEMO = {
	"group": "Production Blocks",
	"store": "Stores",
	"item_group": "Raw Material",
	# item code -> (stock uom, rate per uom, qty per ha of the block, days before today)
	"items": {"Demo NPK Fertiliser": ("Kg", 95, 250, 40), "Demo Fungicide": ("Litre", 1800, 6, 12)},
	"crops": ["Avocado"],
	"budget": {"unit": "Avocado Block A", "amount": 3500000, "account": None},
}
REMARK = "demo-blocks:"


def _company():
	return get_company() or frappe.db.get_value("Company", {}, "name")


def seed_warehouses(company) -> dict:
	group = H.new_warehouse(DEMO["group"], company, is_group=1)
	made = linked = 0
	for u in frappe.get_all("Production Unit", filters={"is_group": 0, "cost_center": ("is", "set")},
			fields=["name", "cost_center", "farm", "warehouse"]):
		if u.warehouse == u.cost_center:
			continue
		if not frappe.db.exists("Warehouse", u.cost_center):
			abbr = frappe.db.get_value("Company", company, "abbr")
			name = u.cost_center[: -len(f" - {abbr}")] if u.cost_center.endswith(f" - {abbr}") else u.cost_center
			made += bool(H.new_warehouse(name, company, parent=group, farm=u.farm))
		frappe.db.set_value("Production Unit", u.name, "warehouse", u.cost_center, update_modified=False)
		linked += 1
	return {"warehouses_created": made, "blocks_linked": linked}


def _store(company):
	abbr = frappe.db.get_value("Company", company, "abbr")
	name = f"{DEMO['store']} - {abbr}"
	return name if frappe.db.exists("Warehouse", name) else H.new_warehouse(DEMO["store"], company)


def _item(code, uom, rate):
	if not frappe.db.exists("Item", code):
		if not frappe.db.exists("UOM", uom):
			frappe.get_doc({"doctype": "UOM", "uom_name": uom}).insert(ignore_permissions=True)
		group = DEMO["item_group"] if frappe.db.exists("Item Group", DEMO["item_group"]) else "All Item Groups"
		frappe.get_doc({"doctype": "Item", "item_code": code, "item_name": code, "item_group": group, "stock_uom": uom,
			"is_stock_item": 1, "valuation_rate": rate, "standard_rate": rate}).insert(ignore_permissions=True)
	return code


def _entry(kind, remark, company, posting_date, items, purpose=None):
	"""A submitted Stock Entry keyed on its remarks (None when it exists)."""
	if frappe.db.exists("Stock Entry", {"remarks": remark, "docstatus": 1}):
		return None
	se = frappe.get_doc({"doctype": "Stock Entry", "stock_entry_type": kind, "purpose": kind, "company": company,
		"posting_date": posting_date, "set_posting_time": 1, "remarks": remark, "items": items})
	se.flags.ignore_permissions = True
	se.insert()
	se.submit()
	return se.name


def seed_issues(company) -> int:
	store = _store(company)
	n = 0
	for crop in DEMO["crops"]:
		for u in frappe.get_all("Production Unit", filters={"crop": crop, "is_group": 0, "cost_center": ("is", "set")},
				fields=["name", "cost_center", "area_ha"], order_by="name"):
			for code, (uom, rate, per_ha, days) in DEMO["items"].items():
				_item(code, uom, rate)
				qty = round(per_ha * flt(u.area_ha or 1), 2)
				d = add_days(today(), -days)
				have = flt(frappe.db.get_value("Bin", {"item_code": code, "warehouse": store}, "actual_qty"))
				if not frappe.db.exists("Stock Entry", {"remarks": f"{REMARK}issue:{u.name}:{code}", "docstatus": 1}) and have < qty:
					_entry("Material Receipt", f"{REMARK}receipt:{u.name}:{code}", company, add_days(d, -5),
						[{"item_code": code, "qty": qty, "uom": uom, "t_warehouse": store, "basic_rate": rate}])
				if _entry("Material Issue", f"{REMARK}issue:{u.name}:{code}", company, d,
						[{"item_code": code, "qty": qty, "uom": uom, "s_warehouse": store, "cost_center": u.cost_center}]):
					n += 1
	return n


def seed_budget(company) -> str:
	cfg = DEMO["budget"]
	cc = frappe.db.get_value("Production Unit", cfg["unit"], "cost_center")
	fy = blockcost.fiscal_year_range()
	if not cc or not fy:
		print("blocks seed: no cost centre or fiscal year; budget skipped")
		return "skipped"
	account = cfg["account"] or frappe.db.get_value("Company", company, "default_expense_account")
	if not account or not frappe.db.exists("Account", account):
		print("blocks seed: no expense account for the budget; skipped")
		return "skipped"
	if frappe.db.exists("Budget", {"cost_center": cc, "budget_against": "Cost Center", "docstatus": ("<", 2),
			"from_fiscal_year": fy[0]}):
		return "exists"
	b = frappe.get_doc({"doctype": "Budget", "budget_against": "Cost Center", "company": company, "cost_center": cc,
		"account": account, "budget_amount": cfg["amount"], "from_fiscal_year": fy[0], "to_fiscal_year": fy[0],
		"applicable_on_booking_actual_expenses": 1, "action_if_annual_budget_exceeded": "Warn",
		"action_if_accumulated_monthly_budget_exceeded": "Warn"})
	b.flags.ignore_permissions = True
	b.insert()
	b.submit()
	return b.name


def run(commit=True):
	company = _company()
	out = seed_warehouses(company)
	out["issues_created"] = seed_issues(company)
	out["budget"] = seed_budget(company)
	if commit:
		frappe.db.commit()
	print(f"blocks seed: {out}")
	return out
