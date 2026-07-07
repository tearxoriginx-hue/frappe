import frappe
from frappe import _
from frappe.utils import nowdate, now_datetime, add_days


@frappe.whitelist()
def create_replacement_dispatch(rma_name):
    doc = frappe.get_doc("RMA Request", rma_name)
    if not doc.replacement_serial_no:
        frappe.throw(_("Replacement serial not set on RMA {0}").format(rma_name))
    frappe.has_permission("RMA Request", "write", doc=doc, throw=True)
    new_serial = frappe.get_doc("Serial No", doc.replacement_serial_no)
    if new_serial.status not in ("Active", "In Store"):
        frappe.throw(_("Serial {0} is not available (status: {1})").format(
            doc.replacement_serial_no, new_serial.status
        ))
    warranty_days = doc.warranty_days or frappe.get_single("RMA Settings").default_warranty_days or 365
    new_serial.customer = doc.customer
    new_serial.branch = doc.branch
    new_serial.company = doc.company
    new_serial.warranty_expiry_date = add_days(nowdate(), warranty_days)
    new_serial.status = "Dispatched"
    new_serial.save(ignore_permissions=True)
    dispatch = frappe.get_doc({
        "doctype": "Dispatch Entry",
        "customer": doc.customer,
        "branch": doc.branch,
        "company": doc.company,
        "posting_date": nowdate(),
        "products": [{
            "item_code": doc.item_code,
            "qty": 1,
            "serial_nos": doc.replacement_serial_no,
        }]
    })
    dispatch.insert(ignore_permissions=True)
    dispatch.submit()
    doc.replacement_dispatch_entry = dispatch.name
    doc.status = "Replaced"
    doc.completed_date = now_datetime()
    doc.save(ignore_permissions=True)
    return dispatch.name
