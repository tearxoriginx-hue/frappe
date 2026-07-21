import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class LeaveEncashment(Document):
    def validate(self):
        self.calculate_amounts()
        self.validate_leave_balance()

    def calculate_amounts(self):
        self.total_amount = flt(self.total_leaves_encashed or 0) * flt(self.encashment_per_leave or 0)
        self.payable_amount = self.total_amount

    def validate_leave_balance(self):
        if self.leave_type and self.employee:
            allocated = frappe.db.sql("""
                SELECT COALESCE(SUM(total_leaves_allocated), 0) as allocated,
                       COALESCE(SUM(total_leave_days), 0) as used
                FROM `tabLeave Allocation`
                WHERE employee = %s AND leave_type = %s AND docstatus = 1
            """, (self.employee, self.leave_type), as_dict=True)
            if allocated:
                balance = flt(allocated[0].allocated) - flt(allocated[0].used)
                if self.total_leaves_encashed > balance:
                    frappe.throw(_("Cannot encash more than available balance ({0} days)").format(balance))
