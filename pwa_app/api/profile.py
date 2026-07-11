import frappe
from frappe import _
from pwa_app.api.utils import get_employee as _get_employee


@frappe.whitelist()
def get_profile():
    user = frappe.session.user
    employee = _get_employee(user)

    profile = {
        "user": user,
        "full_name": frappe.db.get_value("User", user, "full_name") or user,
        "roles": frappe.get_roles(),
    }

    if employee:
        emp_data = frappe.db.get_value(
            "Employee",
            employee,
            [
                "employee_name", "designation", "department", "cell_number",
                "personal_email", "company_email", "image", "date_of_joining",
                "employment_type", "branch", "employee_number",
            ],
            as_dict=True,
        )
        if emp_data:
            profile["employee"] = {
                k: str(v) if v else None
                for k, v in emp_data.items()
            }
            profile["employee"]["name"] = employee

    return profile


@frappe.whitelist()
def get_bank_details():
    user = frappe.session.user
    employee = _get_employee(user)
    if not employee:
        return {}

    details = frappe.db.get_value(
        "Employee",
        employee,
        ["bank_name", "bank_ac_no", "ifsc_code", "branch"],
        as_dict=True,
    )
    return {
        "bank_name": details.bank_name or "" if details else "",
        "bank_ac_no": details.bank_ac_no or "" if details else "",
        "ifsc_code": details.ifsc_code or "" if details else "",
        "branch": details.branch or "" if details else "",
    }


@frappe.whitelist(methods=["POST"])
def update_bank_details(bank_name=None, bank_ac_no=None, ifsc_code=None, branch=None):
    user = frappe.session.user
    employee = _get_employee(user)
    if not employee:
        frappe.throw(_("No employee record found"))

    updates = {}
    if bank_name is not None: updates["bank_name"] = bank_name
    if bank_ac_no is not None: updates["bank_ac_no"] = bank_ac_no
    if ifsc_code is not None: updates["ifsc_code"] = ifsc_code
    if branch is not None: updates["branch"] = branch

    if updates:
        frappe.db.set_value("Employee", employee, updates)
    return {"success": True}


@frappe.whitelist(methods=["POST"])
def change_password(old_password, new_password):
    from frappe.core.doctype.user.user import change_password as _change_password
    try:
        _change_password(frappe.session.user, old_password, new_password)
        return {"success": True}
    except Exception as e:
        frappe.throw(str(e))
