var _replacement_confirmed = false;

frappe.ui.form.on("RMA Request", {

    refresh(frm) {
        _update_visibility(frm);
        _handle_scan_focus(frm);
        _add_custom_buttons(frm);
        _show_status_banner(frm);
    },

    before_save(frm) {
        if (frm.is_new() && frm.doc.rma_type === "Replacement" && frm.doc.replacement_serial_no && !_replacement_confirmed) {
            frappe.validated = false;
            frappe.confirm(
                __("Are you sure you want to replace Serial <b>{0}</b> with <b>{1}</b>?", [
                    frm.doc.serial_no, frm.doc.replacement_serial_no
                ]),
                () => {
                    _replacement_confirmed = true;
                    frm.save();
                },
                () => {}
            );
        }
    },

    after_save(frm) {
        _replacement_confirmed = false;
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
                        _update_visibility(frm);
                    }
                },
            });
        }
    },

    rma_type(frm) {
        _update_visibility(frm);
        _auto_set_status_on_type_change(frm);
    },

    buffer_warranty(frm) {
        _update_visibility(frm);
        if (frm.doc.buffer_warranty === 1 && frm.is_new()) {
            frappe.show_alert({
                message: __("Buffer Warranty selected. Please upload customer's invoice/bill image."),
                indicator: "orange",
            });
        }
    },

    warranty_status(frm) {
        _update_visibility(frm);
    },
});


function _update_visibility(frm) {
    var is_repair = frm.doc.rma_type === "Repair";
    var is_replacement = frm.doc.rma_type === "Replacement";
    var is_oow = frm.doc.warranty_status === "Out of Warranty";
    var is_terminal = ["Repaired", "Replaced", "Cancelled"].includes(frm.doc.status);

    frm.toggle_display("repair_notes", is_repair);
    frm.toggle_display("section_break_replacement", is_replacement);
    frm.toggle_display("column_break_replace", is_replacement);

    const show_buffer = is_oow && is_replacement;
    frm.toggle_display("buffer_warranty", show_buffer);
    frm.toggle_reqd("buffer_warranty", show_buffer);

    const show_invoice = frm.doc.buffer_warranty === 1 && is_replacement;
    frm.toggle_display("invoice_image", show_invoice);
    frm.toggle_reqd("invoice_image", show_invoice);

    frm.toggle_display("invoice_verified", is_replacement);
    frm.toggle_display("manager_verified_by", is_replacement);
    frm.toggle_display("section_break_dates", is_terminal);
}


function _auto_set_status_on_type_change(frm) {
    if (!frm.is_new()) return;

    if (frm.doc.rma_type === "Repair") {
        frm.set_value("status", "Processing");
        setTimeout(() => {
            if (frm.fields_dict && frm.fields_dict.repair_notes) {
                frm.fields_dict.repair_notes.$input.focus();
            }
        }, 200);
    } else if (frm.doc.rma_type === "Replacement") {
        frm.set_value("status", "Replaced");
        setTimeout(() => {
            if (frm.fields_dict && frm.fields_dict.replacement_serial_no &&
                frm.fields_dict.replacement_serial_no.$input) {
                frm.fields_dict.replacement_serial_no.$input.focus();
            }
        }, 200);
    }
}


function _handle_scan_focus(frm) {
    if (frm.is_new() && !frm.doc.serial_no) {
        setTimeout(() => frm.fields_dict.serial_no.$input.focus(), 300);
    }
}


function _add_custom_buttons(frm) {
    frm.clear_custom_buttons();
    const is_new = frm.is_new();
    const is_saved = !is_new;
    const is_manager = frappe.user_roles.includes("RMA Manager") || frappe.user_roles.includes("System Manager");
    const is_terminal = ["Repaired", "Replaced", "Cancelled"].includes(frm.doc.status);

    if (is_new && frm.doc.serial_no && !frm.doc.rma_type) {
        frm.page.set_primary_action(__("Start Repair"), () => {
            frm.set_value("rma_type", "Repair");
            frm.save();
        });
        frm.page.set_secondary_action(__("Request Replacement"), () => {
            frm.set_value("rma_type", "Replacement");
            frm.save();
        });
    }

    if (frm.doc.rma_type === "Repair" && frm.doc.status === "Processing" && is_saved) {
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

    if (is_saved && is_terminal) {
        frm.add_custom_button(__('View Audit Log'), function() {
            _show_audit_log_dialog(frm);
        });
    }

    if (is_saved && frm.doc.status !== "Cancelled") {
        frm.add_custom_button(__("Cancel RMA"), () => {
            frappe.confirm(__("Cancel this RMA request?"), () => {
                frm.call({
                    method: "rma_app.rma_module.doctype.rma_request.rma_request.cancel_rma",
                    args: { docname: frm.doc.name },
                    callback: () => frm.reload_doc(),
                });
            });
        }).addClass("btn-danger");
    }
}



function _show_status_banner(frm) {
    if (frm.is_new()) return;
    var status = frm.doc.status;
    var msg = "";
    var color = "yellow";
    if (status === "Processing") {
        msg = "\u2699\uFE0F <b>Processing</b> \u2014 Click <b>Mark Completed</b> when done.";
        color = "orange";
    } else if (status === "Repaired") {
        msg = "\u2705 Repair completed on " + (frm.doc.completed_date || "");
        color = "green";
    } else if (status === "Replaced") {
        msg = "\uD83D\uDD01 <b>Replaced</b> \u2014 Serial: " + (frm.doc.replacement_serial_no || "N/A")
            + " | Branch: " + (frm.doc.branch || "N/A")
            + " | By: " + (frm.doc.owner || "N/A")
            + " | " + (frm.doc.completed_date || "");
        color = "purple";
    } else if (status === "Cancelled") {
        msg = "\u274C This RMA has been cancelled.";
        color = "red";
    }
    if (msg) {
        frm.set_intro(msg, color);
    }
}


function _show_audit_log_dialog(frm) {
    var logs = (frm.doc.audit_log || []).slice().reverse();
    if (!logs.length) {
        frappe.msgprint(__("No activity recorded for this RMA."));
        return;
    }
    var rows = logs.map(function(log) {
        return "<tr><td>" + (log.date || "") + "</td><td>" + (log.user || "") +
            "</td><td>" + (log.action || "") + "</td><td>" + (log.from_status || "-") +
            "</td><td>" + (log.to_status || "-") + "</td><td>" + (log.notes || "") + "</td></tr>";
    }).join("");
    var table = `<div style="max-height:400px;overflow-y:auto;">
        <table class="table table-bordered table-hover" style="font-size:12px;margin:0;">
            <thead><tr style="background:#f5f5f5;">
                <th>Date</th><th>User</th><th>Action</th><th>From</th><th>To</th><th>Notes</th>
            </tr></thead>
            <tbody>${rows}</tbody>
        </table></div>`;
    var dlg = new frappe.ui.Dialog({
        title: __("RMA Activity Log — {0}", [frm.doc.name]),
        primary_action_label: __("Close"),
        primary_action: function() { dlg.hide(); },
    });
    dlg.$body.html(table);
    dlg.show();
}


