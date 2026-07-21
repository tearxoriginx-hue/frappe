import frappe
from frappe.model.document import Document
from frappe.model.naming import set_name_by_naming_series


class Employee(Document):
    def validate(self):
        self.set_employee_name()
        self.validate_date()

    def set_employee_name(self):
        self.employee_name = " ".join(filter(None, [self.first_name, self.last_name]))

    def validate_date(self):
        if self.date_of_birth and self.date_of_joining:
            if self.date_of_birth > self.date_of_joining:
                frappe.throw("Date of Birth cannot be after Date of Joining")

    def after_insert(self):
        self.create_user_permission()

    def on_update(self):
        self.update_branch_user_permission()

    def create_user_permission(self):
        if self.user_id:
            if not frappe.db.get_value("User Permission", {
                "user": self.user_id,
                "allow": "Employee",
                "for_value": self.name
            }):
                perm = frappe.get_doc({
                    "doctype": "User Permission",
                    "user": self.user_id,
                    "allow": "Employee",
                    "for_value": self.name,
                })
                perm.insert(ignore_permissions=True)

            if self.branch and not frappe.db.get_value("User Permission", {
                "user": self.user_id,
                "allow": "Branch",
                "for_value": self.branch
            }):
                perm = frappe.get_doc({
                    "doctype": "User Permission",
                    "user": self.user_id,
                    "allow": "Branch",
                    "for_value": self.branch,
                    "apply_to_all_doctypes": 1,
                })
                perm.insert(ignore_permissions=True)

    def update_branch_user_permission(self):
        """Update Branch User Permission if branch changed."""
        if not self.user_id:
            return

        # Get existing Branch permission
        existing = frappe.db.get_value("User Permission", {
            "user": self.user_id,
            "allow": "Branch"
        }, "for_value")

        if self.branch:
            if existing and existing != self.branch:
                # Branch changed - update existing
                frappe.db.set_value("User Permission", {
                    "user": self.user_id,
                    "allow": "Branch",
                    "for_value": existing
                }, "for_value", self.branch)
            elif not existing:
                # No permission exists - create new
                perm = frappe.get_doc({
                    "doctype": "User Permission",
                    "user": self.user_id,
                    "allow": "Branch",
                    "for_value": self.branch,
                    "apply_to_all_doctypes": 1,
                })
                perm.insert(ignore_permissions=True)
        elif existing:
            # Branch removed - delete permission
            frappe.db.delete("User Permission", {
                "user": self.user_id,
                "allow": "Branch",
                "for_value": existing
            })


def get_employee_by_user(user):
    """Get employee record linked to a Frappe user."""
    emp = frappe.db.get_value("Employee", {"user_id": user}, ["name", "employee_name", "status"], as_dict=True)
    return emp
