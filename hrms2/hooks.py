app_name = "hrms2"
app_title = "HRMS2"
app_publisher = "Krystaa"
app_description = "HR & Payroll - Employee, Attendance, Biometric, Payroll"
app_email = "hello@krystaa.com"
app_license = "MIT"

doctype_js = {
    "Payroll Entry": "public/js/payroll_entry.js",
    "Employee": "public/js/employee.js",
}

scheduler_events = {
    "hourly": [
        "hrms2.utils.biometric_sync.sync_all_devices",
    ],
}

doc_events = {
    "HR Settings": {
        "validate": "hrms2.utils.biometric_settings.on_hr_settings_validate",
    },
    "Employee Checkin": {
        "on_update": "hrms2.hrms2.doctype.employee_checkin.employee_checkin.update_attendance_from_checkin",
    },
}

custom_fields = {
    "HR Settings": [
        {"fieldname": "biometric_settings_sb","fieldtype": "Section Break","label": "Biometric Settings","collapsible": 1,"insert_after": "unlink_payment_on_cancellation_of_employee_advance"},
        {"fieldname": "enable_biometric_api","default": 1,"fieldtype": "Check","label": "Enable Biometric Punch API","insert_after": "biometric_settings_sb"},
        {"fieldname": "biometric_secret_key","fieldtype": "Data","label": "API Secret Key","insert_after": "enable_biometric_api"},
        {"fieldname": "biometric_endpoint_url","fieldtype": "Data","label": "Endpoint URL","read_only": 1,"insert_after": "biometric_secret_key"},
        {"fieldname": "biometric_short_url","fieldtype": "Data","label": "Short URL","read_only": 1,"insert_after": "biometric_endpoint_url"},
        {"fieldname": "biometric_devices_link","fieldtype": "HTML","options": "<a href='/app/biometric-device' class='btn btn-default btn-xs'>Manage Biometric Devices &rarr;</a>","insert_after": "biometric_short_url"},
        {"fieldname": "biometric_punch_logs_link","fieldtype": "HTML","options": "<a href='/app/biometric-punch-log' class='btn btn-default btn-xs'>View Punch Audit Logs &rarr;</a>","insert_after": "biometric_devices_link"},
        {"fieldname": "biometric_setup_guide","fieldtype": "HTML","label": "Setup Instructions","options": "<div style='padding:10px;background:#f0f7ff;border-left:4px solid #2490ef;border-radius:4px;font-size:12px;line-height:1.7;'><h4 style='margin:0 0 10px 0;color:#1a1a2e;'>Setup Instructions</h4><ol style='margin:0;padding-left:18px;color:#333;'><li>Add Device: Biometric Device &rarr; New &rarr; IP, Port (4370), Branch.</li><li>Map Employees: Employee &rarr; Device Mappings table &rarr; Template ID.</li><li>Configure: Set Endpoint URL (above) on device Push mode.</li><li>Alternative URL: Use Short URL (above) for simple HTTP POST.</li><li>Secret Key: Send as header X-Biometric-Secret.</li><li>Test: Open Biometric Device &rarr; Click Test Connection.</li><li>Auto Sync: Runs hourly. Check Biometric Punch Log.</li></ol><p style='margin:8px 0 0 0;font-size:11px;color:#666;'>Tip: PWA Mobile App works for Geo-Location check-in.</p></div>","insert_after": "biometric_punch_logs_link"},
        {"fieldname": "employee_id_prefixes","default": "EMP-\nKST-EMP-","fieldtype": "Small Text","label": "Employee ID Prefixes","description": "One prefix per line. Employee ID format: PREFIX + sequential number.","insert_after": "biometric_setup_guide"},
    ],
    "Employee": [
        {"fieldname": "checkin_geofence_sb","fieldtype": "Section Break","label": "Check-in Settings","insert_after": "attendance_type"},
        {"fieldname": "checkin_geofence_type","default": "SOFT","fieldtype": "Select","label": "Geofence Check-in Type","options": "SOFT\nHARD\nDISABLED","description": "HARD=block, SOFT=allow+flag, DISABLED=no geofence","insert_after": "checkin_geofence_sb"},
    ],
    "Employee Checkin": [
        {"fieldname": "checkin_details_sb","fieldtype": "Section Break","label": "Check-in Details","insert_after": "employee"},
        {"fieldname": "checkin_selfie","fieldtype": "Attach Image","label": "Check-in Selfie","insert_after": "checkin_details_sb"},
        {"fieldname": "checkin_ip_address","fieldtype": "Data","label": "IP Address","read_only": 1,"insert_after": "checkin_selfie"},
        {"fieldname": "checkin_user_agent","fieldtype": "Small Text","label": "User Agent","read_only": 1,"insert_after": "checkin_ip_address"},
        {"fieldname": "checkin_within_geofence","fieldtype": "Check","label": "Within Geofence","read_only": 1,"insert_after": "checkin_user_agent"},
    ],
}

permission_query_conditions = {}
has_permission = {}
user_data_fields = [
    {"doctype": "Employee","filter_by": "user_id","redact_fields": ["employee_name","date_of_birth","cell_number"],"partial": 1},
]
