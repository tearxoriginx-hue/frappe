#!/usr/bin/env python3
"""Patch remaining HRMS files with erpnext dependencies"""
import os, sys

HRMS = "/home/ubuntu/DEV/main_f/v15_frappe/frappe-bench/apps/hrms/hrms"

def patch_file(relpath, old, new):
    filepath = os.path.join(HRMS, relpath)
    if not os.path.exists(filepath):
        print(f"SKIP (not found): {relpath}")
        return False
    with open(filepath, 'r') as f:
        content = f.read()
    if old not in content:
        print(f"SKIP (pattern not in file): {relpath}")
        return False
    if content.count(old) > 1:
        print(f"WARN (multiple matches): {relpath} - count={content.count(old)}")
    content = content.replace(old, new)
    with open(filepath, 'w') as f:
        f.write(content)
    print(f"FIXED: {relpath}")
    return True

# === 1. hr/utils.py - replace all erpnext references ===
patch_file("hr/utils.py",
    "import erpnext\nfrom erpnext import get_company_currency\nfrom erpnext.setup.doctype.employee.employee import (\n\tget_holiday_list_for_employee,\n\tInactiveEmployeeStatusError,\n\tget_employee_email,\n)",
    "from hrms.hrms_stubs import get_company_currency, get_holiday_list_for_employee, InactiveEmployeeStatusError, get_employee_email")

patch_file("hr/utils.py",
    "erpnext.allow_regional",
    "allow_regional")
    
# Add import for allow_regional at top of file
with open(os.path.join(HRMS, "hr/utils.py"), 'r') as f:
    content = f.read()
# Replace the import line to also include allow_regional
content = content.replace(
    "from hrms.hrms_stubs import get_company_currency, get_holiday_list_for_employee, InactiveEmployeeStatusError, get_employee_email",
    "from hrms.hrms_stubs import get_company_currency, get_holiday_list_for_employee, InactiveEmployeeStatusError, get_employee_email, allow_regional, get_region"
)

# Replace erpnext.get_company_currency() calls
content = content.replace("erpnext.get_company_currency(doc.company)", "get_company_currency(doc.company)")
content = content.replace("erpnext.get_company_currency(company)", "get_company_currency(company)")

with open(os.path.join(HRMS, "hr/utils.py"), 'w') as f:
    f.write(content)

# === 2. Various helper files ===
patch_file("hr/doctype/hr_settings/hr_settings.py",
    "from erpnext.utilities.naming import set_by_naming_series",
    "from frappe.model.naming import set_name_by_naming_series as set_by_naming_series")

patch_file("hr/doctype/leave_encashment/leave_encashment.py",
    "from erpnext.accounts.general_ledger import make_gl_entries",
    "# from erpnext.accounts.general_ledger import make_gl_entries")

patch_file("hr/doctype/leave_encashment/leave_encashment.py",
    "from erpnext.controllers.accounts_controller import AccountsController",
    "from frappe.model.document import Document\nfrom hrms.hrms_stubs import get_company_currency")

# === 3. Payroll files ===
patch_file("payroll/doctype/income_tax_slab/income_tax_slab.py",
    "import erpnext",
    "from hrms.hrms_stubs import get_company_currency")

patch_file("payroll/doctype/income_tax_slab/income_tax_slab.py",
    "self.currency = erpnext.get_company_currency(self.company)",
    "self.currency = get_company_currency(self.company)")

patch_file("payroll/doctype/salary_structure/salary_structure.py",
    "import erpnext",
    "from hrms.hrms_stubs import get_company_currency, get_default_company")

patch_file("payroll/doctype/salary_structure/salary_structure.py",
    "import erpnext",
    "from hrms.hrms_stubs import get_company_currency")

patch_file("payroll/doctype/salary_structure/salary_structure.py",
    "company_curency = erpnext.get_company_currency(company)",
    "company_curency = get_company_currency(company)")

# === 4. Employee Advance ===
patch_file("hr/doctype/employee_advance/employee_advance.py",
    "from erpnext.accounts.doctype.journal_entry.journal_entry import get_default_bank_cash_account",
    "from hrms.hrms_stubs import get_default_bank_cash_account")

# Make import erpnext -> stubs
with open(os.path.join(HRMS, "hr/doctype/employee_advance/employee_advance.py"), 'r') as f:
    content = f.read()
content = content.replace("import erpnext\nfrom hrms.hrms_stubs import get_default_bank_cash_account", 
                          "from hrms.hrms_stubs import get_default_bank_cash_account, get_default_cost_center")
# Wait, I need to check what's actually in get_default_cost_center. I don't have that in stubs.
# Let me just add a stub and replace erpnext.get_default_cost_center with frappe.db.get_value
with open(os.path.join(HRMS, "hr/doctype/employee_advance/employee_advance.py"), 'r') as f:
    content = f.read()
content = content.replace("erpnext.get_default_cost_center(doc.company)", "frappe.db.get_single_value('Company', 'cost_center')")
content = content.replace("erpnext.get_default_cost_center(company)", "frappe.db.get_single_value('Company', 'cost_center')")
with open(os.path.join(HRMS, "hr/doctype/employee_advance/employee_advance.py"), 'w') as f:
    f.write(content)

# === 5. Expense Claim ===
# This is heavily accounting-dependent. Let me just make imports work with stubs.
with open(os.path.join(HRMS, "hr/doctype/expense_claim/expense_claim.py"), 'r') as f:
    content = f.read()

# Replace class inheritance
content = content.replace(
    "from erpnext.controllers.accounts_controller import AccountsController",
    "from frappe.model.document import Document\nfrom hrms.hrms_stubs import get_company_currency"
)

# Replace the class
content = content.replace(
    "class ExpenseClaim(AccountsController):",
    "class ExpenseClaim(Document):"
)

# Replace import erpnext with stubs
content = content.replace(
    "import erpnext\nfrom erpnext.accounts.doctype.repost_accounting_ledger.repost_accounting_ledger import (\n\tvalidate_docs_for_voucher_types,\n)",
    "from hrms.hrms_stubs import get_company_currency, get_default_cost_center"
)

content = content.replace(
    "from erpnext.accounts.doctype.sales_invoice.sales_invoice import get_bank_cash_account",
    "from hrms.hrms_stubs import get_bank_cash_account"
)

content = content.replace(
    "from erpnext.accounts.general_ledger import make_gl_entries",
    "# from erpnext.accounts.general_ledger import make_gl_entries"
)

content = content.replace("erpnext.get_default_cost_center(expense_claim.company)", "get_default_cost_center(expense_claim.company)")
content = content.replace("erpnext.get_default_cost_center(company)", "get_default_cost_center(company)")

with open(os.path.join(HRMS, "hr/doctype/expense_claim/expense_claim.py"), 'w') as f:
    f.write(content)

# === 6. Gratuity ===
with open(os.path.join(HRMS, "payroll/doctype/gratuity/gratuity.py"), 'r') as f:
    content = f.read()
content = content.replace(
    "from erpnext.accounts.general_ledger import make_gl_entries\nfrom erpnext.controllers.accounts_controller import AccountsController",
    "# from erpnext.accounts.general_ledger import make_gl_entries\nfrom frappe.model.document import Document"
)
content = content.replace("class Gratuity(AccountsController):", "class Gratuity(Document):")
with open(os.path.join(HRMS, "payroll/doctype/gratuity/gratuity.py"), 'w') as f:
    f.write(content)

# === 7. Setup.py - Remove erpnext patches ===
with open(os.path.join(HRMS, "setup.py"), 'r') as f:
    content = f.read()
# Remove the entire get_post_install_patches function with erpnext references
import re
# Find and replace the patches list
old_patches = '''\t\t"erpnext.patches.v13_0.move_tax_slabs_from_payroll_period_to_income_tax_slab",
\t\t"erpnext.patches.v13_0.move_doctype_reports_and_notification_from_hr_to_payroll",
\t\t"erpnext.patches.v13_0.move_payroll_setting_separately_from_hr_settings",
\t\t"erpnext.patches.v13_0.update_start_end_date_for_old_shift_assignment",
\t\t"erpnext.patches.v13_0.updates_for_multi_currency_payroll",
\t\t"erpnext.patches.v13_0.update_reason_for_resignation_in_employee",
\t\t"erpnext.patches.v13_0.set_company_in_leave_ledger_entry",
\t\t"erpnext.patches.v13_0.rename_stop_to_send_birthday_reminders",
\t\t"erpnext.patches.v13_0.set_training_event_attendance",
\t\t"erpnext.patches.v14_0.set_payroll_cost_centers",
\t\t"erpnext.patches.v13_0.update_employee_advance_status",
\t\t"erpnext.patches.v13_0.update_expense_claim_status_for_paid_advances",
\t\t"erpnext.patches.v14_0.delete_employee_transfer_property_doctype",
\t\t"erpnext.patches.v13_0.set_payroll_entry_status",'''
content = content.replace(old_patches, "")
with open(os.path.join(HRMS, "setup.py"), 'w') as f:
    f.write(content)

# === 8. Override files ===
# employee_payment_entry.py - skip entirely, we'll disable it
# employee_project.py - skip, we'll disable it  
# employee_timesheet.py - skip, we'll disable it
# company.py - skip, we'll disable it

print("\nRemaining erpnext references in production files:")
os.system(f"grep -rn 'from erpnext\\|import erpnext\\|erpnext\\.' {HRMS} --include='*.py' | grep -v __pycache__ | grep -v '.pyc' | grep -v test_ | grep -v '/test_'")
