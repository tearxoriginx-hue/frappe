import frappe

def after_install():
    create_roles()

def create_roles():
    if not frappe.db.exists("Role", "RMA Staff"):
        frappe.get_doc({
            "doctype": "Role",
            "role_name": "RMA Staff",
            "desk_access": 1,
        }).insert(ignore_permissions=True)
    if not frappe.db.exists("Role", "RMA Manager"):
        frappe.get_doc({
            "doctype": "Role",
            "role_name": "RMA Manager",
            "desk_access": 1,
        }).insert(ignore_permissions=True)
