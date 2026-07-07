import frappe
from frappe import _


@frappe.whitelist(allow_guest=False)
def biometric_checkin(employee=None, device=None, template_id=None, log_type="IN"):
    """Record a biometric check-in."""
    if not employee and (not device or not template_id):
        frappe.throw(_("Either employee or (device + template_id) is required"))
    if not employee and device and template_id:
        mapping = frappe.db.get_value("Employee Biometric",
            {"biometric_device": device, "template_id": template_id}, "parent")
        if not mapping:
            frappe.throw(_("No employee found matching this device and template"))
        employee = mapping
    emp = frappe.db.get_value("Employee", employee, ["name", "status"], as_dict=True)
    if not emp or emp.status != "Active":
        frappe.throw(_("Employee not found or not active"))
    checkin = frappe.get_doc({"doctype": "Employee Checkin", "employee": employee,
        "log_type": log_type, "time": frappe.utils.now_datetime(), "device_id": f"Biometric-{device}"})
    checkin.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "success", "message": _(f"Check-{log_type.lower()} recorded"),
            "time": str(frappe.utils.now_datetime()), "employee": employee, "log_name": checkin.name}


@frappe.whitelist(allow_guest=False)
def get_employees_for_device(device=None, branch=None):
    """Get employees registered for a biometric device."""
    filters = {}
    if device: filters["biometric_device"] = device
    if branch:
        employees = frappe.db.get_all("Employee", {"branch": branch}, pluck="name")
        if not employees: return []
        filters["parent"] = ("in", employees)
    return frappe.db.get_all("Employee Biometric", filters or {},
        ["parent as employee", "biometric_device", "template_id"])


@frappe.whitelist(allow_guest=False)
def sync_biometric_logs(device: str, logs: list):
    """Bulk sync biometric logs from a device."""
    if not logs:
        return {"status": "error", "message": _("No logs provided")}
    device_doc = frappe.get_doc("Biometric Device", device)
    success = errors = 0
    for log in logs:
        try:
            mapping = frappe.db.get_value("Employee Biometric",
                {"biometric_device": device, "template_id": log.get("template_id")}, "parent")
            if not mapping: errors += 1; continue
            checkin = frappe.get_doc({"doctype": "Employee Checkin", "employee": mapping,
                "log_type": log.get("log_type", "IN"), "time": log.get("timestamp", frappe.utils.now_datetime()),
                "device_id": f"Biometric-{device}"})
            checkin.insert(ignore_permissions=True)
            success += 1
        except Exception: errors += 1
    frappe.db.commit()
    device_doc.db_set("last_sync_time", frappe.utils.now_datetime())
    return {"status": "success", "synced": success, "errors": errors}
