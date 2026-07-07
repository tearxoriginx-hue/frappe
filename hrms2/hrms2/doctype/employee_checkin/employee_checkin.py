import frappe
from frappe.model.document import Document
from frappe import _


class EmployeeCheckin(Document):
    def validate(self):
        self.validate_time()

    def validate_time(self):
        if not self.time:
            self.time = frappe.utils.now_datetime()


@frappe.whitelist()
def add_log_based_on_employee_field(employee_field_value, log_type, device_id="PWA", timestamp=None):
    """Create an Employee Checkin log using employee field value."""
    # Find employee by user_id
    emp = frappe.db.get_value("Employee",
        {"user_id": employee_field_value, "status": "Active"},
        ["name", "employee_name"], as_dict=True)

    if not emp:
        emp = frappe.db.get_value("Employee",
            {"employee_name": employee_field_value, "status": "Active"},
            ["name", "employee_name"], as_dict=True)

    if not emp:
        frappe.throw(_("No active employee found for {0}").format(employee_field_value))

    checkin = frappe.get_doc({
        "doctype": "Employee Checkin",
        "employee": emp.name,
        "log_type": log_type,
        "time": timestamp or frappe.utils.now_datetime(),
        "device_id": device_id,
    })
    checkin.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"status": "success", "log_name": checkin.name, "employee": emp.employee_name}


def update_attendance_from_checkin(doc, method):
    """Hook: Update attendance when a checkin is created."""
    if doc.skip_auto_attendance:
        return

    date = frappe.utils.getdate(doc.time)
    existing = frappe.db.get_value("Attendance", {
        "employee": doc.employee,
        "attendance_date": date,
        "docstatus": 1,
    })

    if not existing:
        attendance = frappe.get_doc({
            "doctype": "Attendance",
            "employee": doc.employee,
            "attendance_date": date,
            "status": "Present",
            "in_time": doc.time.time() if doc.log_type == "IN" else None,
            "out_time": doc.time.time() if doc.log_type == "OUT" else None,
        })
        attendance.flags.ignore_permissions = True
        attendance.insert()
        frappe.db.set_value("Employee Checkin", doc.name, "attendance", attendance.name)
    else:
        att_doc = frappe.get_doc("Attendance", existing)
        if doc.log_type == "IN" and not att_doc.in_time:
            att_doc.db_set("in_time", doc.time.time())
        elif doc.log_type == "OUT":
            att_doc.db_set("out_time", doc.time.time())
        frappe.db.set_value("Employee Checkin", doc.name, "attendance", existing)
