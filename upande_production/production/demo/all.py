"""Run every demo seed in dependency order.

bench --site mutara.local execute upande_production.production.demo.all.run
"""

import frappe

from upande_production.production.demo import (
	apiary_seed, aquaculture_seed, avocado_seed, blocks_seed, establishment_seed, fv_seed, harvest_seed, rules_seed, seed, stores_seed, varieties_seed,
)


def run():
	# seed first (units, people, plans, generic harvests); the crop seeds then own their crops'
	# harvests and logs. Unit outlines come from the surveyed map import, never from a seed.
	# History is keyed in before any activity rule exists, and must not be refused by one on a re-run.
	frappe.flags.skip_activity_rules = True
	try:
		for mod in (seed, varieties_seed, avocado_seed, harvest_seed, apiary_seed, aquaculture_seed, fv_seed):
			mod.run()
			print(f"[demo] {mod.__name__} done")
	finally:
		frappe.flags.skip_activity_rules = False
	# the pond seed re-creates its stockings; they take their strain from the variety seed's map
	varieties_seed._fix_ponds()
	# activity rules last: they need the varieties (and their stages) of the crop seeds
	rules_seed.run()
	print(f"[demo] {rules_seed.__name__} done")
	# establishment costs, opening balances, protocol buffers, dry matter tests, cycle flags
	establishment_seed.run()
	print(f"[demo] {establishment_seed.__name__} done")
	# block warehouses, fertiliser / chemical issues per avocado block, an ERP budget
	blocks_seed.run()
	print(f"[demo] {blocks_seed.__name__} done")
	# chemical and fertiliser stores, copied products and opening stock
	stores_seed.run()
	print(f"[demo] {stores_seed.__name__} done")
