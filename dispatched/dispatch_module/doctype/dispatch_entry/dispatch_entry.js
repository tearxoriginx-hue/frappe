// Copyright (c) 2026, Varun and contributors
// For license information, please see license.txt

// ===============================================================
// Helper functions — defined FIRST so they exist when form loads
// ===============================================================

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
        let row_qty = _parse_serials(row.serial_nos || "").length;
        if (row.qty !== row_qty) {
            frappe.model.set_value(row.doctype, row.name, "qty", row_qty);
        }
        total += row_qty;
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

function _render_serial_cells(frm) {
    if (!frm.doc.products || !frm.fields_dict || !frm.fields_dict.products) return;
    const grid = frm.fields_dict.products.grid;
    frm.doc.products.forEach((row) => {
        if (!row.serial_nos) return;
        const grid_row = grid.grid_rows.find(r => r.doc && r.doc.name === row.name);
        if (!grid_row) return;
        const serials = _parse_serials(row.serial_nos);
        if (serials.length === 0) return;
        const $cell = $(grid_row.wrapper).find("[data-fieldname=serial_nos]");
        if (!$cell.length) return;
        let html = "<div style=\"display: flex; flex-wrap: wrap; gap: 3px; max-height: 150px; overflow-y: auto; cursor: pointer;\">";
        serials.forEach((sn) => {
            html += "<span class=\"badge badge-info\" style=\"font-size: 10px; padding: 1px 5px; pointer-events: none;\">" + sn + "</span>";
        });
        html += "</div>";
        try {
            if ($cell.html().trim() !== html.trim()) {
                $cell.html(html);
            }
        } catch(e) {}
    });
}

function _play_audio_tone(type) {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        if (type === "success") {
            osc.type = "sine";
            osc.frequency.setValueAtTime(600, ctx.currentTime);
            osc.frequency.setValueAtTime(900, ctx.currentTime + 0.1);
            gain.gain.setValueAtTime(0.1, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.2);
            osc.start();
            osc.stop(ctx.currentTime + 0.2);
        } else if (type === "error") {
            osc.type = "sawtooth";
            osc.frequency.setValueAtTime(150, ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(80, ctx.currentTime + 0.3);
            gain.gain.setValueAtTime(0.3, ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
            osc.start();
            osc.stop(ctx.currentTime + 0.3);
        }
    } catch (e) {}
}

function _detect_merged_serial(new_sn) {
    // Check 1: Extremely long string = definitely merged
    if (new_sn.length > 40) {
        return "⚠️ Serial number too long (" + new_sn.length + " chars) — possible merged scan?";
    }
    // Check 2: Multiple groups matching typical serial pattern (e.g., SN001, ABC123)
    // Looks for letter-prefix + number combo, repeated
    const groups = new_sn.match(/[A-Z]{2,}\d+/g);
    if (groups && groups.length > 1) {
        return "⚠️ Possible merged scan: detected " + groups.join(", ");
    }
    // Check 3: Multiple alphanumeric clusters (handles mixed formats like ABC-123-XYZ)
    const clusters = new_sn.match(/[A-Z0-9]{3,}/g);
    if (clusters && clusters.length > 2) {
        return "⚠️ Possible merged scan with " + clusters.length + " clusters";
    }
    // Check 4: Has separator patterns that suggest multiple items
    if ((new_sn.match(/[\-\/\|,;]/g) || []).length > 1) {
        return "⚠️ Multiple separators found — possible merged list?";
    }
    return null;
}

function _show_processing_banner(frm) {
    const status = frm.doc.processing_status || "Pending";
    const msgs = {
        "Pending": "⏳ Waiting to be queued for background processing\u2026",
        "In Queue": "⚙️ Processing serials in background \u2014 this page refreshes every 5 seconds automatically.",
        "Processed": "✅ Done! All " + frm.doc.total_qty + " serial numbers have been registered/updated in the system.",
        "Failed": "❌ Processing failed \u2014 click \"Retry Processing\" to try again, or check <b>Error Log</b> for details.",
    };
    const colors = { "Pending": "yellow", "In Queue": "yellow", "Processed": "green", "Failed": "red" };
    frm.dashboard.add_comment(msgs[status], colors[status] || "yellow", true);
}

function _setup_serial_click_handler(frm) {
    if (frm.fields_dict.products && frm.fields_dict.products.grid) {
        var $grid = $(frm.fields_dict.products.grid.wrapper);
        $grid.off("click.dispatch", "[data-fieldname=serial_nos]");
        $grid.on("click.dispatch", "[data-fieldname=serial_nos]", function(e) {
            if (frm.doc.docstatus !== 0) return;
            var $row = $(this).closest(".grid-row");
            var row_name = $row.attr("data-name");
            var row = (frm.doc.products || []).find(r => r.name === row_name);
            if (row) {
                e.stopPropagation();
                _open_serial_dialog(frm, row.name, row.item_code);
            }
        });
    }
}

function _open_serial_dialog(frm, row_name, item_code) {
    // Guard: reuse if already open for same row
    if (frm._serial_dlg && frm._serial_dlg.row_name === row_name) {
        frm._serial_dlg.dialog.show();
        return;
    }
    if (frm._serial_dlg) {
        frm._serial_dlg.dialog.hide();
    }

    const row = frappe.model.get_doc("Dispatch Product", row_name);
    const existing = _parse_serials(row.serial_nos || "");
    // serials is the SINGLE source of truth
    const serials = [...existing];

    const d = new frappe.ui.Dialog({
        title: "Scan Serial Numbers",
        fields: [
            {
                fieldtype: "Data",
                fieldname: "scan_input",
                label: "Item: " + item_code,
                description: "Scan or type a serial number, then press Enter"
            },
            {
                fieldtype: "HTML",
                fieldname: "badge_list"
            },
        ],
        primary_action_label: "Save & Close",
        primary_action: () => {
            frm._serial_dlg = null;
            _render_serial_cells(frm);
            _refresh_totals(frm);
            d.hide();
        },
    });

    frm._serial_dlg = { dialog: d, row_name: row_name };
    d.onhide = function() {
        frm._serial_dlg = null;
    };

    d.show();

    // Real-time badge renderer inside the dialog
    function _render_dlg_badges() {
        let html = "<div style=\"display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px; max-height: 200px; overflow-y: auto;\">";
        serials.forEach((sn, idx) => {
            html += "<span class=\"badge badge-info\" style=\"padding: 4px 8px; font-size: 12px; margin: 2px;\">"
                + sn
                + " <a class=\"sn-remove\" data-idx=\"" + idx + "\" style=\"margin-left: 6px; cursor: pointer; font-weight: bold; color: #fff; opacity: 0.7; text-decoration: none;\">&times;</a>"
                + "</span>";
        });
        html += "</div>";
        d.fields_dict.badge_list.$wrapper.html(html);

        // Bind remove handlers
        d.$wrapper.find(".sn-remove").on("click", function() {
            const idx = parseInt($(this).data("idx"));
            serials.splice(idx, 1);
            _render_dlg_badges();
            _play_audio_tone("success");
            // Update child table in real-time
            frappe.model.set_value("Dispatch Product", row_name, "serial_nos", serials.join("\n"));
            _render_serial_cells(frm);
            _refresh_totals(frm);
        });
    }

    // ============================================================
    // Smart Matrix: Validate serial batch for anomalies
    // ============================================================
    function _validate_serial_matrix() {
        if (serials.length < 2) return;
        const warnings = [];

        // --- Check 1: Length consistency ---
        const lengthCounts = {};
        serials.forEach(s => {
            const len = s.length;
            lengthCounts[len] = (lengthCounts[len] || 0) + 1;
        });
        const mostCommonLen = Object.keys(lengthCounts).reduce(
            (a, b) => lengthCounts[a] > lengthCounts[b] ? a : b
        );
        const unusual = serials.filter(s => s.length !== parseInt(mostCommonLen));
        if (unusual.length > 0 && unusual.length < serials.length / 2) {
            const showUnusual = unusual.slice(0, 5).join(", ");
            const extra = unusual.length > 5 ? "...and " + (unusual.length - 5) + " more" : "";
            warnings.push("⚠️ " + unusual.length + " serial(s) have unusual length (expected " + mostCommonLen + " chars): " + showUnusual + extra);
        }

        // --- Check 2: Prefix pattern detection ---
        const prefixes = {};
        serials.forEach(s => {
            const match = s.match(/^([A-Z]+)/);
            if (match) {
                const prefix = match[1];
                prefixes[prefix] = (prefixes[prefix] || 0) + 1;
            }
        });
        const prefixKeys = Object.keys(prefixes);
        if (prefixKeys.length > 1) {
            const mainPrefix = prefixKeys.reduce((a, b) => prefixes[a] > prefixes[b] ? a : b);
            const outliers = prefixKeys.filter(p => p !== mainPrefix);
            warnings.push("⚠️ Multiple prefixes detected: " + outliers.join(", ") + " (majority: " + mainPrefix + ")");
        }

        // --- Check 3: Duplicate-ish detection (skip for large batches) ---
        if (serials.length <= 200) {
            for (let i = 0; i < serials.length; i++) {
                for (let j = i + 1; j < serials.length; j++) {
                    const s1 = serials[i], s2 = serials[j];
                    if (s1.length > 3 && s2.length > 3) {
                        if (s1.includes(s2) || s2.includes(s1)) {
                            warnings.push("⚠️ Possible duplicate/mis-scan: " + s1 + " contains/in " + s2);
                            break;
                        }
                    }
                }
                if (warnings.length > 3) break;
            }
        } else {
            warnings.push("ℹ️ Batch too large (" + serials.length + ") — skipping duplicate-ish check");
        }

        // --- Check 4: Sequential gap detection ---
        const numberedSerials = serials
            .map(s => {
                const match = s.match(/^(.*[A-Za-z])(\d+)$/);
                return match ? { prefix: match[1].toUpperCase(), num: parseInt(match[2]) } : null;
            })
            .filter(x => x !== null);
        const groups = {};
        numberedSerials.forEach(x => {
            if (!groups[x.prefix]) groups[x.prefix] = [];
            groups[x.prefix].push(x.num);
        });
        for (const [prefix, nums] of Object.entries(groups)) {
            if (nums.length < 3) continue;
            nums.sort((a, b) => a - b);
            for (let i = 1; i < nums.length; i++) {
                if (nums[i] - nums[i-1] > 1) {
                    for (let missing = nums[i-1] + 1; missing < nums[i]; missing++) {
                        warnings.push("⚠️ Possible gap: " + prefix + missing + " is missing");
                        if (warnings.length >= 6) break;
                    }
                }
                if (warnings.length >= 6) break;
            }
            if (warnings.length >= 6) break;
        }

        // Show warnings if any
        if (warnings.length > 0) {
            const display = warnings.slice(0, 4);
            if (warnings.length > 4) {
                display.push("...and " + (warnings.length - 4) + " more warnings");
            }
            frappe.show_alert({
                message: "<b>Serial Validation:</b><br>" + display.join("<br>"),
                indicator: "orange"
            });
        }
    }

    // Find the scan input field
    const $input = d.$wrapper.find("[data-fieldname=scan_input] input");

    // Shared handler for both Enter and paste
    function _add_serials_from_text(text) {
        const parts = text.split(/[\n,;\t| ]+/).filter(s => s.trim());
        let added = 0;
        let last_added = "";

        for (const part of parts) {
            const sn = part.trim().toUpperCase();
            if (!sn) continue;
            if (serials.includes(sn)) {
                frappe.show_alert({ message: "Already added: " + sn, indicator: "orange" });
                _play_audio_tone("error");
                continue;
            }
            const warning = _detect_merged_serial(sn);
            if (warning) {
                frappe.show_alert({ message: warning, indicator: "orange" });
                _play_audio_tone("error");
                continue;
            }
            serials.push(sn);
            added++;
            last_added = sn;
        }

        if (added > 0) {
            _render_dlg_badges();
            _play_audio_tone("success");
            // Update child table in REAL TIME
            frappe.model.set_value("Dispatch Product", row_name, "serial_nos", serials.join("\n"));
            _render_serial_cells(frm);
            _refresh_totals(frm);
        }
        // Run smart matrix validation after batch
        if (added > 0) {
            _validate_serial_matrix();
        } else if (serials.length > 0) {
            // Re-validate even if nothing new added (clears stale warnings)
            _validate_serial_matrix();
        }
        return added;
    }

    // Enter key = single scan/type (also handle Tab for scanners configured with tab suffix)
    $input.on("keydown", function(e) {
        if (e.key === "Enter" || e.key === "Tab") {
            if (e.key === "Tab") e.preventDefault();
            const text = $(this).val();
            if (_add_serials_from_text(text) > 0) {
                $(this).val("");
            } else {
                $(this).val("");
            }
        }
    });

    // Paste = handle batch (split by newline)
    $input.on("paste", function() {
        setTimeout(() => {
            const text = $(this).val();
            if (_add_serials_from_text(text) > 0) {
                $(this).val("");
            }
        }, 0);
    });

    // Input event — detect trailing space/tab (barcode scanner with space suffix)
    $input.on("input", function() {
        const val = $(this).val();
        if (val.endsWith(" ") || val.endsWith("\t")) {
            _add_serials_from_text(val.trim());
            $(this).val("");
        }
    });

    // Initial render of existing badges
    _render_dlg_badges();
    // Validate existing serials on dialog open
    _validate_serial_matrix();
}

// ===============================================================
// Form events
// ===============================================================

frappe.ui.form.on("Dispatch Entry", {

    refresh(frm) {
        _lock_readonly_fields(frm);

        if (frm.is_new() && !frm.doc.branch) {
            frappe.call({
                method: "dispatched.dispatch_module.doctype.dispatch_entry.dispatch_entry.get_user_branch",
                callback: (r) => {
                    if (r.message && r.message.branch) {
                        frm.set_value("branch", r.message.branch);
                        frm.set_df_property("branch", "read_only", 1);
                    }
                },
            });
        } else if (frm.doc.branch) {
            frm.set_df_property("branch", "read_only", 1);
        }

        if (frm.is_new() && !frm.doc.company) {
            frappe.call({
                method: "dispatched.dispatch_module.doctype.dispatch_entry.dispatch_entry.get_user_company",
                callback: (r) => {
                    if (r.message && r.message.company) {
                        frm.set_value("company", r.message.company);
                        frm.set_df_property("company", "read_only", 1);
                    }
                },
            });
        } else if (frm.doc.company) {
            frm.set_df_property("company", "read_only", 1);
        }

        _setup_serial_click_handler(frm);
        _render_serial_cells(frm);

        if (!frm.is_new()) {
            _show_processing_banner(frm);
            if (["In Queue", "Pending"].includes(frm.doc.processing_status)) {
                clearInterval(frm._refresh_interval);
                frm._refresh_interval = setInterval(() => frm.reload_doc(), 5000);
            } else {
                clearInterval(frm._refresh_interval);
            }
        }

        if (!frm.is_new() && frm.doc.processing_status === "Failed") {
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
        if (!row.item_code) {
            row._last_item_code = null;
            return;
        }

        if (row._last_item_code === row.item_code) return;
        row._last_item_code = row.item_code;

        frappe.db.get_value("Item", row.item_code, ["warranty_period_days", "item_name"], (r) => {
            frappe.model.set_value(cdt, cdn, "warranty_period_days", r.warranty_period_days || 0);
            frappe.model.set_value(cdt, cdn, "item_name", r.item_name || "");
            _calculate_expiry(frm, cdt, cdn);

            if (frm.doc.docstatus === 0 && frm._dlg_scheduled !== row.name) {
                frm._dlg_scheduled = row.name;
                setTimeout(() => {
                    frm._dlg_scheduled = null;
                    _open_serial_dialog(frm, row.name, row.item_code);
                }, 100);
            }
        });
    },

    serial_nos(frm, cdt, cdn) {
        if (frm.doc.docstatus !== 0) return;
        _render_serial_cells(frm);
        _refresh_totals(frm);
    },

    products_add(frm, cdt, cdn) {
        setTimeout(() => _render_serial_cells(frm), 300);
    },

    products_remove(frm) {
        _refresh_totals(frm);
    },
});
