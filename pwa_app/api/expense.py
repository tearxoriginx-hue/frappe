import frappe
import base64
from frappe import _
from frappe.utils.file_manager import save_file

from pwa_app.api.utils import get_employee as _get_employee


@frappe.whitelist()
def create_expense(expense_type, amount, expense_date, description=None, file_data=None, file_name=None):
    user = frappe.session.user
    employee = _get_employee(user)
    if not employee:
        frappe.throw(_("No employee record found for this user"))

    frappe.has_permission("Expense Claim", "create", throw=True)

    claim = frappe.get_doc({
        "doctype": "Expense Claim",
        "employee": employee,
        "posting_date": expense_date,
        "expenses": [{
            "expense_type": expense_type,
            "expense_date": expense_date,
            "amount": float(amount),
            "description": description or "",
        }],
    })
    claim.insert(ignore_permissions=True)

    if file_data and file_name:
        try:
            content = base64.b64decode(file_data.split(",")[-1])
            save_file(
                fname=file_name,
                content=content,
                dt="Expense Claim",
                dn=claim.name,
                is_private=1,
            )
        except Exception as e:
            frappe.log_error(f"Expense file upload failed: {e}")

    frappe.db.commit()
    return {"name": claim.name, "status": claim.status}
