app_name = "rma_app"
app_title = "RMA Service Center"
app_publisher = "Krystaa"
app_description = "RMA Service Center - Repair and Replacement Management"
app_email = "hello@krystaa.com"
app_license = "mit"

required_apps = ["core_app"]

after_install = "rma_app.install.after_install"

doctype_js = {
    "RMA Request": "rma_module/doctype/rma_request/rma_request.js"
}

permission_query_conditions = {
    "RMA Request": "rma_app.permissions.rma_request_query",
}

has_permission = {
    "RMA Request": "rma_app.permissions.rma_request_has_permission",
}

scheduler_events = {
    "daily": [
        "rma_app.tasks.daily_overdue_alerts",
    ],
    "monthly": [
        "rma_app.tasks.auto_archive_old_rmas",
    ],
}
