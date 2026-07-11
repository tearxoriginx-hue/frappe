import frappe
from frappe import _
from pwa_app.api.utils import get_employee as _get_employee


@frappe.whitelist()
def get_my_logs(limit=50, offset=0):
    """Get check-in logs for the current user with all details."""
    user = frappe.session.user
    employee = _get_employee(user)
    if not employee:
        return {"logs": [], "total": 0}

    logs = frappe.get_all(
        "Employee Checkin",
        filters={"employee": employee},
        fields=[
            "name", "log_type", "time", "device_id",
            "latitude", "longitude", "checkin_ip_address",
            "checkin_user_agent", "checkin_selfie", "checkin_within_geofence",
        ],
        order_by="time desc",
        limit=limit,
        offset=offset,
    )

    total = frappe.db.count("Employee Checkin", {"employee": employee})

    return {
        "logs": [
            {
                "name": l.name,
                "log_type": l.log_type,
                "time": str(l.time),
                "time_formatted": frappe.utils.format_datetime(l.time),
                "device_id": l.device_id or "",
                "ip_address": l.checkin_ip_address or "",
                "user_agent": l.checkin_user_agent or "",
                "selfie_url": l.checkin_selfie or "",
                "latitude": l.latitude,
                "longitude": l.longitude,
                "map_url": f"https://www.google.com/maps?q={l.latitude},{l.longitude}" if l.latitude and l.longitude else "",
                "within_geofence": bool(l.checkin_within_geofence),
            }
            for l in logs
        ],
        "total": total,
        "employee": employee,
    }


@frappe.whitelist()
def get_employee_logs(employee=None, limit=50, offset=0):
    """HR: Get check-in logs for any employee."""
    user = frappe.session.user
    roles = frappe.get_roles()
    if not set(roles) & {"HR User", "HR Manager", "System Manager"}:
        frappe.throw(_("Permission denied"))

    filters = {}
    if employee:
        filters["employee"] = employee

    logs = frappe.get_all(
        "Employee Checkin",
        filters=filters,
        fields=[
            "name", "employee", "log_type", "time", "device_id",
            "latitude", "longitude", "checkin_ip_address",
            "checkin_user_agent", "checkin_selfie", "checkin_within_geofence",
        ],
        order_by="time desc",
        limit=limit,
        offset=offset,
    )

    employee_names = {}
    for l in logs:
        if l.employee not in employee_names:
            employee_names[l.employee] = frappe.db.get_value(
                "Employee", l.employee, "employee_name"
            )

    return {
        "logs": [
            {
                "name": l.name,
                "employee": l.employee,
                "employee_name": employee_names.get(l.employee, l.employee),
                "log_type": l.log_type,
                "time": str(l.time),
                "time_formatted": frappe.utils.format_datetime(l.time),
                "device_id": l.device_id or "",
                "ip_address": l.checkin_ip_address or "",
                "user_agent": l.checkin_user_agent or "",
                "selfie_url": l.checkin_selfie or "",
                "latitude": l.latitude,
                "longitude": l.longitude,
                "map_url": f"https://www.google.com/maps?q={l.latitude},{l.longitude}" if l.latitude and l.longitude else "",
                "within_geofence": bool(l.checkin_within_geofence),
            }
            for l in logs
        ],
        "total": len(logs),
    }
