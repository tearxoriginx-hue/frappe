app_name = "hrms2"
app_title = "HRMS2"
app_publisher = "Krystaa"
app_description = "Stripped HR & Payroll - Essential features only"
app_email = "hello@krystaa.com"
app_license = "MIT"

# Apps
# ------------------
# required_apps = []

# Includes in <head>
# ------------------
# app_include_js = "hrms2.bundle.js"
# app_include_css = "hrms2.bundle.css"

# include js in doctype views
# doctype_js = {
#     "Employee": "public/js/employee.js",
#     "Employee Checkin": "public/js/employee_checkin.js",
# }

# Scheduled Tasks
# -----------------
scheduler_events = {
    "hourly": [
        "hrms2.utils.biometric_sync.sync_all_devices",
    ],
}

# Document Events
# ---------------
doc_events = {
    "Employee Checkin": {
        "on_update": "hrms2.hrms2.doctype.employee_checkin.employee_checkin.update_attendance_from_checkin",
    },
}

# Permissions
# -----------
permission_query_conditions = {}

has_permission = {}

# User Data Protection
# --------------------
user_data_fields = [
    {
        "doctype": "Employee",
        "filter_by": "user_id",
        "redact_fields": ["employee_name", "date_of_birth", "cell_number"],
        "partial": 1,
    },
]
