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

# Scheduler events
scheduler_events = {
    "daily": [],
}
