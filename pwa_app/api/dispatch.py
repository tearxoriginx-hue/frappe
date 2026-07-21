import frappe
import json
from frappe import _

@frappe.whitelist()
def create_dispatch_entry(customer, invoice_no=None, branch=None, products=None):
    frappe.has_permission("Dispatch Entry", "create", throw=True)
    
    if not products:
        frappe.throw(_("At least one product is required"))
        
    if isinstance(products, str):
        products = json.loads(products)
        
    doc = frappe.get_doc({
        "doctype": "Dispatch Entry",
        "customer": customer,
        "invoice_no": invoice_no,
        "branch": branch,
        "products": []
    })
    
    for p in products:
        doc.append("products", {
            "item_code": p.get("item_code"),
            "serial_nos": p.get("serial_nos")
        })
        
    doc.insert()
    doc.submit()
    return {"name": doc.name, "status": doc.processing_status}
