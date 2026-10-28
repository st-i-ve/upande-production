"""Every invented figure for the Mutara demo lives in DEMO."""

DEMO = {
	"company": "Mutara",
	"farm": {"name": "Mutara", "abbr": "MUT", "area": 120.0},
	"seed": 2026,
	"customers": ["Twiga Foods", "Kakuzi Export"],
	"crops": [
		{"name": "Avocado", "key": "avocado", "accent": "#3f7d3a", "icon": "avocado", "parent": "", "unit": "Block", "sub": "Row", "uom": "Kg", "sort": 1, "cycle_type": "Season"},
		{"name": "Fruits & Vegetables", "key": "fruits-vegetables", "accent": "#c0662b", "icon": "vegetables", "parent": "Pivot", "unit": "Block", "sub": "Bed", "uom": "Kg", "sort": 2, "cycle_type": "Planting"},
		{"name": "Aquaculture", "key": "aquaculture", "accent": "#2b6f9e", "icon": "fish", "parent": "", "unit": "Pond", "sub": "", "uom": "Kg", "sort": 3, "cycle_type": "Pond Cycle", "cycles": 0},
		{"name": "Apiary", "key": "apiary", "accent": "#c99a1b", "icon": "hive", "parent": "", "unit": "Hive Group", "sub": "Hive", "uom": "Kg", "sort": 4, "cycle_type": "Hive Season", "cycles": 0},
	],
	"uoms": ["Kg", "Hectare", "Tree", "Crate", "Bed", "Plant", "Pond", "Hive", "Fingerlings (x1000)"],
	"items": ["Hass Avocado", "Fuerte Avocado", "Potatoes", "Cabbage", "Onion", "Passion Fruit", "Tilapia", "Honey"],
	# crop -> [(operation, work_uom, default_rate, category, is_harvest)]
	"operations": {
		"Avocado": [
			("Pruning", "Tree", 25, "Field Care", 0), ("Fertiliser Application", "Tree", 10, "Nutrition", 0),
			("Irrigation Check", "Hectare", 150, "Irrigation", 0), ("Weeding", "Hectare", 1200, "Field Care", 0),
			("Fruit Count", "Tree", 5, "Field Care", 0), ("Harvest Picking", "Crate", 30, "Harvest", 1),
			("Spraying", "Hectare", 600, "Spray", 0),
		],
		"Fruits & Vegetables": [
			("Land Preparation", "Hectare", 2500, "Planting", 0), ("Planting", "Bed", 60, "Planting", 0),
			("Weeding", "Bed", 40, "Field Care", 0), ("Top Dressing", "Bed", 35, "Nutrition", 0),
			("Spraying", "Hectare", 600, "Spray", 0), ("Harvest", "Crate", 25, "Harvest", 1),
			("Passion Pruning", "Plant", 8, "Field Care", 0),
		],
		"Aquaculture": [
			("Stocking", "Fingerlings (x1000)", 300, "Husbandry", 0), ("Feeding", "Kg", 5, "Husbandry", 0),
			("Water Quality Check", "Pond", 100, "Husbandry", 0), ("Harvest", "Kg", 10, "Harvest", 1),
		],
		"Apiary": [
			("Hive Inspection", "Hive", 20, "Husbandry", 0), ("Treatment", "Hive", 30, "Husbandry", 0),
			("Honey Harvest", "Kg", 40, "Harvest", 1),
		],
	},
	# protocol -> (crop, item, [(operation, day_offset, repeat_every, repeat_count, planned_qty)])
	"protocols": {
		"Avocado Season": ("Avocado", "Hass Avocado", [
			("Pruning", 0, 0, 1, 200), ("Fertiliser Application", 14, 30, 4, 300),
			("Irrigation Check", 0, 7, 26, 6), ("Fruit Count", 60, 0, 1, 100)]),
		"Potato": ("Fruits & Vegetables", "Potatoes", [
			("Land Preparation", -7, 0, 1, 6), ("Planting", 0, 0, 1, 120), ("Weeding", 21, 21, 2, 120),
			("Top Dressing", 30, 0, 1, 120), ("Spraying", 14, 10, 6, 6), ("Harvest", 100, 0, 1, 400)]),
		"Cabbage": ("Fruits & Vegetables", "Cabbage", [
			("Planting", 0, 0, 1, 120), ("Weeding", 20, 0, 1, 120), ("Top Dressing", 28, 0, 1, 120),
			("Spraying", 10, 12, 5, 6), ("Harvest", 85, 0, 1, 450)]),
		"Onion": ("Fruits & Vegetables", "Onion", [
			("Planting", 0, 0, 1, 120), ("Weeding", 25, 20, 3, 120), ("Spraying", 15, 14, 6, 6),
			("Harvest", 120, 0, 1, 350)]),
		"Passion": ("Fruits & Vegetables", "Passion Fruit", [
			("Passion Pruning", 0, 90, 4, 600), ("Spraying", 0, 30, 12, 6), ("Harvest", 0, 14, 26, 150)]),
		"Pond Cycle": ("Aquaculture", "Tilapia", [
			("Stocking", 0, 0, 1, 20), ("Feeding", 0, 7, 26, 80), ("Water Quality Check", 0, 7, 26, 1),
			("Harvest", 180, 0, 1, 500)]),
		"Hive Season": ("Apiary", "Honey", [
			("Hive Inspection", 0, 14, 12, 400), ("Treatment", 30, 0, 1, 400), ("Honey Harvest", 90, 0, 1, 200)]),
	},
	"avocado_blocks": [
		{"name": "Avocado Block A", "code": "A", "area": 6.5, "trees": 1040, "variety": "Hass", "item": "Hass Avocado", "start_ago": 85},
		{"name": "Avocado Block B", "code": "B", "area": 5.2, "trees": 832, "variety": "Fuerte, Hass", "item": "Fuerte Avocado", "start_ago": 100},
	],
	"pivots": [("Pivot 1", 24), ("Pivot 2", 22), ("Pivot 3", 21), ("Pivot 4", 20)],
	# block -> (protocol, active cycle start_ago, status, previous crop item)
	"fv_cycles": {
		"P1-B1": ("Potato", 45, "Active", "Cabbage"), "P1-B2": ("Potato", 62, "Active", "Onion"),
		"P1-B3": ("Cabbage", 50, "Active", "Potatoes"), "P1-B4": ("Cabbage", 95, "Harvesting", "Onion"),
		"P2-B1": ("Onion", 40, "Active", "Potatoes"), "P2-B2": ("Onion", 128, "Harvesting", "Cabbage"),
		"P2-B3": ("Potato", 105, "Harvesting", "Cabbage"), "P2-B4": ("Potato", 30, "Active", "Onion"),
		"P3-B1": ("Cabbage", 66, "Active", "Onion"), "P3-B2": ("Cabbage", 28, "Active", "Potatoes"),
		"P3-B3": ("Onion", 70, "Active", "Potatoes"), "P3-B4": ("Onion", 110, "Active", "Cabbage"),
		"P4-B1": ("Passion", 190, "Harvesting", None), "P4-B2": ("Passion", 200, "Harvesting", None),
		"P4-B3": ("Passion", 185, "Harvesting", None), "P4-B4": ("Passion", 195, "Harvesting", None),
	},
	"ponds": [("Pond 1", 60, "Active"), ("Pond 2", 45, "Active"), ("Pond 3", 176, "Harvesting"), ("Pond 4", 90, "Active")],
	"hives": [("Hive Group North", 40, "Active"), ("Hive Group South", 55, "Harvesting")],
	"prices": {"Hass Avocado": 120, "Fuerte Avocado": 120, "Potatoes": 45, "Cabbage": 30, "Onion": 70,
		"Passion Fruit": 110, "Tilapia": 400, "Honey": 900},
	# weekly harvest per unit by item: kg per ha (or per tree / per unit)
	"weekly_yield": {"Potatoes": 1500, "Cabbage": 1800, "Onion": 1200, "Passion Fruit": 380,
		"Tilapia": 320, "Honey": 70, "Hass Avocado": 1.3, "Fuerte Avocado": 1.1},
	# item -> (basis, sample_size, sampled_yield per sample)
	"samples": {"Potatoes": ("Square Metres", 10, 38), "Cabbage": ("Square Metres", 10, 29),
		"Onion": ("Square Metres", 10, 31), "Passion Fruit": ("Plants", 20, 62),
		"Hass Avocado": ("Trees", 10, 580), "Fuerte Avocado": ("Trees", 10, 520)},
	"status_mix": {"done": 0.80, "late": 0.88, "partial": 0.94},  # cumulative
	"journal_accounts": ["Cost of Goods Sold - MUT", "Miscellaneous Expenses - MUT", "Utility Expenses - MUT", "Office Maintenance Expenses - MUT"],
	"cash_account": "Cash - MUT",
	"value_adders": [
		("Wanjiru", "Kamau", "Female"), ("Otieno", "Odhiambo", "Male"), ("Akinyi", "Onyango", "Female"),
		("Kipchoge", "Rotich", "Male"), ("Njeri", "Mwangi", "Female"), ("Mutua", "Musyoka", "Male"),
		("Chebet", "Koech", "Female"), ("Kariuki", "Gitau", "Male"), ("Atieno", "Ouma", "Female"),
		("Wafula", "Simiyu", "Male"), ("Nyambura", "Njoroge", "Female"), ("Kiprono", "Kirui", "Male"),
		("Muthoni", "Wangari", "Female"), ("Omondi", "Owino", "Male"), ("Naliaka", "Barasa", "Female"),
		("Kimani", "Ndung'u", "Male"), ("Wambui", "Maina", "Female"), ("Juma", "Hassan", "Male"),
		("Achieng", "Awino", "Female"), ("Kosgei", "Langat", "Male"), ("Mwende", "Kioko", "Female"),
		("Barasa", "Wekesa", "Male"), ("Wangui", "Karanja", "Female"), ("Ochieng", "Okoth", "Male"),
	],
	# users who "key in" work (submitted_by on the demo Value Adder Work) and what managers sent back
	"keying_users": ["moses@upande.com", "rose@upande.com", "mumo@upande.com"],
	"approval_mix": {"stale_pending": 4, "fresh_pending": 5, "sent_back": 2, "stale_days": (3, 4),
		"lead_pending": 4, "lead_stale": 1},
	"lead_crop": "Avocado",
	# Avocado leads the demo, so it gets a realistic trailing history: plans for the last `weeks` weeks
	# plus unplanned (ad hoc) work by a crew drawn from the value adders, on Blocks A and B.
	# operation -> (probability per block per week, picks per week when it happens, qty range per person, step)
	"avocado_history": {
		"weeks": 8, "crew": 12, "crew_per_job": (2, 3), "hours": (3.0, 8.0), "last_day_ago": 6,
		"jobs": {
			"Pruning": (0.5, 1, (25, 70), 1), "Irrigation Check": (1.0, 1, (1, 3), 0.5),
			"Fertiliser Application": (0.5, 1, (40, 120), 1), "Spraying": (0.7, 1, (1, 3), 0.5),
			"Weeding": (0.6, 1, (0.5, 2), 0.5), "Harvest Picking": (1.0, 2, (8, 18), 1),
		},
	},
	"sent_back_notes": [
		"Quantity looks too high for the hours worked. Please recheck the count and resubmit.",
		"Wrong people listed for this block. Fix the names, then resubmit.",
	],
	"supervisors": [("Grace", "Wairimu", "Female"), ("Peter", "Kiplagat", "Male"), ("Mary", "Anyango", "Female")],
}
