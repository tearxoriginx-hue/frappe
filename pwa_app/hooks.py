app_name = "pwa_app"
app_title = "PWA App"
app_publisher = "Krystaa"
app_description = "Unified PWA for RMA, Dispatch & HRMS"
app_email = "hello@krystaa.com"
app_license = "mit"
hide_in_menu = True

# DocTypes
# doctype_include removed - pattern was invalid

# Website route rules
website_route_rules = [
    {
        "from_route": "/install/manifest.json",
        "to_route": "install/manifest",
    },
    {
        "from_route": "/install/app/<path:app_path>",
        "to_route": "install/app",
    },
]

# Biometric device API endpoint moved to core_app:
# POST /api/method/core_app.api.biometric_punch.handle_punch
# Short URL: /biopunch_att (requires www page in core_app)

# Jinja template methods
jinja = {
    "methods": [],
}

# Document hooks - auto push notification on Notification Log creation
doc_events = {
    "Notification Log": {
        "on_update": "pwa_app.api.push_notification.notify_on_notification_log"
    },
    "Communication": {
        "after_insert": "pwa_app.api.push_notification.notify_on_incoming_email"
    }
}

# Auto-create Notification Settings on login (fixes Desk error for new users)
on_login = ["pwa_app.api.utils.on_login"]

# Scheduler events
scheduler_events = {
    "daily": [],
}
