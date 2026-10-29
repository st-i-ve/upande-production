import frappe
from frappe.tests import IntegrationTestCase

DOCTYPES = [
	"Production Crop", "Production Unit", "Field Activity", "Production Protocol",
	"Production Protocol Step", "Production Crop Cycle", "Production Work Plan", "Production Plan Task",
	"Value Adder Work", "Production Harvest", "Yield Sample", "Production Forecast",
	"Production Forecast Week", "Buyer Commitment",
]
ROLES = ["Production Manager", "Production Supervisor", "Production Viewer"]


class TestDoctypes(IntegrationTestCase):
	def test_all_doctypes_exist(self):
		for name in DOCTYPES:
			self.assertTrue(frappe.db.table_exists(name), name)
			self.assertEqual(frappe.get_meta(name).is_submittable, 1 if name == "Value Adder Work" else 0, name)
		self.assertTrue(frappe.get_meta("Production Settings").issingle)
		self.assertTrue(frappe.get_meta("Production Unit").is_tree)
		for role in ROLES:
			self.assertTrue(frappe.db.exists("Role", role), role)


NEW_DOCTYPES = [
	"Production Protocol Capital Activity", "Production Protocol Key Activity",
	"Production Protocol Cultural Activity", "Block Establishment Cost", "Block Establishment Cost Split",
	"Block Opening Balance", "Dry Matter Test", "Dry Matter Sample", "Production Capital Account",
]
NEW_FIELDS = {
	"Field Activity": ["activity_type", "color"],
	"Production Crop": ["dry_matter_testing", "dry_matter_on", "dry_matter_target_pct"],
	"Production Variety": [
		"lifespan_years", "harvest_pattern", "harvest_interval_weeks", "is_flowering",
		"weeks_to_first_flowering", "weeks_flowering_to_harvest", "weeks_to_reflower_after_harvest",
		"weeks_to_first_harvest", "harvest_window_weeks", "plants_per_m2", "dry_matter_target_pct",
		"weeks_to_maturity", "flowering_pattern", "flowering_seasons", "flowering_interval_weeks",
	],
	"Production Variety Flowering Season": ["season_name", "start_month", "weeks_flowering_to_harvest", "crop_share_pct"],
	"Production Crop Cycle": ["flowering_season", "juvenile"],
	"Production Protocol": [
		"capital_activities", "key_activities", "cultural_activities", "lifespan_years", "harvest_pattern",
		"harvest_interval_weeks", "is_flowering", "weeks_to_first_flowering", "weeks_flowering_to_harvest",
		"weeks_to_reflower_after_harvest", "plants_per_m2",
	],
	"Production Protocol Key Activity": ["operation", "week", "repeats", "planned_qty", "description"],
	"Production Protocol Cultural Activity": [
		"operation", "schedule", "interval_weeks", "establishment_period_weeks", "pre_harvest_interval_days",
		"planned_qty", "description",
	],
	"Production Protocol Capital Activity": ["operation", "description", "budget_per_ha"],
	"Production Crop Cycle": [
		"cycle_no", "expected_flowering_date", "actual_flowering_date", "actual_harvest_start",
		"actual_harvest_end", "protocol_flags", "flag_count", "due_for_uprooting", "proposed_next_cycle",
	],
	"Production Settings": ["cycle_flag_tolerance_weeks", "capital_accounts"],
	"Block Establishment Cost": [
		"crop", "farm", "posting_date", "operation", "amount", "supplier", "paid_to", "reference", "note",
		"blocks", "split_method", "total_area_ha",
	],
	"Block Establishment Cost Split": ["unit", "area_ha", "share_pct", "amount"],
	"Block Opening Balance": [
		"unit", "crop", "as_of_date", "setup_cost", "running_costs_to_date", "value_recovered_to_date",
		"planted_on", "note",
	],
	"Dry Matter Test": [
		"unit", "cycle", "crop", "variety", "test_date", "tested_on", "samples", "avg_pct", "target_pct",
		"ready", "tested_by",
	],
	"Dry Matter Sample": ["sample_no", "dry_matter_pct"],
	"Production Capital Account": ["account"],
}


class TestNewSchema(IntegrationTestCase):
	def test_new_schema_fields(self):
		for dt in NEW_DOCTYPES:
			self.assertTrue(frappe.db.exists("DocType", dt), dt)
		for dt, fields in NEW_FIELDS.items():
			meta = frappe.get_meta(dt)
			for f in fields:
				self.assertTrue(meta.has_field(f), f"{dt}.{f}")
		self.assertEqual(frappe.get_meta("Block Establishment Cost").is_submittable, 1)
		self.assertTrue(frappe.get_meta("Production Protocol").get_field("steps").hidden)
