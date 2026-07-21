import frappe

from pwa_app.api.utils import get_employee as _get_employee, get_shortcuts as _get_shortcuts, has_any_role
from pwa_app.api.utils import RMA_ROLES, DISPATCH_ROLES, HR_ROLES, MANAGER_ROLES
from pwa_app.api.utils import RMA_OPEN_STATUSES, RMA_COMPLETED_STATUSES, RMA_CLOSED_STATUSES
from pwa_app.api.utils import DISPATCH_PENDING_STATUSES, EXPENSE_PENDING_STATUSES


@frappe.whitelist()
def get_dashboard_config():
    user = frappe.session.user
    roles = frappe.get_roles()
    return {
        "user": {
            "name": user,
            "full_name": frappe.db.get_value("User", user, "full_name") or user,
            "email": frappe.db.get_value("User", user, "email") or user,
            "roles": roles,
            "avatar": frappe.db.get_value("User", user, "user_image") or "",
        },
        "shortcuts": _get_shortcuts(roles),
        "features": _get_feature_flags(roles),
    }


@frappe.whitelist()
def get_dashboard_stats():
    user = frappe.session.user
    roles = frappe.get_roles()
    employee = _get_employee(user)
    return {
        "attendance": _get_attendance_stats(employee),
        "leaves": _get_leave_stats(employee),
        "rma": _get_rma_stats(roles),
        "dispatch": _get_dispatch_stats(roles),
        "expenses": _get_expense_stats(employee),
        "mail": _get_mail_stats(user),
    }


@frappe.whitelist()
def get_recent_activity(limit=10):
    user = frappe.session.user
    roles = frappe.get_roles()
    employee = _get_employee(user)
    activities = []

    if employee:
        checkins = frappe.get_all(
            "Employee Checkin",
            filters={"employee": employee},
            fields=["name", "log_type", "time", "creation"],
            order_by="creation desc",
            limit_page_length=3,
        )
        for c in checkins:
            activities.append({
                "type": "attendance",
                "icon": "login" if c.log_type == "IN" else "logout",
                "icon_color": "green" if c.log_type == "IN" else "orange",
                "title": f"Shift {'Started' if c.log_type == 'IN' else 'Ended'}",
                "subtitle": f"Punch {c.log_type.lower()} recorded",
                "time": frappe.utils.format_time(c.time),
                "date": frappe.utils.format_date(c.time),
                "route": "/attendance",
            })

    if has_any_role(roles, RMA_ROLES):
        rmas = frappe.get_all(
            "RMA Request",
            filters={"docstatus": ["!=", 2]},
            fields=["name", "status", "item_name", "creation"],
            order_by="creation desc",
            limit_page_length=3,
        )
        for r in rmas:
            activities.append({
                "type": "rma",
                "icon": "build",
                "icon_color": "blue",
                "title": r.name,
                "subtitle": r.item_name or "RMA Request",
                "time": frappe.utils.format_time(r.creation),
                "date": frappe.utils.format_date(r.creation),
                "route": "/rma",
            })

    if has_any_role(roles, DISPATCH_ROLES):
        dispatches = frappe.get_all(
            "Dispatch Entry",
            filters={"docstatus": ["!=", 2]},
            fields=["name", "customer", "processing_status", "creation"],
            order_by="creation desc",
            limit_page_length=3,
        )
        for d in dispatches:
            activities.append({
                "type": "dispatch",
                "icon": "local_shipping",
                "icon_color": "purple",
                "title": d.name,
                "subtitle": d.customer or "Dispatch",
                "time": frappe.utils.format_time(d.creation),
                "date": frappe.utils.format_date(d.creation),
                "route": "/dispatch",
            })

    activities.sort(key=lambda x: x.get("date", ""), reverse=True)
    return activities[:limit]


def _get_feature_flags(roles):
    return {
        "dispatch": has_any_role(roles, DISPATCH_ROLES),
        "rma": has_any_role(roles, RMA_ROLES),
        "hr": has_any_role(roles, HR_ROLES),
        "manager": has_any_role(roles, MANAGER_ROLES),
    }


def _get_attendance_stats(employee):
    if not employee:
        return {"checked_in": False, "today_logs": [], "weekly_present": 0}

    today = frappe.utils.today()
    logs = frappe.get_all(
        "Employee Checkin",
        filters={"employee": employee, "time": [">=", today + " 00:00:00"]},
        fields=["name", "log_type", "time"],
        order_by="time asc",
    )

    checked_in = False
    if logs:
        checked_in = logs[-1].log_type == "IN"

    week_start = frappe.utils.add_days(today, -frappe.utils.getdate(today).weekday())
    weekly = frappe.get_all(
        "Employee Checkin",
        filters={"employee": employee, "time": [">=", week_start + " 00:00:00"]},
        fields=["DATE(time) as date"],
        group_by="DATE(time)",
    )

    return {
        "checked_in": checked_in,
        "today_logs": [{"log_type": l.log_type, "time": frappe.utils.format_time(l.time)} for l in logs],
        "weekly_present": len(weekly),
        "last_checkin": frappe.utils.format_time(logs[-1].time) if logs else None,
    }


def _get_leave_stats(employee):
    if not employee:
        return {"balances": [], "pending": 0}

    allocations = frappe.get_all(
        "Leave Allocation",
        filters={"employee": employee, "docstatus": 1},
        fields=["leave_type", "total_leaves_allocated", "total_leave_days"],
    )
    balances = [
        {
            "type": a.leave_type,
            "allocated": a.total_leaves_allocated or 0,
            "used": a.total_leave_days or 0,
            "remaining": (a.total_leaves_allocated or 0) - (a.total_leave_days or 0),
        }
        for a in allocations
    ]

    pending = frappe.get_all(
        "Leave Application",
        filters={"employee": employee, "docstatus": 1, "status": ["in", ["Draft", "Applied"]]},
        limit_page_length=5,
    )

    return {"balances": balances, "pending": len(pending)}


def _get_rma_stats(roles):
    if not has_any_role(roles, RMA_ROLES):
        return {"total": 0, "open": 0, "completed": 0}

    total = frappe.db.count("RMA Request", {"docstatus": ["!=", 2]})
    return {
        "total": total,
        "open": total,
        "completed": 0,
    }


def _get_dispatch_stats(roles):
    if not has_any_role(roles, DISPATCH_ROLES):
        return {"total": 0, "pending": 0}

    total = frappe.db.count("Dispatch Entry", {"docstatus": ["!=", 2]})
    return {
        "total": total,
        "pending": 0,
    }


def _get_expense_stats(employee):
    if not employee:
        return {"total": 0, "pending": 0, "approved": 0, "amount": 0}

    total = frappe.db.count("Expense Claim", {"employee": employee, "docstatus": ["!=", 2]})
    return {
        "total": total,
        "pending": 0,
        "approved": 0,
        "amount": 0,
    }


def _get_mail_stats(user):
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
        return {"unread": len(unread)}
    except Exception:
        return {"unread": 0}
