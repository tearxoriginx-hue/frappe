import frappe
from frappe.utils import now_datetime


def _time_ago(dt):
    """Calculate time ago in human-readable format, safe replacement for deprecated frappe.utils.time_ago."""
    diff = now_datetime() - dt
    days = diff.days
    seconds = diff.seconds
    if days > 30:
        months = days // 30
        return f"{months}mo ago"
    if days > 0:
        return f"{days}d ago"
    hours = seconds // 3600
    if hours > 0:
        return f"{hours}h ago"
    minutes = seconds // 60
    if minutes > 0:
        return f"{minutes}m ago"
    return "just now"


@frappe.whitelist()
def get_notifications():
    user = frappe.session.user

    notifs = frappe.get_all(
        "Notification Log",
        filters={"for_user": user},
        fields=["name", "subject", "type", "creation", "document_type", "document_name", "read"],
        order_by="creation desc",
        limit=50,
    )
    return [
        {
            "name": n.name,
            "subject": n.subject,
            "type": n.type,
            "creation": str(n.creation),
            "time_ago": _time_ago(n.creation),
            "document_type": n.document_type,
            "document_name": n.document_name,
            "read": n.read,
        }
        for n in notifs
    ]


@frappe.whitelist()
def mark_read(name):
    frappe.db.set_value("Notification Log", name, "read", 1)
    return {"success": True}


@frappe.whitelist()
def mark_all_read():
    user = frappe.session.user
    frappe.db.set_value("Notification Log", {"for_user": user, "read": 0}, "read", 1)
    return {"success": True}


@frappe.whitelist()
def get_unread_count():
    user = frappe.session.user
    count = frappe.db.count("Notification Log", {"for_user": user, "read": 0})
    return {"count": count}
