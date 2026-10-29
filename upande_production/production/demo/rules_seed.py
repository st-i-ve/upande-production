"""Idempotent demo activity rules (Production Activity Rule) for Mutara.

bench --site mutara.local execute upande_production.production.demo.rules_seed.run

Every invented figure is in DEMO. A rule with a `product` is made once per variety of that product (so
potato rules do not touch cabbage); a rule without one is crop-wide. Run after the varieties seed.
"""

import frappe

BEFORE = "Not within days before harvest"
AFTER = "Not within days after operation"
NOT_IN = "Not in stage"
ONLY_IN = "Only in stage"

DEMO = {
	# extra operations the rules need (crop, name, uom, rate, category)
	"operations": [("Fruits & Vegetables", "Earthing Up", "Bed", 30, "Other")],
	"rules": [
		# pre-harvest intervals for spraying
		{"crop": "Avocado", "category": "Spraying", "type": BEFORE, "days": 21, "enforcement": "Block",
		 "reason": "Spray residues: stop spraying 21 days before the first picking."},
		{"crop": "Fruits & Vegetables", "product": "Potatoes", "category": "Spraying", "type": BEFORE, "days": 14,
		 "enforcement": "Block", "reason": "Spray residues: stop spraying potatoes 14 days before harvest."},
		{"crop": "Fruits & Vegetables", "product": "Cabbage", "category": "Spraying", "type": BEFORE, "days": 14,
		 "enforcement": "Block", "reason": "Spray residues: stop spraying cabbage 14 days before harvest."},
		{"crop": "Fruits & Vegetables", "product": "Onion", "category": "Spraying", "type": BEFORE, "days": 14,
		 "enforcement": "Block", "reason": "Spray residues: stop spraying onions 14 days before harvest."},
		{"crop": "Fruits & Vegetables", "product": "Passion Fruit", "category": "Spraying", "type": BEFORE, "days": 7,
		 "enforcement": "Block", "reason": "Spray residues: stop spraying passion fruit 7 days before picking."},
		{"crop": "Fruits & Vegetables", "product": "Maize", "category": "Spraying", "type": BEFORE, "days": 14,
		 "enforcement": "Block", "reason": "Spray residues: stop spraying maize 14 days before harvest."},
		# no weeding while the potato tubers are forming and bulking
		{"crop": "Fruits & Vegetables", "product": "Potatoes", "category": "Weeding", "type": NOT_IN,
		 "stage": "Tuber initiation", "enforcement": "Warn",
		 "reason": "Weeding now can damage the young tubers. Give a reason if it cannot wait."},
		{"crop": "Fruits & Vegetables", "product": "Potatoes", "category": "Weeding", "type": NOT_IN,
		 "stage": "Bulking", "enforcement": "Warn",
		 "reason": "Weeding now can damage the tubers. Give a reason if it cannot wait."},
		# no picking soon after a spray
		{"crop": "Avocado", "category": "Harvesting", "type": AFTER, "days": 7, "other_category": "Spraying",
		 "enforcement": "Block", "reason": "Wait out the 7-day safe period after spraying before picking."},
		{"crop": "Fruits & Vegetables", "category": "Harvesting", "type": AFTER, "days": 7,
		 "other_category": "Spraying", "enforcement": "Block",
		 "reason": "Wait out the 7-day safe period after spraying before harvesting."},
		# earthing up only while the potato plants are still vegetative
		{"crop": "Fruits & Vegetables", "product": "Potatoes", "operation": "Earthing Up", "type": ONLY_IN,
		 "stage": "Vegetative", "enforcement": "Warn",
		 "reason": "Earthing up is done while the plants are still growing leaves. Give a reason if you must do it later."},
		# fish are not fed the day before they are harvested
		{"crop": "Aquaculture", "category": "Feeding", "type": BEFORE, "days": 1, "enforcement": "Warn",
		 "reason": "Do not feed the day before harvest: it fouls the water and the fish."},
	],
}


def _ensure_operations():
	for crop, name, uom, rate, cat in DEMO["operations"]:
		if not frappe.db.exists("Production Crop", crop):
			continue
		if not frappe.db.exists("Production Operation", {"crop": crop, "operation_name": name}):
			frappe.get_doc({"doctype": "Production Operation", "crop": crop, "operation_name": name,
				"category": cat, "work_uom": uom, "default_rate": rate, "is_harvest": 0}).insert(ignore_permissions=True)


def _varieties(crop, product):
	if not frappe.db.exists("DocType", "Production Variety"):
		return []
	return frappe.get_all("Production Variety", filters={"crop": crop, "product": product}, pluck="name") \
		or frappe.get_all("Production Variety", filters={"crop": crop, "variety_name": ("like", f"{product}%")}, pluck="name")


def _operation(crop, name):
	return frappe.db.get_value("Production Operation", {"crop": crop, "operation_name": name})


def _make(spec, variety):
	vals = {
		"crop": spec["crop"], "variety": variety, "stage": spec.get("stage"),
		"operation": _operation(spec["crop"], spec["operation"]) if spec.get("operation") else None,
		"operation_category": spec.get("category"), "rule_type": spec["type"], "days": spec.get("days"),
		"other_category": spec.get("other_category"), "enforcement": spec["enforcement"],
	}
	if spec.get("operation") and not vals["operation"]:
		return 0
	filters = {k: (v if v else ("is", "not set")) for k, v in vals.items()
		if k not in ("enforcement", "days")}
	existing = frappe.db.get_value("Production Activity Rule", filters)
	if existing:
		frappe.db.set_value("Production Activity Rule", existing,
			{"days": spec.get("days") or 0, "enforcement": spec["enforcement"], "reason": spec["reason"], "enabled": 1})
		return 0
	frappe.get_doc({"doctype": "Production Activity Rule", **vals, "reason": spec["reason"], "enabled": 1}) \
		.insert(ignore_permissions=True)
	return 1


def run():
	_ensure_operations()
	made = 0
	for spec in DEMO["rules"]:
		if not frappe.db.exists("Production Crop", spec["crop"]):
			continue
		if spec.get("product"):
			varieties = _varieties(spec["crop"], spec["product"])
			if not varieties:
				print(f"[rules] no varieties of {spec['product']} yet: skipped")
			for v in varieties:
				made += _make(spec, v)
		else:
			made += _make(spec, None)
	frappe.db.commit()
	print(f"[rules] {made} rule(s) created, {len(DEMO['rules'])} defined")
	return made
