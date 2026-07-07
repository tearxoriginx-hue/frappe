#!/usr/bin/env python3
"""Batch patch all HRMS files to remove erpnext dependencies"""
import os

HRMS = "/home/ubuntu/DEV/main_f/v15_frappe/frappe-bench/apps/hrms/hrms"

# Replacement rules: (filename_pattern, old_string, new_string)
replacements = [
    # === Pattern 1: employee.employee imports ===
    ("api/__init__.py",
     "from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee",
     "from hrms.hrms_stubs import get_holiday_list_for_employee"),
    ("api/roster.py",
     "from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee",
     "from hrms.hrms_stubs import get_holiday_list_for_employee"),
    ("hr/doctype/attendance_request/attendance_request.py",
     "from erpnext.setup.doctype.employee.employee import is_holiday",
     "from hrms.hrms_stubs import is_holiday"),
    ("hr/doctype/daily_work_summary_group/daily_work_summary_group.py",
     "from erpnext.setup.doctype.holiday_list.holiday_list import is_holiday",
     "from hrms.hrms_stubs import is_holiday"),
    ("hr/doctype/exit_interview/exit_interview.py",
     "from erpnext.setup.doctype.employee.employee import get_employee_email",
     "from hrms.hrms_stubs import get_employee_email"),
    ("hr/doctype/leave_application/leave_application.py",
     "from erpnext.buying.doctype.supplier_scorecard.supplier_scorecard import daterange",
     "from hrms.hrms_stubs import get_period_list as daterange"),
    ("hr/doctype/leave_application/leave_application.py",
     "from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee",
     "from hrms.hrms_stubs import get_holiday_list_for_employee"),
    ("hr/doctype/leave_control_panel/leave_control_panel.py",
     "from erpnext import get_default_company",
     "from hrms.hrms_stubs import get_default_company"),
    ("hr/doctype/shift_type/shift_type.py",
     "from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee",
     "from hrms.hrms_stubs import get_holiday_list_for_employee"),
    ("hr/doctype/shift_type/shift_type.py",
     "from erpnext.setup.doctype.holiday_list.holiday_list import is_holiday",
     "from hrms.hrms_stubs import is_holiday"),
    ("hr/doctype/shift_assignment_tool/shift_assignment_tool.py",
     "from erpnext.accounts.utils import build_qb_match_conditions",
     "from hrms.hrms_stubs import build_qb_match_conditions"),
    ("hr/doctype/training_event/training_event.py",
     "from erpnext.setup.doctype.employee.employee import get_employee_emails",
     "from hrms.hrms_stubs import get_all_employee_emails as get_employee_emails"),
    ("hr/doctype/training_result/training_result.py",
     "from erpnext.setup.doctype.employee.employee import get_employee_emails",
     "from hrms.hrms_stubs import get_all_employee_emails as get_employee_emails"),
    ("hr/doctype/upload_attendance/upload_attendance.py",
     "from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee",
     "from hrms.hrms_stubs import get_holiday_list_for_employee"),
    ("controllers/employee_boarding_controller.py",
     "from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee",
     "from hrms.hrms_stubs import get_holiday_list_for_employee"),
    ("controllers/employee_boarding_controller.py",
     "from erpnext.setup.doctype.holiday_list.holiday_list import is_holiday",
     "from hrms.hrms_stubs import is_holiday"),
    ("controllers/employee_reminders.py",
     "from erpnext.setup.doctype.employee.employee import get_all_employee_emails, get_employee_email",
     "from hrms.hrms_stubs import get_all_employee_emails, get_employee_email"),

    # === Pattern 2: Reports ===
    ("hr/report/employees_working_on_a_holiday/employees_working_on_a_holiday.py",
     "from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee",
     "from hrms.hrms_stubs import get_holiday_list_for_employee"),
    ("hr/report/shift_attendance/shift_attendance.py",
     "from erpnext.accounts.utils import build_qb_match_conditions",
     "from hrms.hrms_stubs import build_qb_match_conditions"),
    ("hr/report/employee_analytics/employee_analytics.py",
     "from erpnext.accounts.utils import build_qb_match_conditions",
     "from hrms.hrms_stubs import build_qb_match_conditions"),
    ("hr/report/employee_birthday/employee_birthday.py",
     "from erpnext.accounts.utils import build_qb_match_conditions",
     "from hrms.hrms_stubs import build_qb_match_conditions"),

    # === Pattern 3: Payroll reports ===
    ("payroll/report/salary_register/salary_register.py",
     "import erpnext",
     "from hrms.hrms_stubs import get_company_currency"),
    ("payroll/report/salary_register/salary_register.py",
     "import erpnext",
     ""),  # Remove duplicate since we replaced the first occurrence
    ("payroll/report/salary_register/salary_register.py",
     "company_currency = erpnext.get_company_currency(filters.get(\"company\"))",
     "company_currency = get_company_currency(filters.get(\"company\"))"),
    ("payroll/report/salary_payments_based_on_payment_mode/salary_payments_based_on_payment_mode.py",
     "import erpnext",
     "from hrms.hrms_stubs import get_company_currency"),
    ("payroll/report/salary_payments_based_on_payment_mode/salary_payments_based_on_payment_mode.py",
     "import erpnext",
     ""),  # Remove duplicate
    ("payroll/report/salary_payments_based_on_payment_mode/salary_payments_based_on_payment_mode.py",
     "currency = erpnext.get_company_currency(filters.company)",
     "currency = get_company_currency(filters.company)"),
    ("payroll/report/salary_payments_via_ecs/salary_payments_via_ecs.py",
     "import erpnext",
     "from hrms.hrms_stubs import get_region"),
    ("payroll/report/salary_payments_via_ecs/salary_payments_via_ecs.py",
     "import erpnext",
     ""),  # Remove duplicate
    ("payroll/report/salary_payments_via_ecs/salary_payments_via_ecs.py",
     "if erpnext.get_region() == \"India\"",
     "if get_region() == \"India\""),
    ("payroll/report/salary_payments_via_ecs/salary_payments_via_ecs.py",
     "if erpnext.get_region() == \"India\":",
     "if get_region() == \"India\":"),
    ("payroll/report/income_tax_deductions/income_tax_deductions.py",
     "import erpnext",
     "from hrms.hrms_stubs import get_region"),
    ("payroll/report/income_tax_deductions/income_tax_deductions.py",
     "import erpnext",
     ""),  # Remove duplicate
    ("payroll/report/income_tax_deductions/income_tax_deductions.py",
     "is_indian_company = erpnext.get_region(filters.get(\"company\")) == \"India\"",
     "is_indian_company = get_region(filters.get(\"company\")) == \"India\""),
]

# Apply replacements
for filename, old, new in replacements:
    filepath = os.path.join(HRMS, filename)
    if not os.path.exists(filepath):
        print(f"SKIP (not found): {filename}")
        continue
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        if old in content:
            content = content.replace(old, new, 1)  # Only replace first occurrence
            with open(filepath, 'w') as f:
                f.write(content)
            print(f"FIXED: {filename}")
        else:
            print(f"SKIP (not found in file): {filename}")
    except Exception as e:
        print(f"ERROR: {filename}: {e}")

print("\nDone! Remaining erpnext references:")
os.system(f"grep -rn 'from erpnext\\|import erpnext\\|erpnext\\.' {HRMS} --include='*.py' | grep -v __pycache__ | grep -v '.pyc'")
