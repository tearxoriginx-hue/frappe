import frappe
from frappe.utils import nowdate, add_days, add_months, getdate, get_datetime, now
from frappe import _


@frappe.whitelist()
def daily_overdue_alerts():
    """
    Daily scheduler:
    - Find RMAs in 'Processing' for > 3 days
    - Notify relevant managers via email
    - Log success/failure
    """
    overdue_date = add_days(nowdate(), -3)

    overdue_rmas = frappe.db.sql(
        """
        SELECT r.name, r.status, r.branch, r.rma_type, e.user_id, r.modified
        FROM `tabRMA Request` r
        LEFT JOIN `tabEmployee` e ON e.branch = r.branch AND e.designation = 'RMA Manager'
        WHERE r.status = 'Processing'
          AND r.modified < %s
    """,
        (overdue_date,),
        as_dict=True,
    )

    if not overdue_rmas:
        frappe.logger().info("No overdue RMAs found today.")
        return

    for rma in overdue_rmas:
        try:
            if rma.user_id:
                frappe.sendmail(
                    recipients=[rma.user_id],
                    subject=f"Overdue RMA Alert: {rma.name}",
                    message=f"""<p>The following RMA is overdue:</p>
                    <ul>
                        <li><b>RMA ID:</b> {rma.name}</li>
                        <li><b>Status:</b> {rma.status}</li>
                        <li><b>Branch:</b> {rma.branch}</li>
                        <li><b>Type:</b> {rma.rma_type}</li>
                        <li><b>Last Modified:</b> {rma.modified}</li>
                    </ul>
                    <p>Please take action.</p>""",
                )
                frappe.logger().info(f"Overdue alert sent for {rma.name} to {rma.user_id}")
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Failed to send overdue alert for {rma.name}")


def auto_archive_old_rmas():
    """
    Monthly scheduler:
    - Set is_archived=1 for RMAs completed > N months ago
    """
    try:
        settings = frappe.get_single("RMA Settings")
        months = getattr(settings, "auto_archive_months", 12) or 12
        cutoff = add_months(nowdate(), -months)

        frappe.db.sql(
            """
            UPDATE `tabRMA Request`
            SET is_archived = 1
            WHERE is_archived = 0
              AND status IN ('Repaired', 'Replaced', 'Cancelled')
              AND completed_date < %s
        """,
            (cutoff,),
        )

        frappe.logger().info(f"Auto-archive completed for RMAs older than {months} months")
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Auto-archive RMA failed")
