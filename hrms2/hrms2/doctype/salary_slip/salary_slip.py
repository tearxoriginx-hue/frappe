import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate, date_diff, flt


class SalarySlip(Document):
    def validate(self):
        self.calculate_working_days()
        self.get_attendance_data()
        self.calculate_payment_days()
        self.calculate_components()
        self.calculate_totals()

    def on_submit(self):
        self.db_set("status", "Submitted")
        self.deduct_employee_advances()

    def on_cancel(self):
        self.db_set("status", "Cancelled")

    def calculate_working_days(self):
        """Calculate total working days in the period excluding holidays/weekly offs"""
        if self.start_date and self.end_date:
            total = date_diff(getdate(self.end_date), getdate(self.start_date)) + 1
            # Subtract holidays (skip holidays falling on Sunday)
            from datetime import timedelta
            holiday_dates = set()
            for h in frappe.db.sql("""
                SELECT h.holiday_date FROM `tabHoliday` h, `tabHoliday List` hl
                WHERE h.parent = hl.name AND hl.name IN (
                    SELECT holiday_list FROM `tabEmployee` WHERE name = %s
                )
                AND h.holiday_date BETWEEN %s AND %s
            """, (self.employee, self.start_date, self.end_date), as_dict=True):
                holiday_dates.add(str(h.holiday_date))
            weekly_offs = 0
            d = getdate(self.start_date)
            end = getdate(self.end_date)
            while d <= end:
                if d.weekday() == 6 and str(d) not in holiday_dates:
                    weekly_offs += 1
                d += timedelta(days=1)
            self.total_working_days = total - len(holiday_dates) - weekly_offs

    def get_attendance_data(self):
        """Get present days, LWP, and overtime from attendance records"""
        if not self.start_date or not self.end_date:
            return

        attendance = frappe.db.sql("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present,
                SUM(CASE WHEN status = 'Half Day' THEN 0.5 ELSE 0 END) as half_day,
                SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent,
                SUM(total_hours) as total_hours
            FROM `tabAttendance`
            WHERE employee = %s
                AND attendance_date BETWEEN %s AND %s
                AND docstatus = 1
        """, (self.employee, self.start_date, self.end_date), as_dict=True)

        if attendance and attendance[0]:
            row = attendance[0]
            self.total_present_days = flt(row.present or 0) + flt(row.half_day or 0)
            self.leave_without_pay = flt(row.absent or 0)
            # Overtime: any hours beyond 8 per day
            if row.total_hours:
                expected_hours = self.total_working_days * 8
                overtime_hours = max(0, flt(row.total_hours) - expected_hours)
                if not self.overtime_hours:
                    self.overtime_hours = overtime_hours

    def calculate_payment_days(self):
        """Payment days = present days (excluding LWP)"""
        if self.total_working_days > 0:
            self.payment_days = self.total_working_days - self.leave_without_pay
        else:
            self.payment_days = 0

    def calculate_components(self):
        """Calculate earnings and deductions based on salary structure"""
        # Clear existing tables
        self.earnings = []
        self.deductions = []

        # Get salary structure assignment
        ssa = frappe.db.get_value("Salary Structure Assignment",
            {"employee": self.employee, "from_date": ("<=", self.end_date or self.start_date)},
            "salary_structure", order_by="from_date desc")

        if not ssa:
            frappe.msgprint(_("No salary structure assigned to {0}").format(self.employee_name))
            return

        ss = frappe.get_doc("Salary Structure", ssa)

        # Calculate hourly rate for overtime
        total_component_amount = 0
        for comp in (ss.earnings or []):
            amount = self.get_component_amount(comp)
            total_component_amount += amount
            self.append("earnings", {
                "salary_component": comp.salary_component,
                "abbr": comp.abbr,
                "amount": amount,
                "type": "Earning"
            })

        # Calculate overtime pay (1.5x hourly rate)
        if self.overtime_hours > 0 and total_component_amount > 0 and self.total_working_days > 0:
            hourly_rate = total_component_amount / (self.total_working_days * 8)
            self.overtime_pay = flt(self.overtime_hours * hourly_rate * 1.5)
            # Add overtime as an earning
            self.append("earnings", {
                "salary_component": "Overtime",
                "abbr": "OT",
                "amount": self.overtime_pay,
                "type": "Earning"
            })

        for comp in (ss.deductions or []):
            amount = self.get_component_amount(comp)
            self.append("deductions", {
                "salary_component": comp.salary_component,
                "abbr": comp.abbr,
                "amount": amount,
                "type": "Deduction"
            })

    def get_component_amount(self, comp):
        """Calculate amount for a salary component considering LWP and formulas"""
        if comp.formula:
            try:
                # Simple formula evaluation
                base_components = {e.salary_component: e.amount for e in self.earnings}
                base = comp.amount or 0
                amount = eval(comp.formula, {"__builtins__": {}}, {
                    "base": base,
                    **base_components
                })
                return flt(amount)
            except Exception:
                return comp.amount or 0

        amount = comp.amount or 0
        # Pro-rata for LWP if component depends on LWP
        if comp.depends_on_lwp and self.leave_without_pay > 0 and self.total_working_days > 0:
            amount = amount * (self.payment_days / self.total_working_days)

        return flt(amount)

    def calculate_totals(self):
        """Calculate gross, deductions, net pay"""
        gross = sum(flt(e.amount or 0) for e in self.earnings)
        deductions = sum(flt(d.amount or 0) for d in self.deductions)

        self.gross_pay = gross
        self.total_deduction = deductions
        self.net_pay = gross - deductions
        self.rounded_total = round(self.net_pay)

    def deduct_employee_advances(self):
        """Auto-deduct approved employee advances from salary"""
        advances = frappe.db.sql("""
            SELECT name, amount, repaid_amount, repayment_method, installment_amount
            FROM `tabEmployee Advance`
            WHERE employee = %s
                AND docstatus = 1
                AND status = 'Approved'
                AND repayment_method = 'Salary Deduction'
                AND (COALESCE(repaid_amount, 0) < amount)
        """, self.employee, as_dict=True)

        total_deduction = 0
        for adv in advances:
            remaining = flt(adv.amount) - flt(adv.repaid_amount or 0)
            installment = flt(adv.installment_amount or remaining)
            deduction = min(installment, remaining)

            if deduction > 0:
                self.append("deductions", {
                    "salary_component": "Employee Advance Repayment",
                    "abbr": "ADV",
                    "amount": deduction,
                    "type": "Deduction"
                })
                # Update advance repaid amount
                frappe.db.set_value("Employee Advance", adv.name,
                    "repaid_amount", flt(adv.repaid_amount or 0) + deduction)
                total_deduction += deduction

                if flt(adv.repaid_amount or 0) + deduction >= flt(adv.amount):
                    frappe.db.set_value("Employee Advance", adv.name, "status", "Repaid")

        self.total_loan_repayment = total_deduction
        # Recalculate net pay
        self.net_pay = flt(self.net_pay or 0) - total_deduction
        self.rounded_total = round(self.net_pay)


@frappe.whitelist()
def get_attendance_summary(employee, start_date, end_date):
    """API to get attendance summary for a period (used in Payroll Entry)"""
    data = frappe.db.sql("""
        SELECT 
            COUNT(*) as total_days,
            SUM(CASE WHEN status = 'Present' THEN 1 WHEN status = 'Half Day' THEN 0.5 ELSE 0 END) as present_days,
            SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) as absent_days,
            SUM(CASE WHEN status = 'On Leave' THEN 1 ELSE 0 END) as leave_days
        FROM `tabAttendance`
        WHERE employee = %s AND attendance_date BETWEEN %s AND %s AND docstatus = 1
    """, (employee, start_date, end_date), as_dict=True)
    return data[0] if data else {}
