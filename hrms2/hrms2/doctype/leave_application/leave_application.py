import frappe
from frappe.model.document import Document
from frappe.utils import date_diff, getdate


class LeaveApplication(Document):
    def validate(self):
        self.calculate_leave_days()
        self.validate_dates()

    def calculate_leave_days(self):
        if self.from_date and self.to_date:
            self.total_leave_days = date_diff(getdate(self.to_date), getdate(self.from_date)) + 1
            if self.half_day:
                self.total_leave_days = self.total_leave_days - 0.5

    def validate_dates(self):
        if self.from_date and self.to_date and getdate(self.from_date) > getdate(self.to_date):
            frappe.throw("From Date cannot be after To Date")

    def on_submit(self):
        if self.status == "Draft":
            self.status = "Applied"
            self.db_set("status", "Applied")
