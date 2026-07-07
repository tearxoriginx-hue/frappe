import frappe
from frappe.utils import now_datetime, get_datetime
import logging

logger = logging.getLogger(__name__)

try:
    from zk import ZK
    from zk.exception import ZKConnectionError, ZKErrorResponse
    ZK_AVAILABLE = True
except ImportError:
    ZK_AVAILABLE = False


def sync_all_devices():
    """Scheduled task: sync all active biometric devices."""
    devices = frappe.get_all("Biometric Device", {"is_active": 1},
        ["name", "device_ip", "device_port", "device_type", "branch",
         "device_password", "last_sync_time"])
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
    """Sync a single biometric device via ZKTeco protocol."""
    ip = device.get("device_ip")
    port = int(device.get("device_port") or 4370)
    password = device.get("device_password") or ""
    device_name = device["name"]

    if not ip:
        return {"device": device_name, "status": "skipped", "reason": "No IP configured"}
    if not ZK_AVAILABLE:
        return {"device": device_name, "status": "skipped", "reason": "pyzk SDK not installed"}

    mappings = frappe.db.get_all("Employee Biometric", {"biometric_device": device_name},
        ["parent as employee", "template_id"])
    template_map = {m["template_id"]: m["employee"] for m in mappings if m.get("template_id")}
    if not template_map:
        return {"device": device_name, "status": "skipped", "reason": "No employee mappings"}

    conn = None
    try:
        zk = ZK(ip, port=port, timeout=10, password=password or None)
        conn = zk.connect()
        if not conn:
            return {"device": device_name, "status": "error", "error": "Could not connect"}
        conn.disable_device()
        raw_attendances = conn.get_attendance()
        last_sync = device.get("last_sync_time")
        last_sync_dt = get_datetime(last_sync) if last_sync else None

        synced = errors = skipped = 0
        for att in raw_attendances:
            try:
                uid = str(att.user_id)
                timestamp = att.timestamp
                if last_sync_dt and timestamp <= last_sync_dt:
                    skipped += 1
                    continue
                employee = template_map.get(uid)
                if not employee:
                    errors += 1
                    continue
                log_type = "IN" if att.status in (0, 2) else "OUT" if att.status in (1, 3) else ("IN" if att.timestamp.hour < 12 else "OUT")
                if frappe.db.exists("Employee Checkin", {"employee": employee, "time": timestamp, "log_type": log_type}):
                    skipped += 1
                    continue
                checkin = frappe.get_doc({"doctype": "Employee Checkin", "employee": employee,
                    "log_type": log_type, "time": str(timestamp), "device_id": f"Biometric-{device_name}"})
                checkin.insert(ignore_permissions=True)
                synced += 1
            except Exception:
                errors += 1
        conn.enable_device()
        frappe.db.commit()
        frappe.db.set_value("Biometric Device", device_name, "last_sync_time", now_datetime())
        return {"device": device_name, "status": "success", "synced": synced, "skipped": skipped, "errors": errors}
    except Exception as e:
        return {"device": device_name, "status": "error", "error": str(e)}
    finally:
        if conn:
            try: conn.disconnect()
            except: pass


@frappe.whitelist(allow_guest=False)
def test_device_connection(device_name: str):
    """Test connection to a biometric device."""
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
        return {"status": "success", "device_name": device.name,
                "firmware": conn.get_firmware(), "serial": conn.get_serialnumber(),
                "user_count": len(conn.get_users()), "attendance_count": len(conn.get_attendance())}
    except Exception as e:
        return {"status": "error", "error": str(e)}
    finally:
        if conn:
            try: conn.disconnect()
            except: pass
