"""Run every demo seed in dependency order.

bench --site mutara.local execute upande_production.production.demo.all.run
"""

from upande_production.production.demo import (
	apiary_seed, aquaculture_seed, avocado_seed, fv_seed, geo, harvest_seed, seed,
)


def run():
	# seed first (units, people, plans, generic harvests); the crop seeds then own their crops'
	# harvests and logs; geo last so every unit has geometry.
	for mod in (seed, avocado_seed, harvest_seed, apiary_seed, aquaculture_seed, fv_seed, geo):
		mod.run()
		print(f"[demo] {mod.__name__} done")
