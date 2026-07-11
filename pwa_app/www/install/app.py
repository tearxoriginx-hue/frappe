import frappe

no_cache = 1


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/install/app"
        raise frappe.Redirect

    user = frappe.session.user
    context.user = user
    context.full_name = frappe.db.get_value("User", user, "full_name") or user
    context.user_email = frappe.db.get_value("User", user, "email") or user
    context.roles = frappe.get_roles()
    context.csrf_token = frappe.sessions.get_csrf_token()
    context.no_cache = 1
