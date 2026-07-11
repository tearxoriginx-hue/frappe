from frappe.model.document import Document
import frappe
from frappe.utils import now_datetime


class BiometricDevice(Document):
    """Master record for a biometric device installed at a branch."""

    def validate(self):
        if not self.setup_instructions_html:
            self.setup_instructions_html = """
<h4>Device Setup Guide</h4>
<ol>
  <li><strong>Connect the device</strong> to your local network and note its IP address.</li>
  <li><strong>Enroll employees</strong> on the biometric device (fingerprint/face/card). Each employee will have a Template/User ID on the device.</li>
  <li><strong>Enter the device IP</strong> in the fields above and ensure the device is reachable from this server.</li>
  <li><strong>Add employee mappings</strong> below — for each employee, enter their Template ID from the device and select this device.</li>
  <li><strong>Test the connection</strong> using the "Test Connection" button above to verify the device is reachable.</li>
  <li><strong>Auto-sync</strong> will run hourly. You can also trigger a manual sync from the server console.</li>
</ol>
<h4>Two Integration Modes</h4>
<p><strong>Push Mode (recommended for cloud)</strong> — Configure your middleware to POST punches to the Endpoint URL from HR Settings &gt; Biometric Settings. The device IP is not needed for push mode.</p>
<p><strong>Pull Mode (ZKTeco protocol)</strong> — The server connects to the device on port 4370 and pulls logs. Requires device IP and communication password. Used by the hourly sync job.</p>
"""

    def on_update(self):
        """Clear cache when device is updated."""
        frappe.cache().delete_key(f"biometric_device:{self.name}")

    def mark_synced(self):
        """Update last sync time to now."""
        self.db_set("last_sync_time", now_datetime())


@frappe.whitelist()
def test_connection(device_name):
    """Test connection to a biometric device and return result."""
    from core_app.utils.biometric_sync import test_device_connection

    result = test_device_connection(device_name)

    device = frappe.get_doc("Biometric Device", device_name)
    device.db_set("last_test_result", str(result))

    return result
