import frappe
from frappe import _
from frappe.utils import now_datetime

no_cache = 1


def get_context(context):
    """Handle GET request — show status page."""
    if frappe.request.method == "POST":
        return _handle_post()

    context.title = "Biometric Punch Endpoint"
    context.is_active = frappe.db.get_single_value("HR Settings", "enable_biometric_api")
    context.secret_configured = bool(
        frappe.db.get_single_value("HR Settings", "biometric_secret_key")
    )
    context.endpoint_url = frappe.utils.get_url() + "/biopunch_att"
    context.api_url = (
        frappe.utils.get_url()
        + "/api/method/hrms2.api.biometric_punch.handle_punch"
    )
    return context


def _handle_post():
    """Handle POST — process biometric punch."""
    data = frappe.local.form_dict

    secret = data.get("secret")
    employee_id = data.get("employee_id")
    log_type = data.get("log_type", "IN")
    timestamp = data.get("timestamp")
    device_id = data.get("device_id")

    try:
        frappe.call(
            "hrms2.api.biometric_punch.handle_punch",
            secret=secret,
            employee_id=employee_id,
            log_type=log_type,
            timestamp=timestamp,
            device_id=device_id,
        )
        frappe.local.response["content_type"] = "application/json"
        frappe.response["message"] = {
            "status": "success",
            "employee": employee_id,
            "time": str(timestamp or now_datetime()),
        }
    except frappe.ValidationError as e:
        frappe.local.response["content_type"] = "application/json"
        frappe.response["message"] = {"status": "error", "error": str(e)}
        frappe.response["http_status_code"] = 400
    except Exception as e:
        frappe.local.response["content_type"] = "application/json"
        frappe.response["message"] = {"status": "error", "error": str(e)}
        frappe.response["http_status_code"] = 500
