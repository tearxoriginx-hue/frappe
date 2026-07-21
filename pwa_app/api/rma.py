import frappe
from frappe import _

@frappe.whitelist()
def create_rma_request(serial_no, rma_type, repair_notes=None):
    frappe.has_permission("RMA Request", "create", throw=True)
    
    # Validation helper auto-populates all detail fields on the backend
    doc = frappe.get_doc({
        "doctype": "RMA Request",
        "serial_no": serial_no,
        "rma_type": rma_type,
        "repair_notes": repair_notes
    })
    
    doc.insert(ignore_permissions=True)
    return {"name": doc.name, "status": doc.status}
