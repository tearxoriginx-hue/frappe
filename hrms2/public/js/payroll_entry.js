frappe.ui.form.on('Payroll Entry', {
    fetch_employees: function(frm) {
        frappe.call({
            method: 'hrms2.hrms2.doctype.payroll_entry.payroll_entry.fetch_employees',
            args: { docname: frm.doc.name },
            callback: function(r) {
                frm.refresh_field('employees');
                frappe.msgprint(__('Employees fetched successfully'));
            }
        });
    },
    export_excel: function(frm) {
        frappe.call({
            method: 'hrms2.hrms2.doctype.payroll_entry.payroll_entry.download_payment_excel',
            args: { docname: frm.doc.name },
            callback: function(r) {
                if (r.message) {
                    var data = r.message;
                    var csv = 'Employee,Name,Bank,Account No,IFSC,Net Pay\n';
                    data.forEach(function(row) {
                        csv += row.employee + ',' + row.employee_name + ',' + 
                               (row.bank_name || '') + ',' + (row.bank_account_no || '') + ',' +
                               (row.ifsc_code || '') + ',' + row.net_pay + '\n';
                    });
                    var blob = new Blob([csv], { type: 'text/csv' });
                    var a = document.createElement('a');
                    a.href = URL.createObjectURL(blob);
                    a.download = 'payroll_payment_' + frm.doc.name + '.csv';
                    a.click();
                    frappe.msgprint(__('Payment file downloaded'));
                }
            }
        });
    }
});
