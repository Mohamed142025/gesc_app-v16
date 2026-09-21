app_name = "gesc_app"
app_title = "Gesc App"
app_publisher = "mohamed sayed"
app_description = "custom app for gesc"
app_email = "mohameddbs53@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "gesc_app",
# 		"logo": "/assets/gesc_app/logo.png",
# 		"title": "Gesc App",
# 		"route": "/gesc_app",
# 		"has_permission": "gesc_app.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# Bump asset query versions when changing raw static files.
app_include_css = "/assets/gesc_app/css/notification_counter.css?v=5"
app_include_js = [
	"/assets/gesc_app/js/sales_order_analysis.js",
	"/assets/gesc_app/js/item_description.js?v=1",
	"/assets/gesc_app/js/notification_counter.js?v=4",
]

# include js, css files in header of web template
# web_include_css = "/assets/gesc_app/css/gesc_app.css"
# web_include_js = "/assets/gesc_app/js/gesc_app.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "gesc_app/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Quotation": "public/js/quotation.js",
	"Project": "public/js/project.js",
	"Task": "public/js/task.js",
	"Project Item": "public/js/project_item.js",
	"Sales Order": "public/js/sales_order.js",
	"Delivery Note": "public/js/delivery_note.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "gesc_app/public/icons.svg"

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
# 	"methods": "gesc_app.utils.jinja_methods",
# 	"filters": "gesc_app.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "gesc_app.install.before_install"
# after_install = "gesc_app.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "gesc_app.uninstall.before_uninstall"
# after_uninstall = "gesc_app.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "gesc_app.utils.before_app_install"
# after_app_install = "gesc_app.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "gesc_app.utils.before_app_uninstall"
# after_app_uninstall = "gesc_app.utils.after_app_uninstall"

after_migrate = "gesc_app.item_description_setup.setup_item_description_fields"

# Build
# ------------------
# To hook into the build process

# after_build = "gesc_app.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "gesc_app.notifications.get_notification_config"

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
	"*": {
		"on_update": "gesc_app.gesc_app.notification_handler.notify_assignees_on_update",
		"validate": "gesc_app.item_description_setup.validate_item_descriptions",
	},
	"Task": {
		"on_update": "gesc_app.gesc_app.task_utils.sync_responsible_assignment",
	},
	"Project": {
		"on_update": "gesc_app.gesc_app.project_utils.generate_tasks_from_template",
	},
	"Sales Order": {
		"validate": "gesc_app.gesc_app.sales_order_utils.validate_contract_relation",
		"on_submit": "gesc_app.gesc_app.sales_order_utils.refresh_linked_project_items",
		"on_cancel": "gesc_app.gesc_app.sales_order_utils.refresh_linked_project_items",
	},
	"Delivery Note": {
		"before_validate": "gesc_app.gesc_app.delivery_note_utils.calculate_line_values",
		"on_submit": "gesc_app.gesc_app.delivery_note_utils.sync_project_item_progress_on_submit",
		"on_cancel": "gesc_app.gesc_app.delivery_note_utils.sync_project_item_progress_on_cancel",
	},
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"gesc_app.tasks.all"
# 	],
# 	"daily": [
# 		"gesc_app.tasks.daily"
# 	],
# 	"hourly": [
# 		"gesc_app.tasks.hourly"
# 	],
# 	"weekly": [
# 		"gesc_app.tasks.weekly"
# 	],
# 	"monthly": [
# 		"gesc_app.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "gesc_app.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "gesc_app.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "gesc_app.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
override_doctype_dashboards = {
	"Quotation": "gesc_app.gesc_app.quotation_dashboard.get_data"
}

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["gesc_app.utils.before_request"]
# after_request = ["gesc_app.utils.after_request"]

# Job Events
# ----------
# before_job = ["gesc_app.utils.before_job"]
# after_job = ["gesc_app.utils.after_job"]

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
# 	"gesc_app.auth.validate"
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

# Fixtures
# --------
# Custom Fields added to standard doctypes (e.g. Quotation) by this app.

fixtures = [
	{
		"doctype": "Custom Field",
		"filters": [
			[
				"dt",
				"in",
				[
					"Quotation",
					"Task",
					"Project",
					"Sales Order",
					"Sales Order Item",
					"Delivery Note Item",
				],
			],
			["fieldname", "like", "custom_%"],
		],
	},
	{
		"doctype": "Workspace",
		"filters": [["name", "=", "Projects"]],
	},
	{
		"doctype": "Workspace Sidebar",
		"filters": [["name", "=", "Projects"]],
	},
	{
		"doctype": "Dashboard",
		"filters": [["name", "=", "Project"]],
	},
	{
		"doctype": "Translation",
		"filters": [["source_text", "like", "%Delivery Note%"]],
	},
]

