import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate, nowdate, add_days
import json


class PayrollEntry(Document):
    def validate(self):
        self.validate_dates()
        if self.get("_action") == "submit":
            self.validate_employees()

    def on_submit(self):
        """Generate salary slips for all selected employees"""
        if self.status == "Draft":
            self.db_set("status", "Processing")
            self.generate_salary_slips()

    def on_cancel(self):
        self.db_set("status", "Cancelled")

    def validate_dates(self):
        if self.start_date and self.end_date and getdate(self.start_date) > getdate(self.end_date):
            frappe.throw(_("Start date cannot be after end date"))

    def validate_employees(self):
        if not self.employees:
            frappe.throw(_("Please add at least one employee"))

    def generate_salary_slips(self):
        """Create Salary Slip documents for all employees in this payroll"""
        success = 0
        errors = 0

        for emp in self.employees:
            try:
                # Check if salary slip already exists for this period
                existing = frappe.db.get_value("Salary Slip", {
                    "employee": emp.employee,
                    "start_date": self.start_date,
                    "end_date": self.end_date,
                    "docstatus": ("!=", 2)
                }, "name")

                if existing:
                    frappe.msgprint(_("Salary slip {0} already exists for {1}").format(existing, emp.employee))
                    continue

                # Get employee details
                emp_doc = frappe.get_doc("Employee", emp.employee)

                # Validate salary structure assignment exists
                ssa = frappe.db.get_value("Salary Structure Assignment", {
                    "employee": emp.employee,
                    "from_date": ("<=", self.end_date or self.start_date),
                    "docstatus": 1
                }, "name", order_by="from_date desc")

                if not ssa:
                    frappe.msgprint(_("No active Salary Structure Assignment found for {0}. Skipping.").format(emp.employee))
                    errors += 1
                    continue

                # Get pay date
                pay_date = self.posting_date or nowdate()

                # Create salary slip
                slip = frappe.get_doc({
                    "doctype": "Salary Slip",
                    "employee": emp.employee,
                    "employee_name": emp_doc.employee_name,
                    "department": emp_doc.department,
                    "designation": emp_doc.designation,
                    "company": self.company,
                    "posting_date": pay_date,
                    "start_date": self.start_date,
                    "end_date": self.end_date,
                    "status": "Generated"
                })
                slip.insert(ignore_permissions=True)
                slip.submit()
                success += 1

            except Exception as e:
                frappe.log_error(f"Payroll generation failed for {emp.employee}: {str(e)}")
                errors += 1

        # Update totals
        totals = frappe.db.sql("""
            SELECT 
                COUNT(*) as count,
                COALESCE(SUM(gross_pay), 0) as gross,
                COALESCE(SUM(total_deduction), 0) as deduction,
                COALESCE(SUM(net_pay), 0) as net
            FROM `tabSalary Slip`
            WHERE start_date = %s AND end_date = %s AND docstatus = 1
        """, (self.start_date, self.end_date), as_dict=True)

        if totals:
            self.db_set({
                "total_employees": cint(totals[0].count),
                "total_gross_pay": flt(totals[0].gross),
                "total_deduction": flt(totals[0].deduction),
                "total_net_pay": flt(totals[0].net),
                "status": "Completed" if errors == 0 else "Failed"
            })

    def get_employees(self):
        """Fetch employees based on filters (used by Fetch Employees button)"""
        filters = [["status", "=", "Active"]]
        if self.branch:
            filters.append(["branch", "=", self.branch])
        if self.department:
            filters.append(["department", "=", self.department])
        if self.company:
            filters.append(["company", "=", self.company])

        employees = frappe.db.get_all("Employee", filters=filters,
            fields=["name as employee", "employee_name", "department", "designation"])

        return employees


@frappe.whitelist()
def fetch_employees(docname):
    """Fetch employees for a Payroll Entry based on filters"""
    doc = frappe.get_doc("Payroll Entry", docname)
    employees = doc.get_employees()
    
    # Clear existing
    doc.set("employees", [])
    for emp in employees:
        doc.append("employees", emp)
    
    doc.save(ignore_permissions=True)
    return len(employees)


@frappe.whitelist()
def download_payment_excel(docname):
    """Generate and return Excel file with employee bank details and net pay"""
    doc = frappe.get_doc("Payroll Entry", docname)
    
    # Get all salary slips for this payroll period
    slips = frappe.db.sql("""
        SELECT 
            ss.employee,
            ss.employee_name,
            ss.bank_name,
            ss.bank_account_no,
            ss.net_pay,
            ss.salary_mode,
            e.ifsc_code,
            e.pan_number
        FROM `tabSalary Slip` ss
        JOIN `tabEmployee` e ON e.name = ss.employee
        WHERE ss.start_date = %s 
            AND ss.end_date = %s
            AND ss.docstatus = 1
        ORDER BY ss.employee_name
    """, (doc.start_date, doc.end_date), as_dict=True)

    return slips


@frappe.whitelist()
def upload_payment_confirmation(docname, data):
    """Process uploaded Excel with payment confirmation data"""
    import json
    doc = frappe.get_doc("Payroll Entry", docname)
    
    if isinstance(data, str):
        data = json.loads(data)
    
    updated = 0
    for row in data:
        employee = row.get("employee")
        payment_ref = row.get("payment_reference")
        paid_amount = row.get("paid_amount")
        status = row.get("status", "Paid")
        
        if employee:
            # Update salary slip status
            slip_name = frappe.db.get_value("Salary Slip", {
                "employee": employee,
                "start_date": doc.start_date,
                "end_date": doc.end_date,
                "docstatus": 1
            }, "name")
            
            if slip_name:
                frappe.db.set_value("Salary Slip", slip_name, "status", status)
                updated += 1
    
    doc.db_set("status", "Completed")
    return {"updated": updated}
