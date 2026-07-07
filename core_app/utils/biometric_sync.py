import frappe
from frappe.utils import now_datetime, get_datetime
import logging

logger = logging.getLogger(__name__)

# Optional: ZKTeco pyzk integration
try:
    from zk import ZK
    from zk.exception import ZKConnectionError, ZKErrorResponse
    ZK_AVAILABLE = True
except ImportError:
    ZK_AVAILABLE = False


def sync_all_devices():
    """
    Scheduled task to sync all active biometric devices.
    Called from scheduler_events in hooks.py (hourly).
    """
    devices = frappe.get_all(
        "Biometric Device",
        {"is_active": 1},
        ["name", "device_ip", "device_port", "device_type", "branch",
         "device_password", "last_sync_time"]
    )

    results = []
    for device in devices:
        try:
            result = sync_device(device)
            results.append(result)
        except Exception as e:
            logger.error(f"Biometric sync failed for {device.name}: {str(e)}")
            results.append({"device": device.name, "status": "error", "error": str(e)})

    return results


def sync_device(device: dict):
    """
    Sync a single biometric device.
    Connects via ZKTeco SDK (pyzk) to fetch attendance logs.

    Args:
        device: dict with name, device_ip, device_port, device_type, branch
    """
    device_name = device.get("name")
    ip = device.get("device_ip")
    port = int(device.get("device_port") or 4370)
    password = device.get("device_password") or ""

    if not ip:
        return {"device": device_name, "status": "skipped", "reason": "No IP configured"}

    # Fetch existing employees mapped to this device for template matching
    mappings = frappe.db.get_all(
        "Employee Biometric",
        {"biometric_device": device_name},
        ["parent as employee", "template_id"]
    )
    template_map = {m["template_id"]: m["employee"] for m in mappings if m.get("template_id")}

    if not template_map:
        return {"device": device_name, "status": "skipped", "reason": "No employee mappings configured"}

    if not ZK_AVAILABLE:
        return {"device": device_name, "status": "skipped", "reason": "pyzk SDK not installed. Run: env/bin/pip install pyzk"}

    conn = None
    try:
        # Connect to device via ZKTeco protocol on port 4370
        zk = ZK(ip, port=port, timeout=10, password=password if password else None)
        conn = zk.connect()

        if not conn:
            return {"device": device_name, "status": "error", "error": "Could not connect to device"}

        # Disable device to prevent user interaction during sync
        conn.disable_device()

        # Fetch attendance logs from device
        raw_attendances = conn.get_attendance()
        logs_count = len(raw_attendances)

        # Get last sync time to only fetch new entries
        last_sync = device.get("last_sync_time")
        if last_sync:
            last_sync_dt = get_datetime(last_sync)
        else:
            last_sync_dt = None

        # Process logs
        synced = 0
        errors = 0
        skipped = 0

        for att in raw_attendances:
            try:
                uid = str(att.user_id)
                timestamp = att.timestamp

                # Skip older logs if we have a last sync time
                if last_sync_dt and timestamp <= last_sync_dt:
                    skipped += 1
                    continue

                # Find employee by template_id (using uid from device)
                employee = template_map.get(uid)
                if not employee:
                    errors += 1
                    continue

                # Determine IN/OUT based on transaction
                # ZKTeco typically returns 0 for IN, 1 for OUT, or 15 for unknown
                log_type = determine_log_type(att)
                if not log_type:
                    skipped += 1
                    continue

                # Check if this log already exists (avoid duplicates)
                existing = frappe.db.exists("Employee Checkin", {
                    "employee": employee,
                    "time": timestamp,
                    "log_type": log_type,
                })
                if existing:
                    skipped += 1
                    continue

                # Create Employee Checkin record
                checkin = frappe.get_doc({
                    "doctype": "Employee Checkin",
                    "employee": employee,
                    "log_type": log_type,
                    "time": str(timestamp),
                    "device_id": f"Biometric-{device_name}",
                })
                checkin.insert(ignore_permissions=True)
                synced += 1

            except Exception:
                errors += 1

        # Re-enable device
        conn.enable_device()

        # Commit all new checkins
        frappe.db.commit()

        # Mark device as synced
        frappe.db.set_value("Biometric Device", device_name, "last_sync_time", now_datetime())

        return {
            "device": device_name,
            "status": "success",
            "total_logs": logs_count,
            "synced": synced,
            "skipped": skipped,
            "errors": errors,
        }

    except ZKConnectionError as e:
        return {"device": device_name, "status": "error", "error": f"Connection failed: {str(e)}"}
    except ZKErrorResponse as e:
        return {"device": device_name, "status": "error", "error": f"Device error: {str(e)}"}
    except Exception as e:
        return {"device": device_name, "status": "error", "error": str(e)}
    finally:
        if conn:
            try:
                conn.disconnect()
            except Exception:
                pass


def determine_log_type(attendance_entry) -> str | None:
    """
    Determine if a ZKTeco attendance entry is IN or OUT.
    ZKTeco status codes: 0=CheckIn, 1=CheckOut, 2=OvertimeIn, 3=OvertimeOut, 15=Unknown
    """
    status = attendance_entry.status
    if status in (0, 2):
        return "IN"
    elif status in (1, 3):
        return "OUT"
    else:
        # Try to figure out based on time - if morning, assume IN; if evening, assume OUT
        try:
            hour = attendance_entry.timestamp.hour
            if hour < 12:
                return "IN"
            else:
                return "OUT"
        except Exception:
            return None


def test_device_connection(device_name: str) -> dict:
    """
    Test connection to a biometric device.
    Returns device info if successful.
    """
    device = frappe.get_doc("Biometric Device", device_name)
    if not device.device_ip:
        return {"status": "error", "error": "No IP configured"}

    if not ZK_AVAILABLE:
        return {"status": "error", "error": "pyzk SDK not installed"}

    conn = None
    try:
        zk = ZK(device.device_ip, port=int(device.device_port or 4370),
                timeout=10, password=device.device_password or None)
        conn = zk.connect()

        if not conn:
            return {"status": "error", "error": "Could not connect"}

        info = {
            "status": "success",
            "device_name": device.name,
            "firmware": conn.get_firmware(),
            "serial": conn.get_serialnumber(),
            "platform": conn.get_platform(),
            "device_name_model": conn.get_device_name(),
            "face_capacity": conn.get_face_cap(),
            "user_count": len(conn.get_users()),
            "attendance_count": len(conn.get_attendance()),
        }
        return info

    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        if conn:
            try:
                conn.disconnect()
            except Exception:
                pass


@frappe.whitelist(allow_guest=False)
def push_employees_to_device(device_name: str):
    """
    Push all mapped employees to a biometric device.
    This ensures the device knows which templates/users to expect.
    """
    if not ZK_AVAILABLE:
        frappe.throw("pyzk SDK not installed. Run: env/bin/pip install pyzk")

    device = frappe.get_doc("Biometric Device", device_name)
    if not device.device_ip:
        frappe.throw("Device has no IP configured")

    mappings = frappe.db.get_all(
        "Employee Biometric",
        {"biometric_device": device_name},
        ["parent as employee", "template_id", "name"]
    )

    if not mappings:
        return {"status": "error", "message": "No employee mappings found for this device"}

    conn = None
    try:
        zk = ZK(device.device_ip, port=int(device.device_port or 4370),
                timeout=15, password=device.device_password or None)
        conn = zk.connect()
        conn.disable_device()

        pushed = 0
        errors = 0

        # Get existing users on device
        existing_users = {str(u.uid): u for u in conn.get_users()}

        for mapping in mappings:
            try:
                uid = mapping.get("template_id")
                if not uid:
                    errors += 1
                    continue

                # Get employee details
                emp = frappe.db.get_value("Employee", mapping["employee"],
                                          ["employee_name", "employee_number"], as_dict=True)
                if not emp:
                    errors += 1
                    continue

                name = emp.employee_name or mapping["employee"]
                # Pyzk uses user_id, name, privilege, password
                conn.set_user(
                    uid=uid,
                    name=name[:24],  # ZKTeco name limit
                    privilege=0,  # 0=User, 14=Admin
                    password=""
                )
                pushed += 1

            except Exception:
                errors += 1

        conn.enable_device()
        return {"status": "success", "pushed": pushed, "errors": errors}

    except Exception as e:
        frappe.throw(f"Failed to push employees: {str(e)}")
    finally:
        if conn:
            try:
                conn.disconnect()
            except Exception:
                pass


def get_active_devices_for_branch(branch: str = None):
    """Get active biometric devices, optionally filtered by branch."""
    filters = {"is_active": 1}
    if branch:
        filters["branch"] = branch
    return frappe.get_all("Biometric Device", filters, ["name", "device_type", "branch", "device_ip"])


def get_employee_device_mapping(employee: str = None):
    """Get biometric device mappings for an employee."""
    filters = {}
    if employee:
        filters["parent"] = employee
    return frappe.db.get_all(
        "Employee Biometric",
        filters,
        ["parent as employee", "biometric_device", "template_id", "is_primary"]
    )
