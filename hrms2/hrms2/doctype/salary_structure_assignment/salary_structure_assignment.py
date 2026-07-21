import frappe
from frappe.model.document import Document


class SalaryStructureAssignment(Document):
    def validate(self):
        self.validate_dates()
        self.calculate_base_and_variable()

    def validate_dates(self):
        # Ensure no overlapping active assignments for same employee
        existing = frappe.db.get_value("Salary Structure Assignment",
            {"employee": self.employee, "from_date": self.from_date, "name": ("!=", self.name)},
            "name")
        if existing:
            frappe.throw(_("Another assignment already exists for this employee on {0}").format(self.from_date))

    def calculate_base_and_variable(self):
        ss = frappe.get_doc("Salary Structure", self.salary_structure)
        base = 0
        variable = 0
        for e in (ss.earnings or []):
            if e.formula:
                base += 0  # formula-based will be computed at payroll time
            else:
                base += e.amount or 0
        for d in (ss.deductions or []):
            if d.formula:
                variable += 0
            else:
                variable += d.amount or 0
        self.base = base
        self.variable = variable
