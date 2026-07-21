import frappe
from frappe.model.document import Document


class PWASettings(Document):
    def generate_vapid_keys(self):
        from pwa_app.api.push_notification import generate_vapid_keys
        return generate_vapid_keys()
