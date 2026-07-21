import frappe
import csv
import io
from frappe import _
from frappe.utils import now_datetime


@frappe.whitelist()
def get_today_checkins(date=None):
    user = frappe.session.user
    roles = frappe.get_roles()
    if not set(roles) & {"System Manager", "HR Manager"}:
        frappe.throw(_("Permission denied"))

    today = date or frappe.utils.today()

    employees = frappe.get_all(
        "Employee",
        filters={"status": "Active"},
        fields=["name", "employee_name", "attendance_type", "designation", "department",
                "branch", "checkin_geofence_type"],
        order_by="employee_name asc",
    )

    checkins = frappe.get_all(
        "Employee Checkin",
        filters=[
            ["time", ">=", f"{today} 00:00:00"],
            ["time", "<=", f"{today} 23:59:59"],
        ],
        fields=["employee", "log_type", "time", "latitude", "longitude", "device_id",
                "checkin_within_geofence", "checkin_ip_address", "checkin_selfie"],
        order_by="time asc",
    )

    emp_checkins = {}
    for c in checkins:
        emp_checkins.setdefault(c.employee, []).append(c)

    # Get latest location track per employee
    location_tracks = []
    try:
        location_tracks = frappe.get_all(
            "Employee Location Track",
            filters={"timestamp": [">=", f"{today} 00:00:00"]},
            fields=["employee", "latitude", "longitude", "timestamp", "is_within_geofence"],
            order_by="timestamp desc",
        )
    except Exception:
        pass  # Doctype may not exist yet
    emp_latest_track = {}
    for lt in location_tracks:
        if lt.employee not in emp_latest_track:
            emp_latest_track[lt.employee] = lt

    results = []
    for emp in employees:
        emp_logs = emp_checkins.get(emp.name, [])
        checked_in = False
        check_in_time = None
        check_out_time = None
        latest_lat = None
        latest_lon = None
        within_geofence = True
        geofence_flag = None
        checkin_selfie = None

        for log in emp_logs:
            if log.log_type == "IN":
                check_in_time = str(log.time)
                checked_in = True
                if hasattr(log, "checkin_within_geofence"):
                    within_geofence = bool(log.checkin_within_geofence)
                if hasattr(log, "checkin_selfie") and log.checkin_selfie:
                    checkin_selfie = log.checkin_selfie
            elif log.log_type == "OUT":
                check_out_time = str(log.time)
                checked_in = False
            if log.latitude and log.longitude:
                latest_lat = log.latitude
                latest_lon = log.longitude

        if not within_geofence:
            geofence_flag = "OUTSIDE_GEOFENCE"

        # Use latest background track location if checkin had no lat/lng
        track = emp_latest_track.get(emp.name)
        if track and not latest_lat:
            latest_lat = track.latitude
            latest_lon = track.longitude
            if hasattr(track, "is_within_geofence") and not track.is_within_geofence:
                geofence_flag = "OUTSIDE_GEOFENCE"

        map_url = ""
        if latest_lat and latest_lon:
            map_url = f"https://www.google.com/maps?q={latest_lat},{latest_lon}"

        results.append({
            "employee": emp.name,
            "employee_name": emp.employee_name,
            "attendance_type": emp.attendance_type or "Biometric",
            "designation": emp.designation or "",
            "department": emp.department or "",
            "branch": emp.branch or "",
            "checkin_geofence_type": emp.checkin_geofence_type or "SOFT",
            "checked_in": checked_in,
            "check_in_time": check_in_time,
            "check_out_time": check_out_time,
            "latitude": latest_lat,
            "longitude": latest_lon,
            "map_url": map_url,
            "geofence_flag": geofence_flag,
            "within_geofence": within_geofence,
            "has_selfie": bool(checkin_selfie),
            "selfie_url": checkin_selfie or "",
            "punches": len(emp_logs),
        })

    return {
        "date": today,
        "total_employees": len(employees),
        "checked_in_count": sum(1 for r in results if r["checked_in"]),
        "geo_count": sum(1 for r in results if r["attendance_type"] in ("Geo-Location", "Both") and r["latitude"]),
        "outside_geofence_count": sum(1 for r in results if r["geofence_flag"]),
        "employees": results,
    }


@frappe.whitelist()
def get_employee_tracks(employee=None):
    """Get location tracks for one or all employees today (for map rendering)."""
    user = frappe.session.user
    roles = frappe.get_roles()
    if not set(roles) & {"System Manager", "HR Manager"}:
        frappe.throw(_("Permission denied"))

    today = frappe.utils.today()
    filters = {"timestamp": [">=", f"{today} 00:00:00"]}
    if employee:
        filters["employee"] = employee

    tracks = frappe.get_all(
        "Employee Location Track",
        filters=filters,
        fields=["employee", "latitude", "longitude", "timestamp", "is_within_geofence"],
        order_by="timestamp asc",
        limit_page_length=500,
    )

    return {
        "tracks": tracks,
        "count": len(tracks),
    }


@frappe.whitelist()
def get_employee_summary(date=None):
    user = frappe.session.user
    roles = frappe.get_roles()
    if not set(roles) & {"System Manager", "HR Manager"}:
        frappe.throw(_("Permission denied"))

    today = date or frappe.utils.today()
    total_active = frappe.db.count("Employee", {"status": "Active"})
    on_leave = frappe.db.count("Leave Application", {
        "status": "Approved",
        "from_date": ["<=", today],
        "to_date": [">=", today],
    })

    return {
        "total_active": total_active,
        "on_leave_today": on_leave,
        "present_today": total_active - on_leave,
    }


@frappe.whitelist()
def export_payroll(month, year):
    user = frappe.session.user
    roles = frappe.get_roles()
    if not set(roles) & {"HR Manager", "System Manager"}:
        frappe.throw(_("Permission denied"))

    month = int(month)
    year = int(year)

    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"

    slips = frappe.get_all(
        "Salary Slip",
        filters={
            "start_date": [">=", start_date],
            "end_date": ["<", end_date],
            "docstatus": 1,
        },
        fields=[
            "employee", "employee_name", "department", "designation",
            "gross_pay", "total_deduction", "net_pay",
            "bank_name", "bank_account_no", "ifsc_code",
            "start_date", "end_date",
        ],
        order_by="employee_name asc",
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Employee ID", "Employee Name", "Department", "Designation",
        "Gross Pay", "Total Deduction", "Net Pay",
        "Bank Name", "Bank Account", "IFSC Code",
        "Period Start", "Period End",
    ])
    for s in slips:
        writer.writerow([
            s.employee, s.employee_name, s.department or "", s.designation or "",
            float(s.gross_pay or 0), float(s.total_deduction or 0), float(s.net_pay or 0),
            s.bank_name or "", s.bank_account_no or "", s.ifsc_code or "",
            str(s.start_date), str(s.end_date),
        ])

    fname = f"payroll_{month}_{year}.csv"
    content = output.getvalue()

    _file = frappe.get_doc({
        "doctype": "File",
        "file_name": fname,
        "content": content,
        "is_private": 1,
    })
    _file.save(ignore_permissions=True)

    return {
        "file_url": _file.file_url,
        "file_name": fname,
        "record_count": len(slips),
    }

@frappe.whitelist()
def get_employee_attendance(employee, days=7):
    user = frappe.session.user
    roles = frappe.get_roles()
    if not set(roles) & {"System Manager", "HR Manager"}:
        frappe.throw(_("Permission denied"))
    today = frappe.utils.today()
    from datetime import timedelta, datetime
    start = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=days-1)).strftime("%Y-%m-%d")
    logs = frappe.get_all("Employee Checkin",
        filters=[
            ["employee", "=", employee],
            ["time", ">=", f"{start} 00:00:00"],
            ["time", "<=", f"{today} 23:59:59"],
        ],
        fields=["name", "log_type", "time", "device_id", "latitude", "longitude"],
        order_by="time desc")
    return {"logs": logs, "count": len(logs)}