import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class BiometricDevice(Document):
    def on_update(self):
        frappe.cache().delete_key(f"biometric_device:{self.name}")

    def mark_synced(self):
        self.db_set("last_sync_time", now_datetime())
