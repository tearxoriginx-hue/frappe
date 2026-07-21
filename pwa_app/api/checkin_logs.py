import frappe
from frappe import _
from pwa_app.api.utils import get_employee as _get_employee


@frappe.whitelist()
def get_my_logs(limit=50, offset=0, from_date=None, to_date=None):
    """Get check-in logs for the current user with all details."""
    user = frappe.session.user
    employee = _get_employee(user)
    if not employee:
        return {"logs": [], "total": 0}

    filters = {"employee": employee}
    if from_date:
        filters["time"] = [">=", f"{from_date} 00:00:00"]
    if to_date:
        if "time" in filters:
            filters["time"] = [filters["time"], ["<=", f"{to_date} 23:59:59"]]
        else:
            filters["time"] = ["<=", f"{to_date} 23:59:59"]

    logs = frappe.get_all(
        "Employee Checkin",
        filters=filters,
        fields=[
            "name", "log_type", "time", "device_id",
            "latitude", "longitude", "checkin_ip_address",
            "checkin_user_agent", "checkin_selfie", "checkin_within_geofence",
        ],
        order_by="time desc",
        limit=limit,
        offset=offset,
    )

    total = frappe.db.count("Employee Checkin", filters)

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
def get_employee_logs(employee=None, limit=50, offset=0, from_date=None, to_date=None):
    """HR: Get check-in logs for any employee."""
    user = frappe.session.user
    roles = frappe.get_roles()
    if not set(roles) & {"HR User", "HR Manager", "System Manager"}:
        frappe.throw(_("Permission denied"))

    filters = {}
    if employee:
        filters["employee"] = employee
    if from_date:
        filters["time"] = [">=", f"{from_date} 00:00:00"]
    if to_date:
        if "time" in filters:
            filters["time"] = [filters["time"], ["<=", f"{to_date} 23:59:59"]]
        else:
            filters["time"] = ["<=", f"{to_date} 23:59:59"]

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

    emp_ids = list(set(l.employee for l in logs if l.employee))
    emp_names = {}
    if emp_ids:
        for e in frappe.get_all("Employee", filters={"name": ["in", emp_ids]}, fields=["name", "employee_name"]):
            emp_names[e.name] = e.employee_name

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
