import frappe
from frappe import _
from pwa_app.api.utils import get_employee as _get_employee
from pwa_app.api.geofence import validate_geofence


@frappe.whitelist()
def get_attendance_status():
    user = frappe.session.user
    employee = _get_employee(user)
    if not employee:
        return {"checked_in": False, "employee": None, "logs": []}

    today = frappe.utils.today()
    logs = frappe.get_all(
        "Employee Checkin",
        filters={"employee": employee, "time": [">=", f"{today} 00:00:00"]},
        fields=["name", "log_type", "time", "device_id"],
        order_by="time asc",
    )

    checked_in = False
    if logs:
        last_log = logs[-1]
        checked_in = last_log.log_type == "IN"

    return {
        "checked_in": checked_in,
        "employee": employee,
        "logs": [
            {
                "name": l.name,
                "type": l.log_type,
                "time": frappe.utils.format_time(l.time),
                "full_time": str(l.time),
                "device": l.device_id or "",
            }
            for l in logs
        ],
        "last_checkin": frappe.utils.format_time(logs[-1].time) if logs and checked_in else None,
    }


def _validate_attendance_type(employee, action="check-in", latitude=None, longitude=None):
    att_type = frappe.db.get_value("Employee", employee, "attendance_type") or "Biometric"
    if att_type == "Biometric":
        return {"success": False, "message": f"Your attendance is managed via biometric device. PWA {action} is not available."}
    if att_type in ("Geo-Location", "Both") and not (latitude and longitude):
        return {"success": False, "message": "Location is required. Please enable GPS."}
    return None


def _do_checkin(employee, user, log_type, latitude, longitude, ip_address, user_agent, geofence_flag=None):
    result = frappe.call(
        "hrms2.hrms2.doctype.employee_checkin.employee_checkin.add_log_based_on_employee_field",
        employee_field_value=user,
        log_type=log_type,
        device_id="PWA",
        employee_fieldname="user_id",
        latitude=latitude,
        longitude=longitude,
    )
    if not result or not result.get("log_name"):
        return {"success": False, "message": "Failed to create checkin log"}

    checkin_name = result["log_name"]
    updates = {}
    if ip_address:
        updates["checkin_ip_address"] = ip_address
    if user_agent:
        updates["checkin_user_agent"] = user_agent
    if latitude and longitude:
        updates["checkin_within_geofence"] = 1 if geofence_flag != "OUTSIDE_GEOFENCE" else 0
    if updates:
        try:
            frappe.db.set_value("Employee Checkin", checkin_name, updates, update_modified=False)
        except Exception:
            pass

    frappe.db.commit()
    return {"success": True, "message": "Checked in successfully", "checkin_name": checkin_name}


@frappe.whitelist(methods=["POST"])
def check_in(latitude=None, longitude=None):
    user = frappe.session.user
    employee = _get_employee(user)
    if not employee:
        return {"success": False, "message": "No employee record found for this user"}

    err = _validate_attendance_type(employee, "check-in", latitude, longitude)
    if err:
        return err

    today = frappe.utils.today()
    last_log = frappe.get_all(
        "Employee Checkin",
        filters={"employee": employee, "time": [">=", f"{today} 00:00:00"]},
        fields=["log_type"],
        order_by="time desc",
        limit_page_length=1,
    )
    if last_log and last_log[0].log_type == "IN":
        return {"success": False, "message": "Already checked in today"}

    geofence_flag = None
    if latitude and longitude:
        _, geofence_flag = validate_geofence(employee, latitude, longitude)

    ip_address = frappe.local.request_ip if hasattr(frappe.local, "request_ip") else None
    user_agent = frappe.local.request.headers.get("User-Agent") if hasattr(frappe.local, "request") else None

    try:
        result = _do_checkin(employee, user, "IN", latitude, longitude, ip_address, user_agent, geofence_flag)
        if geofence_flag == "OUTSIDE_GEOFENCE":
            result["warning"] = "You are outside the designated check-in area. Location has been flagged."
        return result
    except Exception as e:
        return {"success": False, "message": str(e)}


@frappe.whitelist(methods=["POST"])
def check_out(latitude=None, longitude=None):
    user = frappe.session.user
    employee = _get_employee(user)
    if not employee:
        return {"success": False, "message": "No employee record found for this user"}

    err = _validate_attendance_type(employee, "check-out", latitude, longitude)
    if err:
        return err

    today = frappe.utils.today()
    last_log = frappe.get_all(
        "Employee Checkin",
        filters={"employee": employee, "time": [">=", f"{today} 00:00:00"]},
        fields=["log_type", "name"],
        order_by="time desc",
        limit_page_length=1,
    )
    if not last_log or last_log[0].log_type == "OUT":
        return {"success": False, "message": "Not currently checked in"}

    ip_address = frappe.local.request_ip if hasattr(frappe.local, "request_ip") else None
    user_agent = frappe.local.request.headers.get("User-Agent") if hasattr(frappe.local, "request") else None

    try:
        return _do_checkin(employee, user, "OUT", latitude, longitude, ip_address, user_agent)
    except Exception as e:
        return {"success": False, "message": str(e)}


@frappe.whitelist(methods=["POST"])
def upload_checkin_selfie(checkin_name):
    """
    Upload selfie image and attach to an Employee Checkin record.
    Expects multipart file upload with field name 'file'.
    """
    if not checkin_name:
        frappe.throw(frappe._("checkin_name is required"))

    if not frappe.db.exists("Employee Checkin", checkin_name):
        frappe.throw(frappe._("Checkin record not found"))

    # Verify the checkin belongs to the current user's employee
    user = frappe.session.user
    employee = _get_employee(user)
    checkin_employee = frappe.db.get_value("Employee Checkin", checkin_name, "employee")
    if checkin_employee != employee:
        frappe.throw(frappe._("Permission denied"))

    if "file" not in frappe.request.files:
        frappe.throw(frappe._("No file uploaded. Send file with field name 'file'."))

    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": frappe.request.files["file"].filename,
        "is_private": 1,
        "content": frappe.request.files["file"].read(),
        "attached_to_doctype": "Employee Checkin",
        "attached_to_name": checkin_name,
    })
    file_doc.save(ignore_permissions=True)

    try:
        frappe.db.set_value("Employee Checkin", checkin_name, "checkin_selfie", file_doc.file_url, update_modified=False)
    except Exception:
        pass
    frappe.db.commit()

    return {"success": True, "file_url": file_doc.file_url}


@frappe.whitelist()
def get_requests():
    user = frappe.session.user
    employee = _get_employee(user)
    roles = frappe.get_roles()
    is_hr = bool(set(roles) & {"HR Manager", "System Manager"})

    my_requests = []
    team_requests = []

    def fmt(doc_type, name, title, status, date, employee_name=None, can_approve=False):
        return {
            "type": doc_type,
            "name": name,
            "title": title,
            "status": status,
            "date": str(date) if date else "",
            "employee_name": employee_name or "",
            "can_approve": can_approve,
        }

    if employee:
        for dt, fields, title_fmt in [
            ("Leave Application", ["name", "leave_type", "from_date", "to_date", "status", "creation"],
             lambda d: f"{d.leave_type} ({d.from_date} to {d.to_date})"),
            ("Expense Claim", ["name", "total_claimed_amount", "posting_date", "status", "creation"],
             lambda d: f"\u20B9{float(d.total_claimed_amount or 0):.0f} on {d.posting_date}"),
            ("Employee Advance", ["name", "amount", "purpose", "status", "creation"],
             lambda d: f"\u20B9{float(d.amount or 0):.0f} - {d.purpose or ''}"),
        ]:
            docs = frappe.get_all(dt, filters={"employee": employee, "docstatus": ["!=", 2]},
                                  fields=fields, order_by="creation desc", limit=20)
            for d in docs:
                my_requests.append(fmt(dt, d.name, title_fmt(d), d.status, d.creation))

    if is_hr:
        for dt, status_filter, fields, title_fmt in [
            ("Leave Application", {"docstatus": 0},
             ["name", "leave_type", "from_date", "to_date", "status", "employee", "employee_name", "creation"],
             lambda d: f"{d.employee_name} - {d.leave_type} ({d.from_date} to {d.to_date})"),
            ("Expense Claim", {"status": "Submitted"},
             ["name", "total_claimed_amount", "posting_date", "status", "employee", "employee_name", "creation"],
             lambda d: f"{d.employee_name} - \u20B9{float(d.total_claimed_amount or 0):.0f}"),
            ("Employee Advance", {"docstatus": 0},
             ["name", "amount", "purpose", "status", "employee", "employee_name", "creation"],
             lambda d: f"{d.employee_name} - \u20B9{float(d.amount or 0):.0f}"),
        ]:
            docs = frappe.get_all(dt, filters=status_filter, fields=fields, order_by="creation desc", limit=20)
            for d in docs:
                team_requests.append(fmt(dt, d.name, title_fmt(d), d.status, d.creation, d.employee_name, can_approve=True))
        team_requests.sort(key=lambda r: r["date"], reverse=True)

    my_requests.sort(key=lambda r: r["date"], reverse=True)
    return {"my_requests": my_requests, "team_requests": team_requests}


@frappe.whitelist()
def get_weekly_summary():
    user = frappe.session.user
    employee = _get_employee(user)
    if not employee:
        return {"days": []}

    today = frappe.utils.today()
    weekday_num = frappe.utils.getdate(today).weekday()
    week_start = frappe.utils.add_days(today, -weekday_num)

    logs = frappe.get_all(
        "Employee Checkin",
        filters={"employee": employee, "time": [">=", f"{week_start} 00:00:00"]},
        fields=["DATE(time) as date", "log_type"],
        order_by="time asc",
    )

    day_map = {}
    for log in logs:
        d = str(log.date)
        if d not in day_map:
            day_map[d] = {"present": False, "entries": 0}
        day_map[d]["entries"] += 1
        if log.log_type == "IN":
            day_map[d]["present"] = True

    days = []
    for i in range(7):
        d = frappe.utils.add_days(week_start, i)
        ds = str(d)
        day_info = day_map.get(ds, {"present": False, "entries": 0})
        days.append({
            "date": frappe.utils.format_date(d, "ddd, MMM d"),
            "day": frappe.utils.format_date(d, "dddd"),
            "present": day_info["present"],
            "entries": day_info["entries"],
        })

    return {"days": days}


@frappe.whitelist()
def approve_request(doctype, name):
    user = frappe.session.user
    roles = frappe.get_roles()
    is_hr = bool(set(roles) & {"HR Manager", "System Manager"})
    if not is_hr:
        frappe.throw(frappe._("Only HR users can approve requests"))

    doc = frappe.get_doc(doctype, name)
    if doctype == "Leave Application":
        doc.status = "Approved"
        doc.save(ignore_permissions=True)
    elif doctype == "Expense Claim":
        doc.approval_status = "Approved"
        doc.submit()
    elif doctype == "Employee Advance":
        doc.submit()
    else:
        frappe.throw(frappe._("Unsupported doctype"))

    frappe.db.commit()
    return {"success": True, "message": f"{doctype} approved"}


@frappe.whitelist()
def reject_request(doctype, name, reason=None):
    user = frappe.session.user
    roles = frappe.get_roles()
    is_hr = bool(set(roles) & {"HR Manager", "System Manager"})
    if not is_hr:
        frappe.throw(frappe._("Only HR users can reject requests"))

    doc = frappe.get_doc(doctype, name)
    if doctype == "Leave Application":
        doc.status = "Rejected"
        doc.save(ignore_permissions=True)
    elif doctype == "Expense Claim":
        doc.approval_status = "Rejected"
        doc.submit()
    elif doctype == "Employee Advance":
        doc.cancel()
    else:
        frappe.throw(frappe._("Unsupported doctype"))

    frappe.db.commit()
    return {"success": True, "message": f"{doctype} rejected"}
