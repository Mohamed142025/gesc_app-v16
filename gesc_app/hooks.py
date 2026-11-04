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
app_include_js = [
	"/assets/gesc_app/js/sales_order_analysis.js",
	"/assets/gesc_app/js/item_description.js?v=1",
	"/assets/gesc_app/js/private_comments.js?v=2",
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
	# "الغرض" with the sample request (sample_request).
	"Material Request": "public/js/material_request_purpose.js",
	"Quotation": ["public/js/quotation.js", "public/js/quotation_approval.js", "public/js/quotation_addendum.js"],
	"Project": ["public/js/project.js", "public/js/project_controls.js"],
	"Task": ["public/js/task.js", "public/js/task_execution.js"],
	"Project Item": "public/js/project_item.js",
	"Sales Order": ["public/js/sales_order.js", "public/js/sales_order_project.js"],
	"Delivery Note": "public/js/delivery_note.js",
	# The project on every item, and an installation's project stock (stock_entry_project).
	"Stock Entry": "public/js/stock_entry_project.js",
	# Who an announcement goes to (hr_announcement_audience).
	"HR Announcement": "public/js/hr_announcement_audience.js",
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

after_migrate = [
	"gesc_app.item_description_setup.setup_item_description_fields",
	"gesc_app.gesc_app.task_execution_setup.setup_task_execution",
	"gesc_app.gesc_app.project_controls_setup.setup_project_controls",
	"gesc_app.gesc_app.quotation_approval_setup.setup_quotation_approval",
	"gesc_app.gesc_app.quotation_addendum.setup_quotation_addendum",
	"gesc_app.gesc_app.private_comments.setup_private_comments",
	"gesc_app.gesc_app.assignment_edit.setup",
	"gesc_app.gesc_app.sample_request.setup",
	"gesc_app.gesc_app.project_warehouse.setup",
	# The project's name next to every project field (project_title).
	"gesc_app.gesc_app.project_title.setup",
	# Quotation fields read by the print formats (quotation_print).
	"gesc_app.gesc_app.quotation_print.setup",
	# Sales Invoice fields read by the progress statement print format (sales_invoice_print).
	"gesc_app.gesc_app.sales_invoice_print.setup",
	# The project on a Stock Entry and the installation entry type (stock_entry_project).
	"gesc_app.gesc_app.stock_entry_project.setup",
	# The project's team table (project_team).
	"gesc_app.gesc_app.project_team.setup",
	# Employee data: sensitive fields for HR, check-ins created by employees (access_guard).
	"gesc_app.gesc_app.access_guard.setup",
	# Items followed without supply/installation weights (sales_order_progress).
	"gesc_app.gesc_app.sales_order_progress.setup",
	# HR Announcement for selected departments, designations, grades or employees.
	"gesc_app.gesc_app.hr_announcement_audience.setup",
]

# Employee data each employee sees: their own, or their team's (access_guard).
permission_query_conditions = {
	"Salary Slip": "gesc_app.gesc_app.access_guard.salary_slip_condition",
	"Salary Structure Assignment": "gesc_app.gesc_app.access_guard.salary_structure_assignment_condition",
	"Attendance": "gesc_app.gesc_app.access_guard.attendance_condition",
	"Employee Checkin": "gesc_app.gesc_app.access_guard.employee_checkin_condition",
	"PWA Notification": "gesc_app.gesc_app.access_guard.notification_condition",
}
has_permission = {
	"Salary Slip": "gesc_app.gesc_app.access_guard.has_employee_permission",
	"Salary Structure Assignment": "gesc_app.gesc_app.access_guard.has_employee_permission",
	"Attendance": "gesc_app.gesc_app.access_guard.has_employee_permission",
	"Employee Checkin": "gesc_app.gesc_app.access_guard.has_employee_permission",
	"PWA Notification": "gesc_app.gesc_app.access_guard.has_notification_permission",
}

# Private comments: per-user timeline items and the enabled document types at login.
additional_timeline_content = {"*": ["gesc_app.gesc_app.private_comments.timeline"]}
boot_session = "gesc_app.gesc_app.private_comments.boot_session"

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
		"validate": "gesc_app.item_description_setup.validate_item_descriptions",
	},
	"Task": {
		"validate": "gesc_app.gesc_app.task_execution.validate_task",
		"on_update": [
			"gesc_app.gesc_app.task_utils.sync_responsible_assignment",
			"gesc_app.gesc_app.task_execution.on_task_update",
		],
	},
	"Warehouse": {
		"validate": "gesc_app.gesc_app.task_execution.validate_warehouse",
	},
	"Task Type": {
		"validate": "gesc_app.gesc_app.task_execution.validate_task_type",
	},
	"ToDo": {
		"on_update": [
			"gesc_app.gesc_app.material_submittal.acknowledge",
			# An assignee may edit what they are assigned (System Settings, assignment_edit).
			"gesc_app.gesc_app.assignment_edit.sync_edit_share",
		],
		"on_trash": "gesc_app.gesc_app.assignment_edit.revoke_on_delete",
	},
	"System Settings": {
		"on_update": "gesc_app.gesc_app.assignment_edit.apply_setting",
	},
	# Sample requests: a Material Issue for a customer (sample_request).
	"Material Request": {
		"before_validate": "gesc_app.gesc_app.sample_request.sync_purpose",
	},
	"Stock Entry": {
		"before_validate": [
			"gesc_app.gesc_app.sample_request.apply_sample",
			# The project on every item; an installation needs one (stock_entry_project).
			"gesc_app.gesc_app.stock_entry_project.validate",
		],
	},
	"Quotation": {
		"autoname": "gesc_app.gesc_app.quotation_addendum.autoname",
		"validate": [
			"gesc_app.gesc_app.project_controls.set_required_advance",
			"gesc_app.gesc_app.quotation_approval.validate",
			"gesc_app.gesc_app.quotation_addendum.validate",
			"gesc_app.gesc_app.task_execution.validate_quotation_task",
		],
		"on_update": [
			"gesc_app.gesc_app.task_execution.link_quotation_to_task",
			"gesc_app.gesc_app.quotation_approval.on_update",
		],
		"before_submit": "gesc_app.gesc_app.quotation_approval.before_submit",
		"on_submit": [
			"gesc_app.gesc_app.quotation_addendum.on_submit",
			"gesc_app.gesc_app.task_execution.complete_inspection",
		],
		"before_print": "gesc_app.gesc_app.quotation_approval.before_print",
	},
	"Communication": {
		"before_insert": "gesc_app.gesc_app.quotation_approval.check_email",
	},
	"Selling Settings": {
		"validate": "gesc_app.gesc_app.quotation_approval.validate_settings",
	},
	"Project": {
		"validate": "gesc_app.gesc_app.project_controls.validate_project",
		# Every new project gets its own warehouse (project_warehouse).
		"after_insert": "gesc_app.gesc_app.project_warehouse.create_project_warehouse",
		"on_update": [
			"gesc_app.gesc_app.project_utils.generate_tasks_from_template",
			"gesc_app.gesc_app.project_controls.log_project_exception",
			"gesc_app.gesc_app.project_utils.create_project_items",
			"gesc_app.gesc_app.project_title.update_project_title",
			# The team's users are assigned the project (project_team).
			"gesc_app.gesc_app.project_team.sync_assignments",
		],
	},
	"Sales Order": {
		"before_insert": "gesc_app.gesc_app.quotation_addendum.link_sales_order",
		"autoname": "gesc_app.gesc_app.sales_order_utils.set_addendum_name",
		"validate": [
			"gesc_app.gesc_app.sales_order_utils.validate_contract_relation",
			"gesc_app.gesc_app.project_controls.set_required_advance",
			# Supply % + installation % = 100 on every item (sales_order_progress).
			"gesc_app.gesc_app.sales_order_progress.validate_weights",
		],
		"before_submit": "gesc_app.gesc_app.project_controls.validate_sales_order_advance",
		"before_update_after_submit": "gesc_app.gesc_app.project_controls.check_advance_change_after_submit",
		"on_submit": "gesc_app.gesc_app.sales_order_utils.refresh_linked_project_items",
		"on_cancel": "gesc_app.gesc_app.sales_order_utils.refresh_linked_project_items",
	},
	"Delivery Note": {
		"before_validate": "gesc_app.gesc_app.delivery_note_utils.calculate_line_values",
		"on_submit": "gesc_app.gesc_app.delivery_note_utils.sync_project_item_progress_on_submit",
		"on_cancel": "gesc_app.gesc_app.delivery_note_utils.sync_project_item_progress_on_cancel",
	},
	# Guards on employee data, whatever the app or the API sends (access_guard).
	"Employee Checkin": {"before_insert": "gesc_app.gesc_app.access_guard.guard_checkin"},
	"Employee Advance": {
		"validate": "gesc_app.gesc_app.access_guard.strip_draft_schedule",
		"before_submit": "gesc_app.gesc_app.access_guard.strip_draft_schedule",
		"before_update_after_submit": "gesc_app.gesc_app.access_guard.guard_schedule",
	},
	"Permission Request": {"validate": "gesc_app.gesc_app.access_guard.no_self_decision"},
	"Overtime Request": {"validate": "gesc_app.gesc_app.access_guard.no_self_decision"},
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
extend_doctype_class = {
	# Sent to its selected audience (hr_announcement_audience).
	"HR Announcement": "gesc_app.gesc_app.hr_announcement_audience.AudienceMixin",
}

# Overriding Methods
# ------------------------------
#
override_whitelisted_methods = {
	# A sample request's Stock Entry is a sample issue for its customer (sample_request).
	"erpnext.stock.doctype.material_request.material_request.make_stock_entry": "gesc_app.gesc_app.sample_request.make_stock_entry",
	# The employee app's push subscriptions, error log and team card, guarded (access_guard).
	"ms_hrms.web_push.subscribe": "gesc_app.gesc_app.access_guard.subscribe",
	"ms_hrms.web_push.log_client_error": "gesc_app.gesc_app.access_guard.log_client_error",
	"ms_hrms.pwa_api.get_team_today": "gesc_app.gesc_app.access_guard.get_team_today",
}
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
override_doctype_dashboards = {
	"Quotation": "gesc_app.gesc_app.quotation_dashboard.get_data",
	"Task": "gesc_app.gesc_app.task_dashboard.get_data",
	"Project": "gesc_app.gesc_app.project_warehouse.get_dashboard_data",
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
		"filters": [["name", "=", "GESC Projects"]],
	},
	{
		"doctype": "Translation",
		"filters": [["source_text", "like", "%Delivery Note%"]],
	},
]

