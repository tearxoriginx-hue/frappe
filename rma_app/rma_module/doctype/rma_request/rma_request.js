frappe.ui.form.on("RMA Request", {

    refresh(frm) {
        _toggle_rma_type_sections(frm);
        _handle_scan_focus(frm);
        _add_custom_buttons(frm);
        _show_status_banner(frm);
        _toggle_buffer_warranty_section(frm);
    },

    serial_no(frm) {
        if (frm.doc.serial_no) {
            frm.call({
                method: "rma_app.rma_module.doctype.rma_request.rma_request.get_serial_details",
                args: { serial_no: frm.doc.serial_no },
                callback(r) {
                    if (r.message) {
                        $.each(r.message, (key, value) => {
                            frm.set_value(key, value);
                        });
                    }
                },
            });
        }
    },

    rma_type(frm) {
        _toggle_rma_type_sections(frm);
        _toggle_buffer_warranty_section(frm);
        _auto_set_status_on_type_change(frm);
    },

    buffer_warranty(frm) {
        frm.toggle_display("invoice_image", frm.doc.buffer_warranty === 1);
        if (frm.doc.buffer_warranty === 1 && frm.doc.docstatus === 0) {
            frm.set_value("status", "Draft");
            frappe.show_alert({
                message: __("Buffer Warranty selected. Please upload customer's invoice/bill image."),
                indicator: "orange",
            });
        }
    },

    warranty_status(frm) {
        _toggle_buffer_warranty_section(frm);
    },
});


function _toggle_rma_type_sections(frm) {
    frm.toggle_display("repair_notes", frm.doc.rma_type === "Repair");
    frm.toggle_display("section_break_replacement", frm.doc.rma_type === "Replacement");
    frm.toggle_display("column_break_replace", frm.doc.rma_type === "Replacement");
    frm.toggle_display("section_break_dates", frm.doc.status === "Completed" || frm.doc.status === "Replaced");
}


function _toggle_buffer_warranty_section(frm) {
    const is_oow = frm.doc.warranty_status === "Out of Warranty";
    const is_replacement = frm.doc.rma_type === "Replacement";
    frm.toggle_display("buffer_warranty", is_oow && is_replacement);
    frm.toggle_display("invoice_image", frm.doc.buffer_warranty === 1 && is_replacement);
    frm.toggle_display("invoice_verified", is_replacement);
    frm.toggle_display("manager_verified_by", is_replacement);
}


function _auto_set_status_on_type_change(frm) {
    if (frm.doc.rma_type === "Repair") {
        frm.set_value("status", "In Repair");
        setTimeout(() => frm.fields_dict.repair_notes.$input.focus(), 200);
    } else if (frm.doc.rma_type === "Replacement") {
        if (frm.doc.warranty_status === "In Warranty") {
            _check_and_set_pending_approval(frm);
        } else {
            frm.set_value("status", "Draft");
        }
    }
}


function _handle_scan_focus(frm) {
    if (frm.is_new() && !frm.doc.serial_no && frm.doc.docstatus === 0) {
        setTimeout(() => frm.fields_dict.serial_no.$input.focus(), 300);
    }
}


function _add_custom_buttons(frm) {
    frm.clear_custom_buttons();
    const is_draft = frm.doc.docstatus === 0;
    const is_submitted = frm.doc.docstatus === 1;
    const is_manager = frappe.user_roles.includes("RMA Manager") || frappe.user_roles.includes("System Manager");

    if (is_draft && frm.doc.serial_no && !frm.doc.rma_type) {
        frm.page.set_primary_action(__("Start Repair"), () => {
            frm.set_value("rma_type", "Repair");
            frm.save();
        });
        frm.page.set_secondary_action(__("Request Replacement"), () => {
            frm.set_value("rma_type", "Replacement");
            frm.save();
        });
    }

    if (frm.doc.rma_type === "Repair" && frm.doc.status === "In Repair" && is_submitted) {
        frm.add_custom_button(__("Print Slip"), () => _print_slip(frm));
        frm.add_custom_button(__("Mark Completed"), () => {
            frappe.confirm(__("Mark this repair as completed?"), () => {
                frm.call({
                    method: "rma_app.rma_module.doctype.rma_request.rma_request.mark_completed",
                    args: { docname: frm.doc.name },
                    callback: () => frm.reload_doc(),
                });
            });
        }).addClass("btn-primary");
    }

    if (frm.doc.rma_type === "Replacement") {
        if (frm.doc.status === "Approved for Replacement" && is_draft) {
            frm.add_custom_button(__("Scan Replacement Serial"), () => {
                _open_replacement_scan_dialog(frm);
            }).addClass("btn-primary");
        }
        if (frm.doc.status === "Replaced" && is_submitted) {
            frm.add_custom_button(__("Print Slip"), () => _print_slip(frm));
        }
    }

    if (is_submitted && (frm.doc.status === "Completed" || frm.doc.status === "Replaced" || frm.doc.status === "Cancelled")) {
        frm.add_custom_button(__('View Audit Log'), function() {
            _show_audit_log_dialog(frm);
        });
    }

    if (frm.doc.status === "Pending Approval" && is_draft) {
        if (frm.doc.buffer_warranty && !frm.doc.invoice_verified && is_manager) {
            frm.add_custom_button(__("Verify Invoice"), () => {
                frappe.confirm(__("Verify this invoice and approve the replacement?"), () => {
                    frm.call({
                        method: "rma_app.rma_module.doctype.rma_request.rma_request.verify_invoice",
                        args: { docname: frm.doc.name },
                        callback: () => frm.reload_doc(),
                    });
                });
            }).addClass("btn-primary");
        } else if (is_manager) {
            frm.add_custom_button(__("Approve Replacement"), () => {
                frappe.confirm(__("Approve this replacement request?"), () => {
                    frm.call({
                        method: "rma_app.rma_module.doctype.rma_request.rma_request.approve_replacement",
                        args: { docname: frm.doc.name },
                        callback: () => frm.reload_doc(),
                    });
                });
            }).addClass("btn-primary");
        }
    }
}


function _open_replacement_scan_dialog(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __("Scan Replacement Serial"),
        fields: [
            {
                fieldname: "new_serial",
                fieldtype: "Link",
                label: __("New Serial No"),
                options: "Serial No",
                reqd: 1,
                description: __("Scan or type the replacement serial number"),
            },
        ],
        primary_action_label: __("Set & Save"),
        primary_action(values) {
            frm.call({
                method: "rma_app.rma_module.doctype.rma_request.rma_request.create_replacement",
                args: {
                    docname: frm.doc.name,
                    new_serial: values.new_serial,
                },
                callback(r) {
                    if (r.message) {
                        frm.set_value("replacement_serial_no", r.message.replacement_serial_no);
                        frm.set_value("replacement_item_code", r.message.replacement_item_code);
                        frm.refresh_fields();
                        frappe.show_alert({
                            message: __("Replacement serial {0} set").format(values.new_serial),
                            indicator: "green",
                        });
                    }
                    dialog.hide();
                },
            });
        },
    });
    dialog.show();
    setTimeout(() => dialog.get_field("new_serial").$input.focus(), 300);
}


function _show_status_banner(frm) {
    if (frm.doc.docstatus === 1) {
        const status = frm.doc.status || "Draft";
        const msgs = {
            "In Repair": `<span style="color:#f59e0b;">\u2699\uFE0F In Repair</span> - Repair in progress. Click <b>Mark Completed</b> when done.`,
            "Completed": `\u2705 Repair completed on ${frm.doc.completed_date || ""}`,
            "Pending Approval": `\u23F3 ${frm.doc.buffer_warranty ? "Invoice uploaded - " : ""}Awaiting manager approval.`,
            "Approved for Replacement": `\u2705 Approved - Click <b>Scan Replacement Serial</b> to proceed.`,
            "Replaced": `\uD83D\uDD01 Replaced with serial <b>${frm.doc.replacement_serial_no}</b> on ${frm.doc.completed_date || ""}`,
            "Cancelled": `\u274C This RMA has been cancelled.`,
        };
        const colors = {
            "In Repair": "orange",
            "Completed": "green",
            "Pending Approval": "yellow",
            "Approved for Replacement": "blue",
            "Replaced": "purple",
            "Cancelled": "red",
        };
        if (msgs[status]) {
            frm.dashboard.add_comment(msgs[status], colors[status] || "yellow", true);
        }
    }
}


function _print_slip(frm) {
    frappe.call({
        method: "frappe.client.get_print_format",
        args: {
            doctype: "RMA Request",
            name: frm.doc.name,
            print_format: "RMA Slip",
            doc: frm.doc,
        },
        callback(r) {
            if (r.message) {
                const w = window.open();
                if (w) {
                    w.document.write(r.message);
                    w.document.close();
                    w.focus();
                }
            }
        },
    });
}


function _check_and_set_pending_approval(frm) {
    if (frm.is_new() || !frm.doc.warranty_status) return;
    frappe.call({
        method: "frappe.client.get_value",
        args: {
            doctype: "RMA Settings",
            fieldname: ["require_manager_approval_for_replace", "approval_required_for_warranty_status"],
        },
        callback(r) {
            if (r.message) {
                const s = r.message;
                if (s.require_manager_approval_for_replace) {
                    const needs_manager = s.approval_required_for_warranty_status === "In Warranty and Out of Warranty"
                        || (s.approval_required_for_warranty_status === "In Warranty" && frm.doc.warranty_status === "In Warranty");
                    if (needs_manager) {
                        frm.set_value("status", "Pending Approval");
                        frappe.show_alert({
                            message: __("Replacement requires manager approval"),
                            indicator: "orange",
                        });
                    }
                }
            }
        },
    });
}
