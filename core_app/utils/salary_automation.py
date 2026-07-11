import frappe
from frappe.utils import getdate, add_months, today
from frappe import _


EXPENSE_EARNING_COMPONENT = "Expense Reimbursement"
ADVANCE_DEDUCTION_COMPONENT = "Advance Recovery"


def _ensure_salary_component(component_name, component_type):
    """Create a salary component if it doesn't exist."""
    if not frappe.db.exists("Salary Component", component_name):
        doc = frappe.get_doc({
            "doctype": "Salary Component",
            "salary_component": component_name,
            "type": component_type,
            "is_additional": 1,
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()


def on_expense_claim_submit(doc, method):
    """
    When an Expense Claim is submitted (Paid), create an Additional Salary as Earning.
    This reimburses the employee via their salary.
    """
    if doc.status != "Paid" and doc.approval_status != "Approved":
        return

    _ensure_salary_component(EXPENSE_EARNING_COMPONENT, "Earning")

    if frappe.db.exists("Additional Salary", {
        "employee": doc.employee,
        "salary_component": EXPENSE_EARNING_COMPONENT,
        "ref_doctype": "Expense Claim",
        "ref_docname": doc.name,
    }):
        return

    amt = float(doc.total_claimed_amount or 0)
    if amt <= 0:
        return

    payroll_date = doc.posting_date or today()
    if getdate(payroll_date) < getdate(today()):
        payroll_date = today()

    additional_salary = frappe.get_doc({
        "doctype": "Additional Salary",
        "employee": doc.employee,
        "salary_component": EXPENSE_EARNING_COMPONENT,
        "amount": amt,
        "type": "Earning",
        "payroll_date": payroll_date,
        "ref_doctype": "Expense Claim",
        "ref_docname": doc.name,
        "notes": f"Auto-created from Expense Claim {doc.name}: {doc.title or ''}",
        "overwrite_salary_structure_amount": 0,
    })
    additional_salary.insert(ignore_permissions=True)
    frappe.db.commit()


def on_employee_advance_submit(doc, method):
    """
    When an Employee Advance is submitted, create Additional Salary deductions
    as repayment installments spread over the repayment months.
    """
    if doc.docstatus != 1:
        return

    _ensure_salary_component(ADVANCE_DEDUCTION_COMPONENT, "Deduction")

    total_amount = float(doc.amount or 0)
    repayment_months = int(doc.repayment_months or 1)
    if total_amount <= 0 or repayment_months < 1:
        return

    existing = frappe.db.exists("Additional Salary", {
        "employee": doc.employee,
        "salary_component": ADVANCE_DEDUCTION_COMPONENT,
        "ref_doctype": "Employee Advance",
        "ref_docname": doc.name,
    })
    if existing:
        return

    installment_amount = round(total_amount / repayment_months, 2)
    remainder = total_amount - (installment_amount * repayment_months)

    start_date = getdate(today())

    for i in range(repayment_months):
        amt = installment_amount
        if i == repayment_months - 1:
            amt += remainder

        payroll_date = add_months(start_date, i)

        if frappe.db.exists("Additional Salary", {
            "employee": doc.employee,
            "salary_component": ADVANCE_DEDUCTION_COMPONENT,
            "payroll_date": str(payroll_date),
            "ref_doctype": "Employee Advance",
            "ref_docname": doc.name,
        }):
            continue

        additional_salary = frappe.get_doc({
            "doctype": "Additional Salary",
            "employee": doc.employee,
            "salary_component": ADVANCE_DEDUCTION_COMPONENT,
            "amount": amt,
            "type": "Deduction",
            "payroll_date": str(payroll_date),
            "ref_doctype": "Employee Advance",
            "ref_docname": doc.name,
            "notes": f"Installment {i+1}/{repayment_months} for Advance {doc.name}: {doc.purpose or ''}",
            "overwrite_salary_structure_amount": 0,
        })
        additional_salary.insert(ignore_permissions=True)

    frappe.db.commit()
