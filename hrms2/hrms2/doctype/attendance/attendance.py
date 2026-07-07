import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class Attendance(Document):
    def validate(self):
        self.validate_duplicate()
        self.validate_dates()

    def validate_duplicate(self):
        existing = frappe.db.get_value("Attendance", {
            "employee": self.employee,
            "attendance_date": self.attendance_date,
            "docstatus": 1,
            "name": ("!=", self.name)
        })
        if existing:
            frappe.throw(f"Attendance already exists for {self.employee} on {self.attendance_date}")

    def validate_dates(self):
        if self.attendance_date and getdate(self.attendance_date) > getdate():
            frappe.throw("Attendance cannot be marked for a future date")
