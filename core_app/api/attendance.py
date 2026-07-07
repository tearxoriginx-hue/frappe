import frappe
from frappe import _
from frappe.utils import now_datetime, getdate


@frappe.whitelist(allow_guest=False)
def biometric_checkin(employee: str = None, device: str = None, template_id: str = None, log_type: str = "IN"):
    """
    Record a biometric check-in for an employee.
    
    Args:
        employee: Employee name (optional, will use template_id + device if not provided)
        device: Biometric Device name
        template_id: Fingerprint/face template ID
        log_type: "IN" or "OUT"
    
    Returns:
        dict with status and message
    """
    if not employee and (not device or not template_id):
        frappe.throw(_("Either employee or (device + template_id) is required"))
    
    # Find employee by device + template if not specified
    if not employee and device and template_id:
        mapping = frappe.db.get_value(
            "Employee Biometric",
            {"biometric_device": device, "template_id": template_id},
            "parent"
        )
        if not mapping:
            frappe.throw(_("No employee found matching this device and template"))
        employee = mapping
    
    # Verify employee exists and is active
    emp = frappe.db.get_value("Employee", employee, ["name", "status", "user_id", "attendance_type"], as_dict=True)
    if not emp:
        frappe.throw(_("Employee not found"))
    if emp.status != "Active":
        frappe.throw(_("Employee is not active"))
    
    # Get the employee's user_id for creating the checkin log
    user_id = emp.user_id or employee
    
    # Record in Employee Checkin (hrms standard)
    checkin = frappe.get_doc({
        "doctype": "Employee Checkin",
        "employee": employee,
        "log_type": log_type,
        "time": now_datetime(),
        "device_id": f"Biometric-{device}",
    })
    checkin.insert(ignore_permissions=True)
    frappe.db.commit()
    
    return {
        "status": "success",
        "message": _("Check-{0} recorded").format(log_type.lower()),
        "time": str(now_datetime()),
        "employee": employee,
        "log_name": checkin.name
    }


@frappe.whitelist(allow_guest=False)
def get_employees_for_device(device: str = None, branch: str = None):
    """
    Get list of employees registered for a biometric device.
    Used by device sync scripts.
    """
    filters = {}
    if device:
        filters["biometric_device"] = device
    if branch:
        # Get employees under this branch
        employees = frappe.db.get_all("Employee", {"branch": branch}, pluck="name")
        if not employees:
            return []
        return frappe.db.get_all(
            "Employee Biometric",
            {"parent": ("in", employees), **filters},
            ["parent as employee", "biometric_device", "template_id"]
        )
    
    return frappe.db.get_all(
        "Employee Biometric",
        filters or {},
        ["parent as employee", "biometric_device", "template_id"]
    )


@frappe.whitelist(allow_guest=False)
def sync_biometric_logs(device: str, logs: list):
    """
    Bulk sync biometric logs from a device.
    
    Args:
        device: Biometric Device name
        logs: List of dicts with {template_id, log_type, timestamp}
    """
    if not logs:
        return {"status": "error", "message": _("No logs provided")}
    
    device_doc = frappe.get_doc("Biometric Device", device)
    success = 0
    errors = 0
    
    for log in logs:
        try:
            # Find employee by template_id on this device
            mapping = frappe.db.get_value(
                "Employee Biometric",
                {"biometric_device": device, "template_id": log.get("template_id")},
                "parent"
            )
            if not mapping:
                errors += 1
                continue
            
            checkin = frappe.get_doc({
                "doctype": "Employee Checkin",
                "employee": mapping,
                "log_type": log.get("log_type", "IN"),
                "time": log.get("timestamp", now_datetime()),
                "device_id": f"Biometric-{device}",
            })
            checkin.insert(ignore_permissions=True)
            success += 1
            
        except Exception:
            errors += 1
    
    frappe.db.commit()
    
    # Mark device as synced
    device_doc.db_set("last_sync_time", now_datetime())
    
    return {
        "status": "success",
        "synced": success,
        "errors": errors
    }
