frappe.ui.form.on('Employee', {
    refresh: function(frm) {
        // Load naming series prefixes from HR Settings
        _load_naming_series(frm);

        // Trigger PF calculations on refresh
        _calculate_pf(frm);

        // Add custom buttons
        frm.add_custom_button(__('Create Attendance'), function() {
            frappe.new_doc('Attendance', {
                employee: frm.doc.name
            });
        }, __('Create'));

        frm.add_custom_button(__('Create Leave Application'), function() {
            frappe.new_doc('Leave Application', {
                employee: frm.doc.name
            });
        }, __('Create'));

        frm.add_custom_button(__('Create Salary Slip'), function() {
            frappe.new_doc('Salary Slip', {
                employee: frm.doc.name
            });
        }, __('Create'));

        frm.add_custom_button(__('Create Employee Advance'), function() {
            frappe.new_doc('Employee Advance', {
                employee: frm.doc.name
            });
        }, __('Create'));

        // Quick links
        if (!frm.is_new()) {
            frm.add_custom_button(__('View Attendance'), function() {
                frappe.set_route('List', 'Attendance', {
                    employee: frm.doc.name
                });
            }, __('View'));

            frm.add_custom_button(__('View Salary Slips'), function() {
                frappe.set_route('List', 'Salary Slip', {
                    employee: frm.doc.name
                });
            }, __('View'));
        }

        // Set default attendance type for new employees
        if (frm.is_new()) {
            frm.set_value('attendance_type', 'Biometric');
        }
    },

    first_name: function(frm) {
        if (frm.doc.first_name) {
            var name = frm.doc.first_name;
            if (frm.doc.last_name) name += ' ' + frm.doc.last_name;
            frm.set_value('employee_name', name);
        }
    },

    last_name: function(frm) {
        if (frm.doc.last_name && frm.doc.first_name) {
            frm.set_value('employee_name', frm.doc.first_name + ' ' + frm.doc.last_name);
        }
    },

    monthly_gross: function(frm) {
        _calculate_pf(frm);
    },

    applicable_pf: function(frm) {
        _calculate_pf(frm);
    }
});


function _load_naming_series(frm) {
    if (!frm.fields_dict || !frm.fields_dict.naming_series) return;
    frappe.db.get_single_value("HR Settings", "employee_id_prefixes", function(prefixes) {
        if (!prefixes || !prefixes.trim()) return;
        
        var series = prefixes.split("\n")
            .map(function(s) { return s.trim(); })
            .filter(function(s) { return s.length > 0; })
            .join("\n");

        if (!series) return;

        // Update naming_series options directly on the field's df
        frm.fields_dict.naming_series.df.options = series;
        frm.refresh_field("naming_series");

        // Set default if none selected on new form
        if (!frm.doc.naming_series && frm.is_new()) {
            var first = series.split("\n")[0];
            if (first) {
                frm.set_value("naming_series", first);
            }
        }
    });
}


function _set_field_safe(frm, fieldname, value) {
    // Only set value if the field actually exists on the form
    if (frm.fields_dict && frm.fields_dict[fieldname]) {
        frm.set_value(fieldname, value);
    }
}

function _calculate_pf(frm) {
    // Only run if the PF fields exist on the form
    if (!frm.fields_dict || !frm.fields_dict.pf_ee_contribution) return;

    var monthly_gross = flt(frm.doc.monthly_gross);
    var applicable_pf = frm.doc.applicable_pf;

    // Reset PF fields if no gross or PF not applicable
    if (!monthly_gross || !applicable_pf) {
        _set_field_safe(frm, "pf_ee_contribution", 0);
        _set_field_safe(frm, "pf_er_contribution", 0);
        _set_field_safe(frm, "monthly_in_hand", monthly_gross);
        _calculate_ctc(frm, monthly_gross, 0);
        return;
    }

    // Get PF percentages from HR Settings (single DB call)
    frappe.db.get_value("HR Settings", "HR Settings",
        ["pf_employee_percentage", "pf_employer_percentage"],
        function(r) {
            var ee_pct = flt(r.pf_employee_percentage) || 12;
            var er_pct = flt(r.pf_employer_percentage) || 13;

            var pf_ee = flt(monthly_gross * ee_pct / 100);
            var pf_er = flt(monthly_gross * er_pct / 100);
            var in_hand = monthly_gross - pf_ee;

            _set_field_safe(frm, "pf_ee_contribution", pf_ee);
            _set_field_safe(frm, "pf_er_contribution", pf_er);
            _set_field_safe(frm, "monthly_in_hand", in_hand);

            _calculate_ctc(frm, monthly_gross, pf_er);
        });
}


function _calculate_ctc(frm, monthly_gross, pf_er) {
    if (!frm.fields_dict || !frm.fields_dict.annual_ctc) return;
    // Annual CTC = (Monthly Gross + Employer PF) x 12
    var annual = flt((monthly_gross + pf_er) * 12);
    _set_field_safe(frm, "annual_ctc", annual);
}
