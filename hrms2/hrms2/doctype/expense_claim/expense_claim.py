import frappe
from frappe.model.document import Document


class ExpenseClaim(Document):
    def validate(self):
        self.calculate_totals()

    def calculate_totals(self):
        total = 0
        if self.expenses:
            for exp in self.expenses:
                total += exp.amount or 0
        self.total_claimed_amount = total
        self.total_sanctioned_amount = total
