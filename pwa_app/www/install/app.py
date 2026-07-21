import frappe

no_cache = 1


def get_context(context):
    app_name = frappe.db.get_single_value("Website Settings", "app_name") or "ERP"
    context.site_name = app_name
    context.app_name = app_name

    context.app_logo_url = ""
    try:
        ws = frappe.get_single("Website Settings")
        context.app_logo_url = ws.splash_image or ws.application_logo or ""
        context.favicon_url = ws.favicon or "/assets/frappe/images/frappe-favicon.svg"
    except Exception:
        context.favicon_url = "/assets/frappe/images/frappe-favicon.svg"

    is_guest = frappe.session.user == "Guest"
    context.is_guest = is_guest

    if not is_guest:
        user = frappe.session.user
        context.user = user
        context.full_name = frappe.db.get_value("User", user, "full_name") or user
        context.user_email = frappe.db.get_value("User", user, "email") or user
        context.roles = frappe.get_roles()
        context.csrf_token = frappe.sessions.get_csrf_token()
    else:
        context.user = ""
        context.full_name = ""
        context.user_email = ""
        context.roles = []
        context.csrf_token = ""

    context.no_cache = 1
    context.version = "1.0 Beta"
