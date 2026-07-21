import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate


class AttendanceRequest(Document):
    def validate(self):
        self.set_total_hours()

    def on_submit(self):
        if self.approval_status == "Draft":
            self.db_set("approval_status", "Pending")

    def on_update_after_submit(self):
        if self.approval_status == "Approved":
            self.apply_attendance()

    def set_total_hours(self):
        if self.in_time and self.out_time:
            from datetime import datetime, timedelta
            fmt = "%H:%M:%S"
            t1 = datetime.strptime(str(self.in_time), fmt)
            t2 = datetime.strptime(str(self.out_time), fmt)
            diff = (t2 - t1).seconds / 3600
            self.total_hours = round(diff, 1)

    def apply_attendance(self):
        existing = frappe.db.get_value("Attendance", {
            "employee": self.employee,
            "attendance_date": self.attendance_date,
            "docstatus": 1
        })
        if existing:
            att = frappe.get_doc("Attendance", existing)
            att.db_set("status", self.status)
        else:
            att = frappe.get_doc({
                "doctype": "Attendance",
                "employee": self.employee,
                "attendance_date": self.attendance_date,
                "status": self.status,
                "in_time": self.in_time,
                "out_time": self.out_time,
                "total_hours": self.total_hours
            })
            att.flags.ignore_permissions = True
            att.insert()


@frappe.whitelist()
def approve_attendance_request(docname):
    user_roles = frappe.get_roles(frappe.session.user)
    if "HR Manager" not in user_roles and "System Manager" not in user_roles:
        frappe.throw(_("Only HR Manager can approve attendance requests"))
    doc = frappe.get_doc("Attendance Request", docname)
    if doc.approval_status != "Pending":
        frappe.throw(_("Request is not in Pending status"))
    doc.db_set({
        "approval_status": "Approved",
        "approved_by": frappe.session.user,
        "approval_date": nowdate()
    })
    doc.apply_attendance()
    return doc.approval_status


@frappe.whitelist()
def reject_attendance_request(docname):
    doc = frappe.get_doc("Attendance Request", docname)
    doc.db_set("approval_status", "Rejected")
    return doc.approval_status
