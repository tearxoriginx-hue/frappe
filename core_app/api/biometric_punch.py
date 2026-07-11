import frappe
from frappe import _
from frappe.utils import now_datetime


@frappe.whitelist(allow_guest=True, methods=["POST"])
def handle_punch(secret=None, employee_id=None, log_type="IN", timestamp=None, device_id=None):
    """
    Public endpoint for biometric devices to push punch data.

    POST /api/method/core_app.api.biometric_punch.handle_punch
    {
        "secret": "auto-generated-secret",
        "employee_id": "EMP001",
        "log_type": "IN",
        "timestamp": "2026-07-11 09:00:00",
        "device_id": "ZK-Door-01"
    }
    """
    punch_time = timestamp or now_datetime()
    ip_address = frappe.local.request_ip if hasattr(frappe.local, "request_ip") else None

    try:
        secret_valid = _verify_secret(secret)

        if log_type not in ("IN", "OUT"):
            frappe.throw(_("log_type must be IN or OUT"))

        if not employee_id:
            frappe.throw(_("employee_id is required"))

        employee = _resolve_employee(employee_id)
        if not employee:
            frappe.throw(_("No employee found matching: {}").format(employee_id))

        frappe.call(
            "hrms.hr.doctype.employee_checkin.employee_checkin.add_log_based_on_employee_field",
            employee_field_value=employee["field_value"],
            log_type=log_type,
            device_id=device_id or "Biometric-Device",
            timestamp=punch_time,
            employee_fieldname=employee["fieldname"],
        )

        frappe.db.commit()

        _log_punch(
            "Success", punch_time, employee["name"], device_id,
            log_type, employee_id, ip_address, secret_valid, None,
        )

        return {
            "status": "success",
            "employee": employee["name"],
            "time": str(punch_time),
        }

    except frappe.ValidationError as e:
        _log_punch(
            "Error", punch_time, None, device_id,
            log_type, employee_id, ip_address, secret_valid, str(e),
        )
        raise

    except Exception as e:
        _log_punch(
            "Error", punch_time, None, device_id,
            log_type, employee_id, ip_address, secret_valid, str(e),
        )
        raise


@frappe.whitelist(allow_guest=True, methods=["GET"])
def ping():
    """Health check for biometric device connectivity testing."""
    return {"status": "ok", "message": "Biometric endpoint active"}


def _verify_secret(secret):
    """Validate shared secret from HR Settings. Returns True if valid."""
    if not secret:
        frappe.throw(_("Secret key is required"))

    expected = frappe.db.get_single_value("HR Settings", "biometric_secret_key")
    if not expected:
        frappe.throw(_("Biometric secret not configured in HR Settings"))

    if secret != expected:
        frappe.throw(_("Invalid secret key"))

    return True


def _resolve_employee(employee_id):
    """
    Resolve employee from their employee_id string.
    Tries:
      1. Employee Biometric child table (by template_id on any device)
      2. Employee.name (direct match)
      3. Employee.user_id (match by linked User ID)
    """
    bio = frappe.db.get_value(
        "Employee Biometric",
        {"template_id": employee_id},
        ["parent", "template_id"],
        as_dict=True,
    )
    if bio:
        device_link = frappe.db.get_value(
            "Employee Biometric",
            {"template_id": employee_id, "parent": bio.parent},
            "biometric_device",
        )
        return {
            "name": bio.parent,
            "field_value": employee_id,
            "fieldname": "attendance_device_id",
            "biometric_device": device_link,
        }

    emp = frappe.db.get_value(
        "Employee",
        {"name": employee_id},
        ["name", "user_id"],
        as_dict=True,
    )
    if emp:
        field_val = emp.user_id or emp.name
        return {
            "name": emp.name,
            "field_value": field_val,
            "fieldname": "user_id" if emp.user_id else "name",
            "biometric_device": None,
        }

    return None


def _log_punch(status, timestamp, employee, device_id, log_type,
               employee_id_sent, ip_address, secret_valid, error_message):
    """Create an audit log entry for a biometric punch attempt."""
    try:
        bio_device = None
        if employee:
            bio_device = frappe.db.get_value(
                "Employee Biometric",
                {"parent": employee, "template_id": employee_id_sent},
                "biometric_device",
            )

        log = frappe.get_doc({
            "doctype": "Biometric Punch Log",
            "timestamp": timestamp,
            "status": status,
            "employee": employee,
            "biometric_device": bio_device,
            "device_id": device_id,
            "log_type": log_type,
            "employee_id_sent": employee_id_sent,
            "ip_address": ip_address,
            "secret_valid": 1 if secret_valid else 0,
            "error_message": error_message,
        })
        log.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception:
        pass
