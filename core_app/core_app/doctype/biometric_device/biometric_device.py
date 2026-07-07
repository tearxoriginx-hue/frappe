from frappe.model.document import Document
import frappe
from frappe.utils import now_datetime


class BiometricDevice(Document):
    """Master record for a biometric device installed at a branch."""

    def on_update(self):
        """Clear cache when device is updated."""
        frappe.cache().delete_key(f"biometric_device:{self.name}")

    def mark_synced(self):
        """Update last sync time to now."""
        self.db_set("last_sync_time", now_datetime())
