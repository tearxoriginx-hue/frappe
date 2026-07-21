import frappe

from pwa_app.api.utils import get_employee as _get_employee, get_shortcuts as _get_shortcuts, has_any_role
from pwa_app.api.utils import RMA_ROLES, DISPATCH_ROLES, RMA_OPEN_STATUSES, RMA_CLOSED_STATUSES, DISPATCH_PENDING_STATUSES


@frappe.whitelist()
def get_shortcuts():
    return _get_shortcuts()


@frappe.whitelist()
def get_shortcut_badges():
    user = frappe.session.user
    employee = _get_employee(user)
    roles = frappe.get_roles()
    badges = {}

    try:
        unread = frappe.get_all(
            "Communication",
            filters={
                "communication_type": "Communication",
                "sent_or_received": "Received",
                "recipients": ["like", f"%{user}%"],
                "seen": 0,
            },
            limit_page_length=5,
        )
        badges["mail"] = len(unread)
    except Exception:
        badges["mail"] = 0

    if employee:
        try:
            pending = frappe.get_all(
                "Leave Application",
                filters={"employee": employee, "docstatus": 1, "status": ["in", ["Draft", "Applied"]]},
                limit_page_length=5,
            )
            badges["leaves"] = len(pending)
        except Exception:
            badges["leaves"] = 0

    if has_any_role(roles, RMA_ROLES):
        try:
            open_rmas = frappe.get_all(
                "RMA Request",
                filters={"docstatus": ["!=", 2], "status": ["in", RMA_OPEN_STATUSES]},
                limit_page_length=5,
            )
            badges["rma"] = len(open_rmas)
        except Exception:
            badges["rma"] = 0

    if has_any_role(roles, DISPATCH_ROLES):
        try:
            pending_dispatch = frappe.get_all(
                "Dispatch Entry",
                filters={"docstatus": ["!=", 2], "processing_status": ["in", DISPATCH_PENDING_STATUSES]},
                limit_page_length=5,
            )
            badges["dispatch"] = len(pending_dispatch)
        except Exception:
            badges["dispatch"] = 0

    return badges
