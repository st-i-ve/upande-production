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
		"logo": "/assets/upande_production/images/upande_mark.svg",
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
app_include_js = "/assets/upande_production/js/production_desk.js"

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
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
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
}

# Fixtures
# --------
# The Expo push-token field lives on the core User doctype (one token per
# line, mirroring upande_harvest/support_api.py's convention), but it exists
# only for this app's notifications, so this app owns and exports it.
fixtures = [
	{
		"doctype": "Custom Field",
		"filters": [["name", "in", ["User-custom_expo_push_tokens"]]],
	},
	{
		"doctype": "Role",
		"filters": [["name", "in", ["Production Manager", "Production Supervisor", "Production Viewer"]]],
	},
	# The desk workspace's launcher (one section of app links per crop) and the
	# desk-grid icon that opens that workspace.
	{"doctype": "Custom HTML Block", "filters": [["name", "in", ["Production Navigation"]]]},
	{"doctype": "Desktop Icon", "filters": [["name", "in", ["Production"]]]},
]

# Scheduled Tasks
# ---------------

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

