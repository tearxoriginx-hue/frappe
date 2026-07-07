// Copyright (c) 2026, Varun and contributors
// For license information, please see license.txt

frappe.ui.form.on("Dispatch Entry", {

    refresh(frm) {
        _lock_readonly_fields(frm);

        // Auto-fill branch from the logged-in user's Employee record
        if (frm.is_new() && !frm.doc.branch) {
            frappe.db.get_value("Employee", { user_id: frappe.session.user }, "branch", (r) => {
                if (r && r.branch) {
                    frm.set_value("branch", r.branch);
                }
            });
        }

        // Replace serial_nos cell text with clickable badges
        _render_serial_cells(frm);

        // Processing status banner + auto-refresh on submitted docs
        if (frm.doc.docstatus === 1) {
            _show_processing_banner(frm);
            if (["In Queue", "Pending"].includes(frm.doc.processing_status)) {
                clearInterval(frm._refresh_interval);
                frm._refresh_interval = setInterval(() => frm.reload_doc(), 5000);
            } else {
                clearInterval(frm._refresh_interval);
            }
        }

        // On failure — add a "Retry" button
        if (frm.doc.docstatus === 1 && frm.doc.processing_status === "Failed") {
            frm.add_custom_button(__("Retry Processing"), () => {
                frappe.call({
                    method: "dispatched.dispatch_module.doctype.dispatch_entry.dispatch_entry.retry_processing",
                    args: { doc_name: frm.doc.name },
                    callback() {
                        frm.reload_doc();
                        frappe.show_alert({ message: "Re-queued for processing", indicator: "blue" });
                    },
                });
            }).addClass("btn-primary");
        }
    },

    customer(frm) {
        _refresh_totals(frm);
    },
});

// ---------------------------------------------------------------
// Child table events — Dispatch Product
// ---------------------------------------------------------------
frappe.ui.form.on("Dispatch Product", {
    item_code(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.item_code) return;

        frappe.db.get_value("Item", row.item_code, ["warranty_period", "item_name"], (r) => {
            frappe.model.set_value(cdt, cdn, "warranty_period_days", r.warranty_period || 0);
            frappe.model.set_value(cdt, cdn, "item_name", r.item_name || "");
            _calculate_expiry(frm, cdt, cdn);

            // Auto-open scan dialog to save clicks
            if (frm.doc.docstatus === 0) {
                setTimeout(() => {
                    _open_serial_dialog(frm, row.name, row.item_code);
                }, 100);
            }
        });
    },

    // When user clicks the serial_nos cell directly, open the scan dialog
    serial_nos(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (frm.doc.docstatus !== 0) return;  // only on draft
        _open_serial_dialog(frm, row.name, row.item_code);
    },

    products_add(frm, cdt, cdn) {
        setTimeout(() => _render_serial_cells(frm), 300);
    },

    products_remove(frm) {
        _refresh_totals(frm);
    },
});

// ---------------------------------------------------------------
// Private helpers
// ---------------------------------------------------------------

function _lock_readonly_fields(frm) {
    ["posting_date", "posting_time", "total_qty", "processing_status"].forEach(
        (f) => frm.set_df_property(f, "read_only", 1)
    );
}


function _calculate_expiry(frm, cdt, cdn) {
    const row = locals[cdt][cdn];
    const posting_date = frm.doc.posting_date || frappe.datetime.get_today();
    if (!row.warranty_period_days) return;

    const expiry = frappe.datetime.add_days(posting_date, row.warranty_period_days);
    frappe.model.set_value(cdt, cdn, "expiry_date", expiry);
}

function _refresh_totals(frm) {
    let total = 0;
    (frm.doc.products || []).forEach((row) => {
        total += _parse_serials(row.serial_nos || "").length;
    });
    frm.set_value("total_qty", total);
}

function _parse_serials(text) {
    if (!text) return [];
    const seen = new Set();
    return text
        .split("\n")
        .map((s) => s.trim())
        .filter((s) => s && !seen.has(s.toUpperCase()) && seen.add(s.toUpperCase()));
}

// ---------------------------------------------------------------
// Hardware Scanning Smart Validation Helpers
// ---------------------------------------------------------------

function _play_audio_tone(type) {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        if (type === "success") {
            osc.type = 'sine';
            osc.frequency.setValueAtTime(600, ctx.currentTime);
            osc.frequency.setValueAtTime(900, ctx.currentTime + 0.1);
            gain.gain.setValueAtTime(0.1, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.2);
            osc.start();
            osc.stop(ctx.currentTime + 0.2);
        } else if (type === "error") {
            osc.type = 'sawtooth';
            osc.frequency.setValueAtTime(150, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(80, ctx.currentTime + 0.3);
            gain.gain.setValueAtTime(0.3, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
            osc.start();
            osc.stop(ctx.currentTime + 0.3);
        }
    } catch (e) {
        // AudioContext not supported or disabled
    }
}

function _detect_merged_serial(new_sn, existing_serials) {
    // 1. Hard length warning
    if (new_sn.length > 40) return "Scan is unusually long. Multiple barcodes?";
    if (!existing_serials || existing_serials.length === 0) return null;

    // 2. Length Anomaly Detection vs previous scans
    const lengths = existing_serials.map(s => s.length);
    const counts = {};
    let most_common_length = lengths[0];
    let max_count = 0;
    for (const len of lengths) {
        counts[len] = (counts[len] || 0) + 1;
        if (counts[len] > max_count) {
            max_count = counts[len];
            most_common_length = len;
        }
    }

    // If new serial is 1.7x or more the size of the normal one, flag it
    if (new_sn.length >= most_common_length * 1.7 && most_common_length > 3) {
        return `Length is ${new_sn.length} chars, but previous serials are ~${most_common_length} chars.`;
    }

    // 3. Prefix Repetition (e.g., SN1234SN5678)
    const last_sn = existing_serials[existing_serials.length - 1];
    const prefixMatch = last_sn.match(/^([A-Za-z]{2,5}[-_:]?)/);
    if (prefixMatch) {
        const prefix = prefixMatch[1];
        const splitCount = new_sn.toUpperCase().split(prefix.toUpperCase()).length - 1;
        if (splitCount > 1) {
            return `Detected prefix "${prefix}" multiple times.`;
        }
    }

    return null; // All good
}

// ---------------------------------------------------------------
// Render clickable badges inside the "Serial Numbers" grid column
// ---------------------------------------------------------------

function _render_serial_cells(frm) {
    const grid = frm.fields_dict.products && frm.fields_dict.products.grid;
    if (!grid) return;

    setTimeout(() => {
        (frm.doc.products || []).forEach((row, idx) => {
            const $gridRow = $(grid.wrapper).find(`.rows .row-index[data-idx="${idx + 1}"]`).closest('.grid-row');
            if (!$gridRow.length) return;

            // Find the serial_nos cell (look for the column with field "serial_nos")
            const $cell = $gridRow.find('[data-fieldname="serial_nos"]');
            if (!$cell.length) return;

            const count = _parse_serials(row.serial_nos || "").length;
            const isDraft = frm.doc.docstatus === 0;

            if (isDraft) {
                $cell.html(`
					<div class="dispatch-serial-badge" style="
						cursor:pointer;
						display:inline-flex;
						align-items:center;
						gap:6px;
						padding:4px 12px;
						background:${count > 0 ? '#eef2ff' : '#f9fafb'};
						border:1px solid ${count > 0 ? '#818cf8' : '#d1d5db'};
						border-radius:20px;
						font-size:12px;
						font-weight:600;
						color:${count > 0 ? '#4338ca' : '#6b7280'};
						white-space:nowrap;
					">
						${count > 0 ? '📋' : '➕'}
						${count > 0 ? count + ' serial' + (count !== 1 ? 's' : '') + ' — click to manage' : 'Click to scan serials'}
					</div>
				`);

                $cell.off("click.dispatch").on("click.dispatch", (e) => {
                    e.stopPropagation();
                    _open_serial_dialog(frm, row.name, row.item_code);
                });
            } else {
                // Submitted — just show the count
                $cell.html(`
					<span style="font-size:12px;color:#6b7280;">
						${count > 0 ? '📋 ' + count + ' serials logged' : '—'}
					</span>
				`);
                if (count > 0) {
                    $cell.css("cursor", "pointer").off("click.dispatch").on("click.dispatch", (e) => {
                        e.stopPropagation();
                        _open_serial_dialog(frm, row.name, row.item_code);
                    });
                }
            }
        });
    }, 250);
}

// ---------------------------------------------------------------
// The Serial Management Dialog
// ---------------------------------------------------------------

function _open_serial_dialog(frm, row_name, item_code) {
    const product_row = (frm.doc.products || []).find((r) => r.name === row_name);
    if (!product_row) return;

    let serials = _parse_serials(product_row.serial_nos || "");
    const isReadonly = frm.doc.docstatus !== 0;

    const dialog = new frappe.ui.Dialog({
        title: `Serial Numbers — ${item_code || "Select Item First"}`,
        size: "large",
        fields: [
            {
                fieldname: "info_section",
                fieldtype: "HTML",
                options: `<div id="sn-dialog-root"></div>`,
            },
        ],
        primary_action_label: isReadonly ? "Close" : "Save & Close",
        primary_action() {
            if (!isReadonly) {
                const updated = _get_dialog_serials();
                frappe.model.set_value("Dispatch Product", row_name, "serial_nos", updated.join("\n"));
                frappe.model.set_value("Dispatch Product", row_name, "qty", updated.length);
                _refresh_totals(frm);
                frm.dirty();
                setTimeout(() => _render_serial_cells(frm), 300);
            }
            dialog.hide();
        },
    });

    dialog.show();

    const $root = dialog.$wrapper.find("#sn-dialog-root");
    _render_serial_ui($root, serials, item_code, isReadonly);

    function _get_dialog_serials() {
        const result = [];
        $root.find(".sn-row[data-sn]").each(function () {
            result.push($(this).attr("data-sn"));
        });
        return result;
    }
}

function _render_serial_ui($root, initialSerials, item_code, isReadonly) {
    let serials = [...initialSerials];

    function render() {
        const q = ($root.find("#sn-search").val() || "").trim().toUpperCase();
        const filtered = q ? serials.filter((s) => s.toUpperCase().includes(q)) : serials;

        $root.empty();
        $root.append(`
			<div style="padding:12px 0 4px;">
				${!isReadonly ? `
				<!-- Scan bar -->
				<div style="display:flex;gap:10px;align-items:center;margin-bottom:12px;flex-wrap:wrap;">
					<input
						id="sn-scan-input"
						type="text"
						placeholder="🔫 Scan or type serial number + Enter"
						autocomplete="off" autocorrect="off" spellcheck="false"
						style="flex:1;min-width:200px;padding:8px 14px;border:2px solid #818cf8;border-radius:8px;font-size:14px;font-weight:500;"
					/>
					<span style="font-size:13px;color:#6b7280;white-space:nowrap;">
						Total: <strong>${serials.length}</strong>
					</span>
				</div>
				<div id="sn-last-feedback" style="min-height:20px;margin-bottom:8px;font-size:12px;"></div>
				` : `
				<div style="margin-bottom:12px;font-size:13px;color:#6b7280;">
					Showing <strong>${serials.length}</strong> logged serial numbers (read-only after submission).
				</div>
				`}

				<!-- Search bar -->
				<input
					id="sn-search"
					type="text"
					placeholder="🔍 Search serial number…"
					value="${q || ''}"
					style="width:100%;padding:6px 12px;border:1px solid #e5e7eb;border-radius:6px;font-size:12px;margin-bottom:10px;"
				/>

				<!-- Table -->
				<div style="max-height:400px;overflow-y:auto;border:1px solid #e5e7eb;border-radius:8px;">
					<table style="width:100%;border-collapse:collapse;font-size:13px;">
						<thead>
							<tr style="background:#f9fafb;position:sticky;top:0;z-index:1;">
								<th style="padding:8px 12px;text-align:left;border-bottom:1px solid #e5e7eb;width:50px;">#</th>
								<th style="padding:8px 12px;text-align:left;border-bottom:1px solid #e5e7eb;">Serial Number</th>
								${!isReadonly ? '<th style="padding:8px 12px;text-align:center;border-bottom:1px solid #e5e7eb;width:70px;">Delete</th>' : ''}
							</tr>
						</thead>
						<tbody>
							${filtered.length === 0
                ? `<tr><td colspan="3" style="text-align:center;padding:28px;color:#9ca3af;">
									${serials.length > 0 ? 'No serials match your search' : 'No serials yet — start scanning above'}</td></tr>`
                : filtered.map((sn) => `
									<tr class="sn-row" data-sn="${frappe.utils.escape_html(sn)}"
										style="border-bottom:1px solid #f3f4f6;">
										<td style="padding:6px 12px;color:#9ca3af;">${serials.indexOf(sn) + 1}</td>
										<td style="padding:6px 12px;font-family:monospace;font-size:13px;">${frappe.utils.escape_html(sn)}</td>
										${!isReadonly ? `<td style="padding:6px 12px;text-align:center;">
											<button class="btn btn-xs btn-danger sn-delete-btn"
												data-sn="${frappe.utils.escape_html(sn)}"
												style="border-radius:6px;padding:1px 8px;font-size:11px;">✕</button>
										</td>` : ''}
									</tr>
								`).join("")
            }
						</tbody>
					</table>
				</div>
			</div>
		`);

        // ---- Scan input handlers (only on draft) ----
        if (!isReadonly) {
            let scanTimer;
            const $scanInput = $root.find("#sn-scan-input");

            $scanInput
                .on("keydown", function (e) {
                    if (e.key === "Enter") {
                        e.preventDefault();
                        _add_serial($(this).val().trim());
                        $(this).val("").focus();
                    }
                })
                .on("input", function () {
                    clearTimeout(scanTimer);
                    const val = $(this).val().trim();
                    scanTimer = setTimeout(() => {
                        if (val.length >= 6) {
                            _add_serial(val);
                            $(this).val("").focus();
                        }
                    }, 150);
                });

            // Auto-focus the scan input
            setTimeout(() => $scanInput.focus(), 100);
        }

        // ---- Search: live filter ----
        $root.find("#sn-search").on("input", () => render());

        // ---- Delete buttons ----
        if (!isReadonly) {
            $root.find(".sn-delete-btn").on("click", function () {
                const sn = $(this).attr("data-sn");
                serials = serials.filter((s) => s !== sn);
                $root.find("#sn-last-feedback").html(
                    `<span style="color:#ef4444;">🗑 Removed: <b>${sn}</b></span>`
                );
                render();
            });
        }
    }

    function _add_serial(sn) {
        if (!sn) return;

        // Smart Scan Validation
        const mergedWarning = _detect_merged_serial(sn, serials);
        if (mergedWarning) {
            _play_audio_tone("error");
            frappe.show_alert({ message: `<b>Merged Scan Error:</b><br>${mergedWarning}`, indicator: "red" }, 5);
            $root.find("#sn-last-feedback").html(
                `<span style="color:#ef4444;font-size:13px;">❌ <b>Rejected:</b> ${sn} (${mergedWarning})</span>`
            );

            // Visual error feedback on the input box
            const $input = $root.find("#sn-scan-input");
            $input.css({ "background-color": "#fee2e2", "border-color": "#ef4444" });
            setTimeout(() => $input.css({ "background-color": "", "border-color": "#818cf8" }), 800);
            return;
        }

        if (serials.findIndex((s) => s.toUpperCase() === sn.toUpperCase()) !== -1) {
            _play_audio_tone("error");
            frappe.show_alert({ message: `Duplicate skipped: <b>${sn}</b>`, indicator: "orange" }, 3);
            $root.find("#sn-last-feedback").html(
                `<span style="color:#f59e0b;">⚠ Duplicate: <b>${sn}</b> already in list</span>`
            );
            return;
        }

        serials.push(sn);
        _play_audio_tone("success");
        frappe.show_alert({ message: `✓ Added: <b>${sn}</b>`, indicator: "green" }, 2);
        $root.find("#sn-last-feedback").html(
            `<span style="color:#22c55e;">✓ Added: <b>${sn}</b></span>`
        );
        render();
    }

    render();
}

// ---------------------------------------------------------------
// Processing status banner
// ---------------------------------------------------------------

function _show_processing_banner(frm) {
    const status = frm.doc.processing_status || "Pending";
    const msgs = {
        "Pending": "⏳ Waiting to be queued for background processing…",
        "In Queue": "⚙️ Processing serials in background — this page refreshes every 5 seconds automatically.",
        "Processed": `✅ Done! All ${frm.doc.total_qty} serial numbers have been registered/updated in the system.`,
        "Failed": '❌ Processing failed — click "Retry Processing" to try again, or check <b>Error Log</b> for details.',
    };
    const colors = { "Pending": "yellow", "In Queue": "yellow", "Processed": "green", "Failed": "red" };

    frm.dashboard.add_comment(msgs[status], colors[status] || "yellow", true);
}
