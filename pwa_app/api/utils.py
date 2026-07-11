import frappe

RMA_ROLES = ["RMA Staff", "RMA Manager", "System Manager"]
DISPATCH_ROLES = ["Dispatch User", "Dispatch Operator", "Dispatch Manager", "System Manager"]
HR_ROLES = ["HR User", "HR Manager", "System Manager"]
MANAGER_ROLES = ["RMA Manager", "Dispatch Manager", "HR Manager", "System Manager"]

RMA_OPEN_STATUSES = ["Draft", "In Repair", "Pending Approval", "Approved for Replacement"]
RMA_COMPLETED_STATUSES = ["Completed", "Replaced"]
RMA_CLOSED_STATUSES = ["Completed", "Replaced", "Cancelled"]

DISPATCH_PENDING_STATUSES = ["Pending", "In Queue"]
EXPENSE_PENDING_STATUSES = ["Draft", "Submitted"]


def get_employee(user=None):
    user = user or frappe.session.user
    emp = frappe.get_all(
        "Employee",
        filters={"user_id": user},
        fields=["name"],
        limit_page_length=1,
    )
    return emp[0].name if emp else None


def get_shortcuts(roles=None):
    roles = roles or frappe.get_roles()
    try:
        settings = frappe.get_single("PWA Settings")
        if settings and settings.shortcuts:
            visible = []
            for s in settings.shortcuts:
                if not s.visible:
                    continue
                if s.allowed_roles:
                    allowed = [r.strip() for r in s.allowed_roles.split(",")]
                    if not any(r in roles for r in allowed):
                        continue
                visible.append({
                    "label": s.label,
                    "icon": s.icon,
                    "icon_bg": s.icon_bg_color,
                    "icon_color": s.icon_text_color,
                    "route": s.route,
                    "badge_field": s.badge_field or "",
                })
            return visible
    except Exception:
        pass

    defaults = [
        {"label": "Attendance", "icon": "schedule", "icon_bg": "bg-blue-100", "icon_color": "text-blue-600", "route": "/attendance"},
        {"label": "Leaves", "icon": "calendar_today", "icon_bg": "bg-orange-100", "icon_color": "text-orange-600", "route": "/leaves"},
        {"label": "Expenses", "icon": "receipt_long", "icon_bg": "bg-blue-100", "icon_color": "text-blue-600", "route": "/expenses"},
        {"label": "RMA", "icon": "build", "icon_bg": "bg-purple-100", "icon_color": "text-purple-600", "route": "/rma", "allowed_roles": RMA_ROLES},
        {"label": "Dispatch", "icon": "local_shipping", "icon_bg": "bg-green-100", "icon_color": "text-green-600", "route": "/dispatch", "allowed_roles": DISPATCH_ROLES},
        {"label": "Mail", "icon": "mail", "icon_bg": "bg-red-100", "icon_color": "text-red-600", "route": "/mail"},
        {"label": "Directory", "icon": "contacts", "icon_bg": "bg-green-100", "icon_color": "text-green-600", "route": "/directory"},
        {"label": "Items", "icon": "inventory_2", "icon_bg": "bg-teal-100", "icon_color": "text-teal-600", "route": "/items"},
        {"label": "Payslips", "icon": "payments", "icon_bg": "bg-teal-100", "icon_color": "text-teal-600", "route": "/salary", "allowed_roles": HR_ROLES},
        {"label": "Customers", "icon": "people", "icon_bg": "bg-indigo-100", "icon_color": "text-indigo-600", "route": "/customers"},
    ]
    visible = []
    for d in defaults:
        allowed = d.get("allowed_roles", [])
        if allowed and not any(r in roles for r in allowed):
            continue
        visible.append({k: v for k, v in d.items() if k != "allowed_roles"})
    return visible


def has_any_role(roles, role_list):
    return any(r in roles for r in role_list)


@frappe.whitelist(allow_guest=False)
def get_app_config():
    try:
        leave_types = frappe.get_all("Leave Type", pluck="name")
    except Exception:
        leave_types = ["Casual Leave", "Sick Leave", "Privilege Leave", "Leave Without Pay", "Compensatory Off"]

    rma_status_options = ["Draft", "In Repair", "Completed", "Pending Approval", "Approved for Replacement", "Replaced", "Cancelled"]
    dispatch_status_options = ["Pending", "In Queue", "Processed", "Failed"]

    return {
        "leave_types": leave_types,
        "rma_statuses": rma_status_options,
        "dispatch_statuses": dispatch_status_options,
    }
