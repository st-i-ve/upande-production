app_name = "upande_production"
app_title = "Upande Production"
app_publisher = "Upande"
app_description = "Multi-crop production planning, field tracking, block costing and forecasting"
app_email = "teddy@upande.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
add_to_apps_screen = [
	{
		"name": "upande_production",
		"logo": "/assets/upande_production/images/production_logo.svg",
		"title": "Production",
		"route": "/app/production",
	}
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/upande_production/css/upande_production.css"
# Same-tab navigation for the /production_app sidebar and launcher links (Frappe
# forces target="_blank" on URL sidebar items, which production_desk.js overrides).
app_include_js = [
	"/assets/upande_production/js/production_desk.js",
	"/assets/upande_production/js/upande_tile_logo.js",
	# Summer flowers (ported from upande_summer_flowers): planting calendar and the form walkthrough
	"/assets/upande_production/js/sf_calendar.js",
	"/assets/upande_production/js/sf_walkthrough.js",
]

# include js, css files in header of web template
# web_include_css = "/assets/upande_production/css/upande_production.css"
# web_include_js = "/assets/upande_production/js/upande_production.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "upande_production/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Crop Protocol": [
		"public/js/crop_protocol_walkthrough.js",
		"public/js/crop_protocol_ways.js",
		"public/js/crop_protocol_flush_shares.js",
	],
	"Crop Cycle": "public/js/crop_cycle_planting.js",
}
doctype_list_js = {"Block": "public/js/block_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "upande_production/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "upande_production.utils.jinja_methods",
# 	"filters": "upande_production.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "upande_production.install.before_install"
# after_install = "upande_production.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "upande_production.uninstall.before_uninstall"
# after_uninstall = "upande_production.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "upande_production.utils.before_app_install"
# after_app_install = "upande_production.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "upande_production.utils.before_app_uninstall"
# after_app_uninstall = "upande_production.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "upande_production.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "upande_production.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Avocado Fruit Count": {
		"after_insert": "upande_production.api.avocadoapi.notify_new_fruit_count",
	},
	# Field execution (ported from upande_agriculture). The Stock Entry forecast refresh
	# is hooked by upande_crop_material_planning, which owns forecasts.
	"Crop Cycle": {
		"on_update": "upande_production.controllers.crop_cycle_on_update",
		"on_trash": "upande_production.controllers.crop_cycle_on_trash",
	},
	# Summer flowers (ported from upande_summer_flowers). The Crop Cycle class override below runs the lifecycle.
	"Crop Protocol": {
		"before_validate": "upande_production.summer_flowers.crop_protocol.before_validate",
		"validate": "upande_production.summer_flowers.crop_protocol.validate",
		"on_update": "upande_production.summer_flowers.crop_protocol.on_update",
	},
	"Block": {
		"validate": "upande_production.summer_flowers.block.validate_block",
		"autoname": "upande_production.summer_flowers.bed_naming.block_autoname",
	},
	"Bed": {
		"validate": "upande_production.summer_flowers.bed.validate_bed",
		"autoname": "upande_production.summer_flowers.bed_naming.bed_autoname",
		"before_validate": "upande_production.summer_flowers.bed_naming.bed_farm_from_block",
	},
	"Greenhouse": {
		"on_update": [
			"upande_production.crop_production.doctype.greenhouse.greenhouse.sync_logs_to_crop_cycles",
			"upande_production.crop_production.doctype.greenhouse.greenhouse.sync_bed_master",
		],
	},
	"Production Plan Form": {
		"before_save": "upande_production.controllers.production_plan_form_before_save",
		"on_update": "upande_production.controllers.production_plan_form_on_update",
		"on_trash": "upande_production.controllers.production_plan_form_on_trash",
	},
}

before_migrate = "upande_production.summer_flowers.customization_check.before_migrate"
after_migrate = [
	"upande_production.summer_flowers.protocol_merge.after_migrate",
	"upande_production.summer_flowers.tours.sync_form_tours",
]
# The summer flower lifecycle rides on Crop Cycle (gated on custom_is_summer_flower_cycle) and Bed.
override_doctype_class = {
	"Bed": "upande_production.summer_flowers.bed.SummerFlowerBed",
	"Crop Cycle": "upande_production.summer_flowers.crop_cycle.SummerFlowerCropCycle",
}

# Fixtures
# --------
# The Expo push-token field lives on the core User doctype (one token per
# line, mirroring upande_harvest/support_api.py's convention), but it exists
# only for this app's notifications, so this app owns and exports it.
fixtures = [
	{
		"doctype": "Custom Field",
		"filters": [["name", "in", ["User-custom_expo_push_tokens", "Stock Entry-production_harvest_batch", "Stock Entry Detail-production_harvest_batch", "Stock Entry Detail-production_unit", "Stock Entry Detail-production_crates", "Item-production_avg_kg_per_crate"]]],
	},
	{
		"doctype": "Role",
		"filters": [["name", "in", ["Production Manager", "Production Supervisor", "Production Viewer", "Agriculture Manager", "Agriculture User"]]],
	},
	{"doctype": "Workspace", "filters": [["module", "=", "Crop Production"]]},
	# Summer flowers approvals (ported from upande_summer_flowers)
	{"doctype": "Workflow State", "filters": [["name", "in", ["Draft", "Pending Approval", "Approved", "Rejected", "Active", "Superseded", "Planted", "Uprooted", "Cancelled"]]]},
	{"doctype": "Workflow Action Master", "filters": [["name", "in", ["Submit for Approval", "Approve", "Reject", "Reopen", "Revise", "Mark Planted", "Mark Uprooted", "Cancel Planting"]]]},
	{"doctype": "Workflow", "filters": [["name", "in", ["Planting Calendar Approval", "Crop Protocol Approval"]]]},
	# Per-farm scan-location routing createGradingStockEntry depends on for Standard Roses
	# (Spray Roses are graded in place, no mapping needed). Master data, not code, but without
	# a fixture it silently does not exist on a fresh deploy.
	{"doctype": "Scan Location Mapping", "filters": [["name", "in", ["Simotwo-MAP", "Chepsito-MAP", "Kapkolia-MAP", "Karen-MAP", "Torongo-MAP", "Kaptumbo-MAP"]]]},
	# The desk workspace's launcher (one section of app links per crop) and the
	# desk-grid icon that opens that workspace.
	{"doctype": "Custom HTML Block", "filters": [["name", "in", ["Production Navigation", "Roses Production Navigation", "Agriculture Navigation", "Crop Cycle Dashboard"]]]},
	{"doctype": "Desktop Icon", "filters": [["name", "in", ["Production"]]]},
]

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"upande_production.production.logic.stages.refresh_all_open",
		"upande_production.production.logic.cycle_chain.refresh_flags_all",
		"upande_production.scheduled.release_stale_buckets",
		"upande_production.scheduled.rollup_plan_tasks",
	],
}

override_doctype_dashboards = {
	"Stock Entry": "upande_production.stock_entry_connections.get_dashboard_data",
}

# The roses mobile app and desk JS still call the old upande_agriculture paths; they resolve here.
# Budget/projection/week-summary paths are mapped by upande_crop_material_planning and the
# seedling-request/propagation/trial paths by upande_propagation.
override_whitelisted_methods = {
	"upande_agriculture.api.mark_cycle_harvestable": "upande_production.api.crop_production.mark_cycle_harvestable",
	"upande_agriculture.api.submit_production_plan": "upande_production.api.crop_production.submit_production_plan",
	"upande_agriculture.api.list_active_cycles": "upande_production.api.crop_production.list_active_cycles",
	"upande_agriculture.plan.week_plan": "upande_production.plan.week_plan",
	"upande_agriculture.plan.house_tasks": "upande_production.plan.house_tasks",
	"upande_agriculture.plan.live_operations": "upande_production.plan.live_operations",
	"upande_agriculture.plan.house_bed_load": "upande_production.plan.house_bed_load",
	"upande_agriculture.plan.set_task_status": "upande_production.plan.set_task_status",
	"upande_agriculture.plan.update_task": "upande_production.plan.update_task",
	"upande_agriculture.plan.delete_task": "upande_production.plan.delete_task",
	"upande_agriculture.plan.task_options": "upande_production.plan.task_options",
	"upande_agriculture.plan.add_task": "upande_production.plan.add_task",
	"upande_agriculture.farm_map.map_payload": "upande_production.farm_map.map_payload",
	"upande_agriculture.farm_map.bed_geometry": "upande_production.farm_map.bed_geometry",
	"upande_agriculture.farm_map.weather_now": "upande_production.farm_map.weather_now",
}
MOBILE_ENDPOINTS = (
	"createGradingStockEntry", "createHarvestStockEntry", "fetchBucketContents", "getBucketStatus",
	"amendHarvestEntry", "getGreenhouseData", "productionCreateCropCycle", "productionGetGreenhouseSpec",
	"productionGetPlanForm", "productionHarvestReport", "productionGreenhouseVarietyBreakdown",
	"productionListCropCycles", "productionListFarms", "productionListGreenhouseSpecs",
	"productionListGreenhouses", "productionListPlanForms", "productionListRejectionReasons",
	"productionListVarieties", "productionRecordReplant", "productionRecordUproot", "productionSavePlanForm",
	"productionSetGreenhouseGrower", "productionUpdatePlanTask", "reportDeviceTelemetry", "submitFieldRejects",
)
override_whitelisted_methods.update({
	f"upande_agriculture.mobile.api.{name}": f"upande_production.mobile.crop_production.{name}"
	for name in MOBILE_ENDPOINTS
})
del MOBILE_ENDPOINTS

# scheduler_events = {
# 	"all": [
# 		"upande_production.tasks.all"
# 	],
# 	"daily": [
# 		"upande_production.tasks.daily"
# 	],
# 	"hourly": [
# 		"upande_production.tasks.hourly"
# 	],
# 	"weekly": [
# 		"upande_production.tasks.weekly"
# 	],
# 	"monthly": [
# 		"upande_production.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "upande_production.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "upande_production.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "upande_production.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "upande_production.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["upande_production.utils.before_request"]
# after_request = ["upande_production.utils.after_request"]

# Job Events
# ----------
# before_job = ["upande_production.utils.before_job"]
# after_job = ["upande_production.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"upande_production.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

# Old upande_summer_flowers paths keep working: every whitelisted method it had that production now owns.
SUMMER_FLOWERS_OVERRIDES = {
	"upande_summer_flowers.mobile.api.delivery_schedule": "upande_production.mobile.summer_flowers_api.delivery_schedule",
	"upande_summer_flowers.mobile.api.draft_plant_receipt": "upande_production.mobile.summer_flowers_api.draft_plant_receipt",
	"upande_summer_flowers.mobile.api.farm_plan": "upande_production.mobile.summer_flowers_api.farm_plan",
	"upande_summer_flowers.mobile.api.motherstock_batches": "upande_production.mobile.summer_flowers_api.motherstock_batches",
	"upande_summer_flowers.mobile.api.motherstock_line": "upande_production.mobile.summer_flowers_api.motherstock_line",
	"upande_summer_flowers.mobile.api.motherstock_plan": "upande_production.mobile.summer_flowers_api.motherstock_plan",
	"upande_summer_flowers.mobile.api.open_plant_orders": "upande_production.mobile.summer_flowers_api.open_plant_orders",
	"upande_summer_flowers.mobile.api.production_plans": "upande_production.mobile.summer_flowers_api.production_plans",
	"upande_summer_flowers.mobile.api.propagation_detail": "upande_production.mobile.summer_flowers_api.propagation_detail",
	"upande_summer_flowers.mobile.api.propagation_plans": "upande_production.mobile.summer_flowers_api.propagation_plans",
	"upande_summer_flowers.mobile.api.propagation_schedule": "upande_production.mobile.summer_flowers_api.propagation_schedule",
	"upande_summer_flowers.mobile.api.propagation_units": "upande_production.mobile.summer_flowers_api.propagation_units",
	"upande_summer_flowers.mobile.api.propagation_varieties": "upande_production.mobile.summer_flowers_api.propagation_varieties",
	"upande_summer_flowers.mobile.api.protocol_detail": "upande_production.mobile.summer_flowers_api.protocol_detail",
	"upande_summer_flowers.mobile.api.record_propagation_actual": "upande_production.mobile.summer_flowers_api.record_propagation_actual",
	"upande_summer_flowers.mobile.api.save_protocol": "upande_production.mobile.summer_flowers_api.save_protocol",
	"upande_summer_flowers.mobile.api.submit_protocol_for_approval": "upande_production.mobile.summer_flowers_api.submit_protocol_for_approval",
	"upande_summer_flowers.mobile.api.tc_suppliers": "upande_production.mobile.summer_flowers_api.tc_suppliers",
	"upande_summer_flowers.summer_flowers.api.block_coverage": "upande_production.summer_flowers.api.block_coverage",
	"upande_summer_flowers.summer_flowers.api.filters": "upande_production.summer_flowers.api.filters",
	"upande_summer_flowers.summer_flowers.api.monthly_series": "upande_production.summer_flowers.api.monthly_series",
	"upande_summer_flowers.summer_flowers.api.on_ground": "upande_production.summer_flowers.api.on_ground",
	"upande_summer_flowers.summer_flowers.api.overview": "upande_production.summer_flowers.api.overview",
	"upande_summer_flowers.summer_flowers.api.protocol_comparison": "upande_production.summer_flowers.api.protocol_comparison",
	"upande_summer_flowers.summer_flowers.bed.backfill_bed_area": "upande_production.summer_flowers.bed.backfill_bed_area",
	"upande_summer_flowers.summer_flowers.block.beds_for_range": "upande_production.summer_flowers.block.beds_for_range",
	"upande_summer_flowers.summer_flowers.block.create_from_beds": "upande_production.summer_flowers.block.create_from_beds",
	"upande_summer_flowers.summer_flowers.block.link_beds_to_block": "upande_production.summer_flowers.block.link_beds_to_block",
	"upande_summer_flowers.summer_flowers.block.revise_area": "upande_production.summer_flowers.block.revise_area",
	"upande_summer_flowers.summer_flowers.crop_cycle_api.bed_work": "upande_production.summer_flowers.crop_cycle_api.bed_work",
	"upande_summer_flowers.summer_flowers.crop_cycle_api.biological_assets": "upande_production.summer_flowers.crop_cycle_api.biological_assets",
	"upande_summer_flowers.summer_flowers.crop_cycle_api.cycle": "upande_production.summer_flowers.crop_cycle_api.cycle",
	"upande_summer_flowers.summer_flowers.crop_cycle_api.cycles": "upande_production.summer_flowers.crop_cycle_api.cycles",
	"upande_summer_flowers.summer_flowers.crop_cycle_api.scope": "upande_production.summer_flowers.crop_cycle_api.scope",
	"upande_summer_flowers.summer_flowers.crop_cycle_ops.bed_work_action": "upande_production.summer_flowers.crop_cycle_ops.bed_work_action",
	"upande_summer_flowers.summer_flowers.crop_cycle_ops.create_bed_work": "upande_production.summer_flowers.crop_cycle_ops.create_bed_work",
	"upande_summer_flowers.summer_flowers.crop_cycle_ops.log_bed_progress": "upande_production.summer_flowers.crop_cycle_ops.log_bed_progress",
	"upande_summer_flowers.summer_flowers.crop_cycle_ops.set_biological_asset": "upande_production.summer_flowers.crop_cycle_ops.set_biological_asset",
	"upande_summer_flowers.summer_flowers.crop_cycle_ops.set_cycle_scope": "upande_production.summer_flowers.crop_cycle_ops.set_cycle_scope",
	"upande_summer_flowers.summer_flowers.crop_protocol.active_versions": "upande_production.summer_flowers.crop_protocol.active_versions",
	"upande_summer_flowers.summer_flowers.crop_protocol.submit_for_approval": "upande_production.summer_flowers.crop_protocol.submit_for_approval",
	"upande_summer_flowers.summer_flowers.crop_routes.classify": "upande_production.summer_flowers.crop_routes.classify",
	"upande_summer_flowers.summer_flowers.crop_routes.provision": "upande_production.summer_flowers.crop_routes.provision",
	"upande_summer_flowers.summer_flowers.crop_routes.spread_season": "upande_production.summer_flowers.crop_routes.spread_season",
	"upande_summer_flowers.summer_flowers.delivery_confirmation.confirm": "upande_production.summer_flowers.delivery_confirmation.confirm",
	"upande_summer_flowers.summer_flowers.delivery_confirmation.confirm_and_raise": "upande_production.summer_flowers.delivery_confirmation.confirm_and_raise",
	"upande_summer_flowers.summer_flowers.delivery_confirmation.save_requirements": "upande_production.summer_flowers.delivery_confirmation.save_requirements",
	"upande_summer_flowers.summer_flowers.delivery_confirmation.save_schedule": "upande_production.summer_flowers.delivery_confirmation.save_schedule",
	"upande_summer_flowers.summer_flowers.delivery_confirmation.schedule_for": "upande_production.summer_flowers.delivery_confirmation.schedule_for",
	"upande_summer_flowers.summer_flowers.doctype.crop_protocol_version.crop_protocol_version.current_version": "upande_production.crop_production.doctype.crop_protocol_version.crop_protocol_version.current_version",
	"upande_summer_flowers.summer_flowers.doctype.crop_protocol_version.crop_protocol_version.resolve_version": "upande_production.crop_production.doctype.crop_protocol_version.crop_protocol_version.resolve_version",
	"upande_summer_flowers.summer_flowers.doctype.planting_calendar.planting_calendar.calendar_events": "upande_production.crop_production.doctype.planting_calendar.planting_calendar.calendar_events",
	"upande_summer_flowers.summer_flowers.operations_api.act": "upande_production.summer_flowers.operations_api.act",
	"upande_summer_flowers.summer_flowers.operations_api.add_demand_weeks": "upande_production.summer_flowers.operations_api.add_demand_weeks",
	"upande_summer_flowers.summer_flowers.operations_api.agree_motherstock_line": "upande_production.summer_flowers.operations_api.agree_motherstock_line",
	"upande_summer_flowers.summer_flowers.operations_api.assign_all_blocks": "upande_production.summer_flowers.operations_api.assign_all_blocks",
	"upande_summer_flowers.summer_flowers.operations_api.block_options": "upande_production.summer_flowers.operations_api.block_options",
	"upande_summer_flowers.summer_flowers.operations_api.budget_detail": "upande_production.summer_flowers.operations_api.budget_detail",
	"upande_summer_flowers.summer_flowers.operations_api.chain_status": "upande_production.summer_flowers.operations_api.chain_status",
	"upande_summer_flowers.summer_flowers.operations_api.create_production_plan": "upande_production.summer_flowers.operations_api.create_production_plan",
	"upande_summer_flowers.summer_flowers.operations_api.create_propagation_plan": "upande_production.summer_flowers.operations_api.create_propagation_plan",
	"upande_summer_flowers.summer_flowers.operations_api.crop_cycle_detail": "upande_production.summer_flowers.operations_api.crop_cycle_detail",
	"upande_summer_flowers.summer_flowers.operations_api.crop_cycles": "upande_production.summer_flowers.operations_api.crop_cycles",
	"upande_summer_flowers.summer_flowers.operations_api.end_cycle_on": "upande_production.summer_flowers.operations_api.end_cycle_on",
	"upande_summer_flowers.summer_flowers.operations_api.motherstock_commitment": "upande_production.summer_flowers.operations_api.motherstock_commitment",
	"upande_summer_flowers.summer_flowers.operations_api.plan_action": "upande_production.summer_flowers.operations_api.plan_action",
	"upande_summer_flowers.summer_flowers.operations_api.plan_preview": "upande_production.summer_flowers.operations_api.plan_preview",
	"upande_summer_flowers.summer_flowers.operations_api.plan_transitions": "upande_production.summer_flowers.operations_api.plan_transitions",
	"upande_summer_flowers.summer_flowers.operations_api.process_overview": "upande_production.summer_flowers.operations_api.process_overview",
	"upande_summer_flowers.summer_flowers.operations_api.propose_horizon": "upande_production.summer_flowers.operations_api.propose_horizon",
	"upande_summer_flowers.summer_flowers.operations_api.record_cuttings_on": "upande_production.summer_flowers.operations_api.record_cuttings_on",
	"upande_summer_flowers.summer_flowers.operations_api.record_harvest": "upande_production.summer_flowers.operations_api.record_harvest",
	"upande_summer_flowers.summer_flowers.operations_api.reset_targets": "upande_production.summer_flowers.operations_api.reset_targets",
	"upande_summer_flowers.summer_flowers.operations_api.review_queue": "upande_production.summer_flowers.operations_api.review_queue",
	"upande_summer_flowers.summer_flowers.operations_api.set_actual_pinch": "upande_production.summer_flowers.operations_api.set_actual_pinch",
	"upande_summer_flowers.summer_flowers.operations_api.set_block": "upande_production.summer_flowers.operations_api.set_block",
	"upande_summer_flowers.summer_flowers.operations_api.set_weekly_target": "upande_production.summer_flowers.operations_api.set_weekly_target",
	"upande_summer_flowers.summer_flowers.protocol_split.move": "upande_production.summer_flowers.protocol_split.move",
	"upande_summer_flowers.summer_flowers.protocol_split.move_back": "upande_production.summer_flowers.protocol_split.move_back",
	"upande_summer_flowers.summer_flowers.root_line.agree_material_plan": "upande_production.summer_flowers.root_line.agree_material_plan",
	"upande_summer_flowers.summer_flowers.root_line.arrivals_for": "upande_production.summer_flowers.root_line.arrivals_for",
	"upande_summer_flowers.summer_flowers.root_line.how_it_is_raised": "upande_production.summer_flowers.root_line.how_it_is_raised",
	"upande_summer_flowers.summer_flowers.root_line.plan_for": "upande_production.summer_flowers.root_line.plan_for",
	"upande_summer_flowers.summer_flowers.root_line.propagation_overview": "upande_production.summer_flowers.root_line.propagation_overview",
	"upande_summer_flowers.summer_flowers.root_line.propagation_units": "upande_production.summer_flowers.root_line.propagation_units",
	"upande_summer_flowers.summer_flowers.root_line.raising_choices": "upande_production.summer_flowers.root_line.raising_choices",
	"upande_summer_flowers.summer_flowers.root_line.selling_choices": "upande_production.summer_flowers.root_line.selling_choices",
	"upande_summer_flowers.summer_flowers.root_line.set_propagation_unit": "upande_production.summer_flowers.root_line.set_propagation_unit",
	"upande_summer_flowers.summer_flowers.root_line.set_raising": "upande_production.summer_flowers.root_line.set_raising",
	"upande_summer_flowers.summer_flowers.root_line.set_selling": "upande_production.summer_flowers.root_line.set_selling",
	"upande_summer_flowers.summer_flowers.root_line.ways_for": "upande_production.summer_flowers.root_line.ways_for",
	"upande_summer_flowers.summer_flowers.route_methods.apply_catalogue": "upande_production.summer_flowers.route_methods.apply_catalogue",
	"upande_summer_flowers.summer_flowers.route_ways.route_info": "upande_production.summer_flowers.route_ways.route_info",
	"upande_summer_flowers.summer_flowers.route_ways.route_stages": "upande_production.summer_flowers.route_ways.route_stages",
}
override_whitelisted_methods.update(SUMMER_FLOWERS_OVERRIDES)
