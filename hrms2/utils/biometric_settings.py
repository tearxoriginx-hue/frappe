import frappe
from frappe.utils import get_url
import secrets


def on_hr_settings_validate(doc, method):
    """Auto-generate biometric secret key and populate URL fields."""
    if not doc.get("biometric_secret_key"):
        doc.biometric_secret_key = "bio_" + secrets.token_hex(16)

    base_url = get_url()
    doc.biometric_endpoint_url = (
        base_url + "/api/method/hrms2.api.biometric_punch.handle_punch"
    )
    doc.biometric_short_url = base_url + "/biopunch_att"
