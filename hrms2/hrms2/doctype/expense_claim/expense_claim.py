import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate

class ExpenseClaim(Document):
    def validate(self):
        self.calculate_totals()

    def on_submit(self):
        if self.status == "Draft":
            self.db_set("status", "Submitted")

    def before_submit(self):
        if not self.expenses:
            frappe.throw(_("Please add at least one expense"))

    def calculate_totals(self):
        total = 0
        if self.expenses:
            for exp in self.expenses:
                total += flt(exp.amount or 0)
        self.total_claimed_amount = total
        self.total_sanctioned_amount = total

    def on_cancel(self):
        self.db_set("status", "Cancelled")


@frappe.whitelist()
def approve_expense_claim(docname):
    user_roles = frappe.get_roles(frappe.session.user)
    if "HR Manager" not in user_roles and "System Manager" not in user_roles:
        frappe.throw(_("Only HR Manager can approve expense claims"))
    doc = frappe.get_doc("Expense Claim", docname)
    if doc.status != "Submitted":
        frappe.throw(_("Claim must be in Submitted status to approve"))
    doc.db_set({"status": "Approved", "approved_by": frappe.session.user, "approval_date": nowdate()})
    return doc.status


@frappe.whitelist()
def reject_expense_claim(docname, reason=None):
    user_roles = frappe.get_roles(frappe.session.user)
    if "HR Manager" not in user_roles and "System Manager" not in user_roles:
        frappe.throw(_("Only HR Manager can reject expense claims"))
    doc = frappe.get_doc("Expense Claim", docname)
    doc.db_set({"status": "Rejected", "rejection_reason": reason or "No reason provided"})
    return doc.status
