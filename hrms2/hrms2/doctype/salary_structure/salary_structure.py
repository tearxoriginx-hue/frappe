import frappe
from frappe import _
from frappe.model.document import Document


class SalaryStructure(Document):
    def validate(self):
        self.validate_duplicate_components()

    def validate_duplicate_components(self):
        components = []
        for table in [self.earnings, self.deductions]:
            for row in (table or []):
                if row.salary_component in components:
                    frappe.throw(_("Salary Component {0} is already added").format(row.salary_component))
                components.append(row.salary_component)
