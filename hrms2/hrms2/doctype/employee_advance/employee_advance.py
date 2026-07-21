import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate


class EmployeeAdvance(Document):
    def validate(self):
        self.calculate_installment()
        self.calculate_outstanding()

    def on_submit(self):
        if self.status == "Draft":
            self.db_set("status", "Pending Approval")

    def on_update_after_submit(self):
        self.calculate_outstanding()

    def calculate_installment(self):
        if self.repayment_method == "Installment Plan" and self.installment_periods > 0:
            self.installment_amount = flt(self.amount) / self.installment_periods
        elif self.repayment_method == "Salary Deduction":
            self.installment_amount = self.amount
            self.installment_periods = 1
        else:
            self.installment_amount = self.amount
            self.installment_periods = 1

    def calculate_outstanding(self):
        self.outstanding_amount = flt(self.amount) - flt(self.repaid_amount or 0) - flt(self.paid_amount or 0)


@frappe.whitelist()
def approve_advance(docname):
    frappe.has_permission("Employee Advance", "write", throw=True)
    user_roles = frappe.get_roles(frappe.session.user)
    if "HR Manager" not in user_roles and "System Manager" not in user_roles:
        frappe.throw(_("Only HR Manager can approve advances"))
    doc = frappe.get_doc("Employee Advance", docname)
    if doc.status != "Pending Approval":
        frappe.throw(_("Advance is not in Pending Approval status"))
    doc.db_set({"status": "Approved", "approved_by": frappe.session.user, "approval_date": nowdate()})
    return doc.status


@frappe.whitelist()
def reject_advance(docname, reason=None):
    frappe.has_permission("Employee Advance", "write", throw=True)
    user_roles = frappe.get_roles(frappe.session.user)
    if "HR Manager" not in user_roles and "System Manager" not in user_roles:
        frappe.throw(_("Only HR Manager can reject advances"))
    doc = frappe.get_doc("Employee Advance", docname)
    doc.db_set({"status": "Rejected", "rejection_reason": reason or "No reason provided"})
    return doc.status
