import frappe
from frappe import _

from pwa_app.api.utils import get_employee as _get_employee, HR_ROLES


@frappe.whitelist()
def create_advance(amount, purpose=None, repayment_months=1):
    user = frappe.session.user
    employee = _get_employee(user)
    if not employee:
        frappe.throw(_("No employee record found for this user"))

    advance = frappe.get_doc({
        "doctype": "Employee Advance",
        "employee": employee,
        "amount": float(amount),
        "purpose": purpose or "",
        "repayment_months": int(repayment_months),
    })
    advance.insert()
    return {"name": advance.name, "status": advance.status, "amount": float(amount)}


@frappe.whitelist()
def get_advances():
    user = frappe.session.user
    employee = _get_employee(user)
    if not employee:
        return []

    advances = frappe.get_all(
        "Employee Advance",
        filters={"employee": employee, "docstatus": ["!=", 2]},
        fields=["name", "amount", "purpose", "status", "creation"],
        order_by="creation desc",
        limit=20,
    )
    return advances
