import frappe
from frappe.model.document import Document
from frappe.utils import get_timedelta


class ShiftType(Document):
    def validate(self):
        self.validate_timings()
        self.validate_grace_periods()

    def validate_timings(self):
        if self.start_time and self.end_time:
            if self.start_time >= self.end_time:
                frappe.throw("Start Time must be before End Time")

    def validate_grace_periods(self):
        if self.late_entry_grace_period < 0:
            frappe.throw("Grace period cannot be negative")
        if self.early_exit_grace_period < 0:
            frappe.throw("Grace period cannot be negative")
