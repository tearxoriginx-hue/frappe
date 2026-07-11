app_name = "core_app"
app_title = "Core App"
app_publisher = "Krystaa"
app_description = "Core DocTypes for RMA & Dispatch"
app_email = "hello@krystaa.com"
app_license = "mit"
hide_in_menu = True

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "core_app",
# 		"logo": "/assets/core_app/logo.png",
# 		"title": "Core App",
# 		"route": "/core_app",
# 		"has_permission": "core_app.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/core_app/css/core_app.css"
# app_include_js = "/assets/core_app/js/core_app.js"

# include js, css files in header of web template
# web_include_css = "/assets/core_app/css/core_app.css"
# web_include_js = "/assets/core_app/js/core_app.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "core_app/public/scss/website"

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
# app_include_icons = "core_app/public/icons.svg"

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
# 	"methods": "core_app.utils.jinja_methods",
# 	"filters": "core_app.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "core_app.install.before_install"
# after_install = "core_app.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "core_app.uninstall.before_uninstall"
# after_uninstall = "core_app.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "core_app.utils.before_app_install"
# after_app_install = "core_app.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "core_app.utils.before_app_uninstall"
# after_app_uninstall = "core_app.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "core_app.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "core_app.notifications.get_notification_config"

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
	"HR Settings": {
		"validate": "core_app.utils.biometric_settings.on_hr_settings_validate",
	},
	"Expense Claim": {
		"on_submit": "core_app.utils.salary_automation.on_expense_claim_submit",
	},
	"Employee Advance": {
		"on_submit": "core_app.utils.salary_automation.on_employee_advance_submit",
	},
}

# Custom Fields
# ----------

custom_fields = {
	"HR Settings": [
		{
			"fieldname": "biometric_settings_sb",
			"fieldtype": "Section Break",
			"label": "Biometric Settings",
			"collapsible": 1,
			"insert_after": "unlink_payment_on_cancellation_of_employee_advance",
		},
		{
			"fieldname": "enable_biometric_api",
			"default": 1,
			"fieldtype": "Check",
			"label": "Enable Biometric Punch API",
			"insert_after": "biometric_settings_sb",
		},
		{
			"fieldname": "biometric_secret_key",
			"description": "Shared secret for biometric device authentication. Clear field and save to regenerate.",
			"fieldtype": "Data",
			"label": "API Secret Key",
			"insert_after": "enable_biometric_api",
		},
		{
			"fieldname": "biometric_endpoint_url",
			"fieldtype": "Data",
			"label": "Endpoint URL",
			"read_only": 1,
			"insert_after": "biometric_secret_key",
		},
		{
			"fieldname": "biometric_short_url",
			"fieldtype": "Data",
			"label": "Short URL",
			"read_only": 1,
			"insert_after": "biometric_endpoint_url",
		},
		{
			"fieldname": "biometric_devices_link",
			"fieldtype": "HTML",
			"options": '<a href="/app/biometric-device" class="btn btn-default btn-xs">Manage Biometric Devices →</a>',
			"insert_after": "biometric_short_url",
		},
		{
			"fieldname": "biometric_punch_logs_link",
			"fieldtype": "HTML",
			"options": '<a href="/app/biometric-punch-log" class="btn btn-default btn-xs">View Punch Audit Logs →</a>',
			"insert_after": "biometric_devices_link",
		},
		{
			"fieldname": "biometric_setup_guide",
			"fieldtype": "HTML",
			"label": "Setup Instructions",
			"options": """
<h4>How to set up biometric integration</h4>
<ol>
  <li><strong>Enable the API</strong> — Ensure "Enable Biometric Punch API" is checked above.</li>
  <li><strong>Get your Secret Key</strong> — The "API Secret Key" field above was auto-generated on save. Copy this key.</li>
  <li><strong>Choose an endpoint URL</strong> — Use either the <strong>Endpoint URL</strong> or <strong>Short URL</strong> shown above. The short URL (<code>/biopunch_att</code>) is recommended for most devices.</li>
  <li><strong>Configure your biometric middleware</strong> — Set your middleware or device to POST punch data with:<br>
    <code>{ "secret": "&lt;your-secret-key&gt;", "employee_id": "&lt;employee-id&gt;", "log_type": "IN", "timestamp": "2026-07-11 09:00:00", "device_id": "ZK-Door-01" }</code>
  </li>
  <li><strong>Map employees</strong> — Go to <a href="/app/biometric-device">Biometric Device</a> to add devices, then open each <strong>Employee</strong> record to add biometric mappings (Template ID from device → Employee).</li>
  <li><strong>Test</strong> — Use any HTTP client (curl, Postman) to POST a test punch or visit the <a href="/biopunch_att">Short URL</a> to verify the endpoint is active.</li>
</ol>
<h4>How employee lookup works</h4>
<p>When a punch comes in, the system resolves the <code>employee_id</code> to an Employee record by:</p>
<ol>
  <li>Checking the <strong>Employee Biometric</strong> child table for a matching <strong>Template ID</strong></li>
  <li>If not found, matching directly by <strong>Employee Name</strong></li>
  <li>If not found, matching by the <strong>User ID</strong> linked to the Employee</li>
</ol>
<h4>Auto-sync (pull mode)</h4>
<p>If your device supports the ZKTeco protocol (port 4370), you can also configure the system to <strong>pull</strong> logs automatically:</p>
<ol>
  <li>Create a <a href="/app/biometric-device/new">Biometric Device</a> record with the device IP, port, and password.</li>
  <li>Add employee biometric mappings on each Employee record (Template ID from the device).</li>
  <li>The system will auto-sync logs every hour (scheduled job: <code>biometric_sync.sync_all_devices</code>).</li>
  <li>Or click <strong>Test Connection</strong> on the Biometric Device page to verify connectivity.</li>
</ol>
""",
			"insert_after": "biometric_punch_logs_link",
		},
	],
	"Employee": [
		{
			"fieldname": "checkin_geofence_sb",
			"fieldtype": "Section Break",
			"label": "Check-in Settings",
			"insert_after": "attendance_type",
		},
		{
			"fieldname": "checkin_geofence_type",
			"default": "SOFT",
			"fieldtype": "Select",
			"label": "Geofence Check-in Type",
			"options": "SOFT\nHARD\nDISABLED",
			"description": "HARD = block check-in outside area. SOFT = allow but flag. DISABLED = no geofence check.",
			"insert_after": "checkin_geofence_sb",
		},
	],
	"Employee Checkin": [
		{
			"fieldname": "checkin_details_sb",
			"fieldtype": "Section Break",
			"label": "Check-in Details",
			"insert_after": "employee",
		},
		{
			"fieldname": "checkin_selfie",
			"fieldtype": "Attach Image",
			"label": "Check-in Selfie",
			"insert_after": "checkin_details_sb",
		},
		{
			"fieldname": "checkin_ip_address",
			"fieldtype": "Data",
			"label": "IP Address",
			"read_only": 1,
			"insert_after": "checkin_selfie",
		},
		{
			"fieldname": "checkin_user_agent",
			"fieldtype": "Small Text",
			"label": "User Agent",
			"read_only": 1,
			"insert_after": "checkin_ip_address",
		},
		{
			"fieldname": "checkin_within_geofence",
			"fieldtype": "Check",
			"label": "Within Geofence",
			"read_only": 1,
			"insert_after": "checkin_user_agent",
		},
	],
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"core_app.tasks.all"
# 	],
# 	"daily": [
# 		"core_app.tasks.daily"
# 	],
# 	"hourly": [
# 		"core_app.tasks.hourly"
# 	],
# 	"weekly": [
# 		"core_app.tasks.weekly"
# 	],
# 	"monthly": [
# 		"core_app.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "core_app.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "core_app.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------

# Scheduled Tasks
# -----------------

scheduler_events = {
	"all": [
		"core_app.utils.biometric_sync.sync_all_devices",
	],
	"hourly": [
		"core_app.utils.biometric_sync.sync_all_devices",
	],
}

# Request Events
# ----------------
# before_request = ["core_app.utils.before_request"]
# after_request = ["core_app.utils.after_request"]

# Job Events
# ----------
# before_job = ["core_app.utils.before_job"]
# after_job = ["core_app.utils.after_job"]

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
# 	"core_app.auth.validate"
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

