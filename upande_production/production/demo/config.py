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
	"items": ["Hass Avocado", "Fuerte Avocado", "Potatoes", "Cabbage", "Onion", "Passion Fruit", "Maize", "Tilapia", "Honey"],
	# crop -> [(operation, work_uom, default_rate, category, is_harvest)]
	"operations": {
		"Avocado": [
			("Pruning", "Tree", 25, "Pruning", 0), ("Fertiliser Application", "Tree", 10, "Fertilising", 0),
			("Irrigation Check", "Hectare", 150, "Irrigation", 0), ("Weeding", "Hectare", 1200, "Weeding", 0),
			("Fruit Count", "Tree", 5, "Other", 0), ("Harvest Picking", "Crate", 30, "Harvesting", 1),
			("Spraying", "Hectare", 600, "Spraying", 0),
		],
		"Fruits & Vegetables": [
			("Land Preparation", "Hectare", 2500, "Other", 0), ("Planting", "Bed", 60, "Other", 0),
			("Weeding", "Bed", 40, "Weeding", 0), ("Top Dressing", "Bed", 35, "Fertilising", 0),
			("Spraying", "Hectare", 600, "Spraying", 0), ("Harvest", "Crate", 25, "Harvesting", 1),
			("Passion Pruning", "Plant", 8, "Pruning", 0),
		],
		"Aquaculture": [
			("Stocking", "Fingerlings (x1000)", 300, "Other", 0), ("Feeding", "Kg", 5, "Feeding", 0),
			("Water Quality Check", "Pond", 100, "Other", 0), ("Harvest", "Kg", 10, "Harvesting", 1),
		],
		"Apiary": [
			("Hive Inspection", "Hive", 20, "Other", 0), ("Treatment", "Hive", 30, "Other", 0),
			("Honey Harvest", "Kg", 40, "Harvesting", 1),
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
		"Maize": ("Fruits & Vegetables", "Maize", [
			("Land Preparation", -7, 0, 1, 6), ("Planting", 0, 0, 1, 120), ("Weeding", 21, 21, 2, 120),
			("Top Dressing", 35, 0, 1, 120), ("Spraying", 21, 14, 4, 6), ("Harvest", 110, 0, 1, 400)]),
		"Pond Cycle": ("Aquaculture", "Tilapia", [
			("Stocking", 0, 0, 1, 20), ("Feeding", 0, 7, 26, 80), ("Water Quality Check", 0, 7, 26, 1),
			("Harvest", 180, 0, 1, 500)]),
		"Hive Season": ("Apiary", "Honey", [
			("Hive Inspection", 0, 14, 12, 400), ("Treatment", 30, 0, 1, 400), ("Honey Harvest", 90, 0, 1, 200)]),
	},
	# The real avocado blocks come from the survey (Phase 1 / Phase 2); these are the farm's figures about them.
	# `active` blocks are bearing and picking: cycles, plans, work, harvests, dry matter and counts.
	# The rest are young plantings with trees and a master record but no crop yet.
	"avocado": {
		"active": ["PH1-B1", "PH1-B2", "PH1-B3", "PH1-B4", "PH1-B5", "PH1-B6", "PH1-B7", "PH1-B8", "PH1-B9",
			"PH2-B1", "PH2-B2", "PH2-B3"],
		"sampled": ["PH1-B1", "PH1-B2", "PH1-B3", "PH1-B4", "PH1-B5", "PH1-B6", "PH2-B1", "PH2-B2"],  # dry matter and counts
		"worked": ["PH1-B1", "PH1-B2", "PH1-B3", "PH1-B4", "PH1-B5", "PH2-B1"],  # unplanned work history
		"fuerte": ["PH1-B3", "PH1-B7", "PH2-B2"],
		# (blocks, planting year); anything else is default_planted
		"planted": [
			(("PH1-B1", "PH1-B2", "PH1-B3", "PH1-B4", "PH1-B5", "PH1-B6", "PH1-B7", "PH1-B8", "PH1-B9"), 2018),
			(("PH2-B1", "PH2-B2", "PH2-B3"), 2020),
			(("PH1-B10", "PH1-B11", "PH1-B12", "PH1-B13", "PH1-B14", "PH1-B15", "PH1-B16"), 2023),
		],
		"default_planted": 2024,
		"bearing_from_planted": 2021,
		"trees_per_ha": 160, "live_share": 0.97, "bearing_share": 0.95, "sick_share": 0.03, "infill_share": 0.02,
		"start_ago": 85,  # cycle start days before today
		"kg_per_tree": {"year_2024": (58, 72), "late_2025": (36, 46), "early_2026": (52, 62)},
		"early_estimate_share": 0.89, "typed_forecast_share": 1.0,
		"dm_start": (18.4, 20.2), "dm_gain": (0.55, 0.72),  # blocks start below the floor; some cross 24
		"fruit_count": {"per_tree": (320, 375), "weight_g": (205, 225), "drop_pct": 8},
	},
	# Pivot blocks: crop cycle per block -> (protocol, active cycle start_ago, status, previous crop item, variety).
	# The first eight blocks keep the cycles they had before the survey replaced the demo outlines.
	"fv_cycles": {
		"P1-B1": ("Potato", 45, "Active", "Cabbage", "Shangi"), "P1-B2": ("Potato", 62, "Active", "Onion", "Dutch Robjin"),
		"P1-B3": ("Cabbage", 50, "Active", "Potatoes", "Gloria F1"), "P1-B4": ("Cabbage", 95, "Harvesting", "Onion", "Copenhagen Market"),
		"P2-B1": ("Onion", 40, "Active", "Potatoes", "Red Creole"), "P2-B2": ("Onion", 128, "Harvesting", "Cabbage", "Red Creole"),
		"P2-B3": ("Potato", 105, "Harvesting", "Cabbage", "Markies"), "P2-B4": ("Potato", 30, "Active", "Onion", "Shangi"),
		"P1-B5": ("Onion", 55, "Active", "Potatoes", "Red Creole"), "P1-B6": ("Onion", 112, "Harvesting", "Cabbage", "Red Pinoy F1"),
		"P1-B7": ("Potato", 98, "Harvesting", "Onion", "Markies"), "P1-B8": ("Potato", 20, "Active", "Cabbage", "Shangi"),
		"P1-B9": ("Maize", 70, "Active", "Potatoes", "H513"), "P1-B10": ("Cabbage", 34, "Active", "Onion", "Gloria F1"),
		"P1-B11": ("Passion", 190, "Harvesting", None, "Purple"), "P1-B12": ("Onion", 75, "Active", "Cabbage", "Red Creole"),
		"P2-B5": ("Cabbage", 72, "Active", "Potatoes", "Copenhagen Market"), "P2-B6": ("Cabbage", 82, "Harvesting", "Onion", "Gloria F1"),
		"P2-B7": ("Potato", 66, "Active", "Cabbage", "Dutch Robjin"), "P2-B8": ("Passion", 200, "Harvesting", None, "Sweet Yellow"),
		"P2-B9": ("Maize", 105, "Harvesting", "Onion", "H513"), "P2-B10": ("Potato", 48, "Active", "Cabbage", "Shangi"),
		"P2-B11": ("Passion", 185, "Harvesting", None, "Purple"), "P2-B12": ("Onion", 100, "Active", "Potatoes", "Red Pinoy F1"),
	},
	"ponds": [("Pond 1", 60, "Active"), ("Pond 2", 45, "Active"), ("Pond 3", 176, "Harvesting"), ("Pond 4", 90, "Active")],
	"hives": [("Hive Group North", 40, "Active"), ("Hive Group South", 55, "Harvesting")],
	"prices": {"Hass Avocado": 120, "Fuerte Avocado": 120, "Potatoes": 45, "Cabbage": 30, "Onion": 70,
		"Passion Fruit": 110, "Maize": 40, "Tilapia": 400, "Honey": 900},
	# weekly harvest per unit by item: kg per ha (or per tree / per unit)
	"weekly_yield": {"Potatoes": 1500, "Cabbage": 1800, "Onion": 1200, "Passion Fruit": 380, "Maize": 900,
		"Tilapia": 320, "Honey": 70, "Hass Avocado": 1.3, "Fuerte Avocado": 1.1},
	# item -> (basis, sample_size, sampled_yield per sample)
	"samples": {"Potatoes": ("Square Metres", 10, 38), "Cabbage": ("Square Metres", 10, 29),
		"Onion": ("Square Metres", 10, 31), "Passion Fruit": ("Plants", 20, 62), "Maize": ("Square Metres", 10, 12),
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
	# Activity lists per crop: (name, activity_type, category, work_uom). Existing operations keep their
	# colour and only get the type; new ones are made with a distinct colour from `activity_palette`.
	"capital_avocado": [
		("Bush clearing", "Capital", "Other", "Hectare"), ("Single ripping", "Capital", "Other", "Hectare"),
		("Cross ripping", "Capital", "Other", "Hectare"), ("Disc harrowing", "Capital", "Other", "Hectare"),
		("Marking of ridges", "Capital", "Other", "Hectare"), ("Ridge-line ripping", "Capital", "Other", "Hectare"),
		("Ridging", "Capital", "Other", "Hectare"), ("Fertiliser application (basal)", "Capital", "Fertilising", "Hectare"),
		("Irrigation system installation", "Capital", "Irrigation", "Hectare"),
		("Windbreak planting", "Capital", "Other", "Hectare"), ("Planting material", "Capital", "Other", "Hectare"),
	],
	"field_activities": [
		("Planting", "Planting", "Other", "Tree"), ("Uprooting / clearing", "Uprooting", "Other", "Hectare"),
		("Mulching", "Cultural", "Other", "Hectare"), ("Seedling support (staking)", "Key activity", "Other", "Plant"),
		("Irrigating", "Cultural", "Irrigation", "Hectare"), ("Fertigating", "Cultural", "Fertilising", "Hectare"),
		("Fertiliser Application", "Cultural", "Fertilising", "Hectare"), ("Drenching", "Cultural", "Other", "Hectare"),
		("Weeding", "Cultural", "Weeding", "Hectare"), ("Soil management", "Cultural", "Other", "Hectare"),
		("Pest management", "Cultural", "Other", "Hectare"), ("Dry matter testing", "Key activity", "Other", "Hectare"),
		("Gap filling", "Key activity", "Other", "Plant"), ("Bending", "Key activity", "Other", "Tree"),
		("Earthing Up", "Key activity", "Other", "Bed"), ("Fruit Count", "Key activity", "Other", "Tree"),
	],
	"capital_other": {
		"Apiary": [("Hive stands", "Capital", "Other", "Hive"), ("Hives", "Capital", "Other", "Hive"),
			("Apiary fencing", "Capital", "Other", "Hive")],
		"Aquaculture": [("Pond excavation", "Capital", "Other", "Pond"), ("Pond liner", "Capital", "Other", "Pond"),
			("Inlet and outlet works", "Capital", "Other", "Pond"), ("Aerator installation", "Capital", "Other", "Pond")],
	},
	# crops that get the field activities and the capital list above (apiary / aquaculture only get theirs)
	"activity_crops": ["Avocado", "Fruits & Vegetables"],
	"activity_palette": ["#2F7D5B", "#C2410C", "#2563EB", "#9333EA", "#CA8A04", "#0E7490", "#BE185D", "#65A30D",
		"#B45309", "#4F46E5", "#0F766E", "#DC2626", "#7C3AED", "#059669", "#D97706", "#0284C7", "#DB2777", "#84CC16",
		"#92400E", "#1D4ED8", "#A21CAF", "#15803D", "#EA580C", "#0891B2", "#E11D48", "#4D7C0F", "#6D28D9", "#B91C1C",
		"#155E75", "#854D0E", "#475569", "#BE123C"],
}
