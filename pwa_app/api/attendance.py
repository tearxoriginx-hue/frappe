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


@frappe.whitelist(methods=["POST"])
def check_in(latitude=None, longitude=None):
    user = frappe.session.user
    employee = _get_employee(user)
    if not employee:
        frappe.throw(_("No employee record found for this user"))

    att_type = frappe.db.get_value("Employee", employee, "attendance_type") or "Biometric"
    if att_type == "Biometric":
        frappe.throw(_("Your attendance is managed via biometric device. PWA check-in is not available."))

    if att_type in ("Geo-Location", "Both") and not (latitude and longitude):
        frappe.throw(_("Location is required for check-in. Please enable GPS."))

    today = frappe.utils.today()
    last_log = frappe.get_all(
        "Employee Checkin",
        filters={"employee": employee, "time": [">=", f"{today} 00:00:00"]},
        fields=["log_type"],
        order_by="time desc",
        limit_page_length=1,
    )
    if last_log and last_log[0].log_type == "IN":
        frappe.throw(_("Already checked in today"))

    geofence_flag = None
    if latitude and longitude:
        _, geofence_flag = validate_geofence(employee, latitude, longitude)

    ip_address = frappe.local.request_ip if hasattr(frappe.local, "request_ip") else None
    user_agent = frappe.local.request.headers.get("User-Agent") if hasattr(frappe.local, "request") else None

    try:
        checkin_name = frappe.call(
            "hrms.hr.doctype.employee_checkin.employee_checkin.add_log_based_on_employee_field",
            employee_field_value=user,
            log_type="IN",
            device_id="PWA",
            employee_fieldname="user_id",
            latitude=latitude,
            longitude=longitude,
        )

        if checkin_name:
            frappe.db.set_value("Employee Checkin", checkin_name, {
                "checkin_ip_address": ip_address,
                "checkin_user_agent": user_agent,
                "checkin_within_geofence": 1 if geofence_flag is None else 0,
            }, update_modified=False)

        frappe.db.commit()

        extra = {}
        if geofence_flag == "OUTSIDE_GEOFENCE":
            extra["warning"] = "You are outside the designated check-in area. Location has been flagged."

        return {
            "success": True,
            "message": "Checked in successfully",
            "checkin_name": checkin_name,
            **extra,
        }
    except Exception as e:
        frappe.throw(str(e))


@frappe.whitelist(methods=["POST"])
def check_out(latitude=None, longitude=None):
    user = frappe.session.user
    employee = _get_employee(user)
    if not employee:
        frappe.throw(_("No employee record found for this user"))

    today = frappe.utils.today()
    last_log = frappe.get_all(
        "Employee Checkin",
        filters={"employee": employee, "time": [">=", f"{today} 00:00:00"]},
        fields=["log_type", "name"],
        order_by="time desc",
        limit_page_length=1,
    )
    if not last_log or last_log[0].log_type == "OUT":
        frappe.throw(_("Not currently checked in"))

    ip_address = frappe.local.request_ip if hasattr(frappe.local, "request_ip") else None
    user_agent = frappe.local.request.headers.get("User-Agent") if hasattr(frappe.local, "request") else None

    try:
        checkin_name = frappe.call(
            "hrms.hr.doctype.employee_checkin.employee_checkin.add_log_based_on_employee_field",
            employee_field_value=user,
            log_type="OUT",
            device_id="PWA",
            employee_fieldname="user_id",
            latitude=latitude,
            longitude=longitude,
        )

        if checkin_name and (ip_address or user_agent):
            updates = {}
            if ip_address: updates["checkin_ip_address"] = ip_address
            if user_agent: updates["checkin_user_agent"] = user_agent
            frappe.db.set_value("Employee Checkin", checkin_name, updates, update_modified=False)

        frappe.db.commit()
        return {"success": True, "message": "Checked out successfully", "checkin_name": checkin_name}
    except Exception as e:
        frappe.throw(str(e))


@frappe.whitelist(methods=["POST"])
def upload_checkin_selfie(checkin_name):
    """
    Upload selfie image and attach to an Employee Checkin record.
    Expects multipart file upload with field name 'file'.
    """
    if not checkin_name:
        frappe.throw(_("checkin_name is required"))

    if not frappe.db.exists("Employee Checkin", checkin_name):
        frappe.throw(_("Checkin record not found"))

    if "file" not in frappe.request.files:
        frappe.throw(_("No file uploaded. Send file with field name 'file'."))

    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": frappe.request.files["file"].filename,
        "is_private": 1,
        "content": frappe.request.files["file"].read(),
        "attached_to_doctype": "Employee Checkin",
        "attached_to_name": checkin_name,
    })
    file_doc.save(ignore_permissions=True)

    frappe.db.set_value("Employee Checkin", checkin_name, "checkin_selfie", file_doc.file_url, update_modified=False)
    frappe.db.commit()

    return {"success": True, "file_url": file_doc.file_url}


@frappe.whitelist()
def get_requests():
    user = frappe.session.user
    employee = _get_employee(user)
    roles = frappe.get_roles()
    is_hr = bool(set(roles) & {"HR User", "HR Manager", "System Manager"})

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
    is_hr = bool(set(roles) & {"HR User", "HR Manager", "System Manager"})
    if not is_hr:
        frappe.throw(_("Only HR users can approve requests"))

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
        frappe.throw(_("Unsupported doctype"))

    frappe.db.commit()
    return {"success": True, "message": f"{doctype} approved"}


@frappe.whitelist()
def reject_request(doctype, name, reason=None):
    user = frappe.session.user
    roles = frappe.get_roles()
    is_hr = bool(set(roles) & {"HR User", "HR Manager", "System Manager"})
    if not is_hr:
        frappe.throw(_("Only HR users can reject requests"))

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
        frappe.throw(_("Unsupported doctype"))

    frappe.db.commit()
    return {"success": True, "message": f"{doctype} rejected"}
