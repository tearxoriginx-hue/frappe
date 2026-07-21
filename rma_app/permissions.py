import frappe


def rma_request_query(user):
    """Permission query for RMA Request list view.

    - RMA Manager / System Manager: see all records
    - RMA Staff: see only records for their own branch
    - Others: see nothing (1=0)
    """
    if "RMA Manager" in frappe.get_roles(user) or "System Manager" in frappe.get_roles(user):
        return ""

    employee = frappe.db.get_value(
        "Employee",
        {"user_id": user},
        "branch",
    )
    if employee:
        return f"`tabRMA Request`.branch = {frappe.db.escape(employee)}"

    return "1=0"


def rma_request_has_permission(doc, ptype, user):
    """Check if user has permission for a specific RMA Request document.

    - RMA Manager / System Manager: full access
    - RMA Staff: can create/submit, or read/write own branch records
    """
    if "RMA Manager" in frappe.get_roles(user) or "System Manager" in frappe.get_roles(user):
        return True

    if "RMA Staff" in frappe.get_roles(user):
        if ptype in ("create", "submit"):
            return True

        employee = frappe.db.get_value(
            "Employee",
            {"user_id": user},
            "branch",
        )
        if employee and doc.branch == employee:
            return True

    return False
