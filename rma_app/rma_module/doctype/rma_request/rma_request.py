import os
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, nowdate, add_days, getdate


class RMARequest(Document):
    def autoname(self):
        """Generate readable names: RMA-DELHI-05-03-26-0001"""
        branch_code = (self.branch or "GEN").upper().replace(" ", "")[:6]
        posting = self.posting_date or nowdate()
        date_str = frappe.utils.formatdate(posting, "dd-MM-yy")
        prefix = f"RMA-{branch_code}-{date_str}-"
        self.name = frappe.model.naming.make_autoname(prefix + ".####")

    def validate(self):
        if self.serial_no:
            serial_doc = frappe.get_doc("Serial No", self.serial_no)
            if not self.item_code:
                self.item_code = serial_doc.item_code
            if not self.item_name:
                self.item_name = serial_doc.item_name
            if not self.customer:
                self.customer = serial_doc.customer
            if not self.branch:
                self.branch = serial_doc.branch
            if not self.company:
                self.company = serial_doc.company
            if self.customer and not self.customer_name:
                self.customer_name = frappe.db.get_value("Customer", self.customer, "customer_name")
        self.set_warranty_status()
        self.validate_branch_access()
        self.validate_invoice_image()
        if not self.posting_date:
            self.posting_date = nowdate()

        if self.is_new():
            if self.rma_type == "Repair":
                self.status = "Processing"
            elif self.rma_type == "Replacement":
                self.validate_replacement_serial()
                self.validate_buffer_warranty()
                if not self.replacement_serial_no:
                    frappe.throw(_("Replacement serial number is required for Replacement RMA"))
                self.status = "Replaced"
                self.completed_date = now_datetime()
                self.replacement_date = now_datetime()
        else:
            if self.rma_type == "Replacement" and self.replacement_serial_no:
                self.validate_replacement_serial()

    def after_insert(self):
        if self.rma_type == "Repair":
            self._log_activity("Created", "", "Processing", "Repair RMA created")
        elif self.rma_type == "Replacement":
            self._log_activity("Created", "", "Replaced", "Replacement completed")
            self.update_serial_statuses()
            self.replacement_item_code = self.item_code
            self.db_set("replacement_item_code", self.replacement_item_code)

    def set_warranty_status(self):
        if self.warranty_expiry:
            if getdate(self.warranty_expiry) >= getdate(nowdate()):
                self.warranty_status = "In Warranty"
            else:
                self.warranty_status = "Out of Warranty"

    def before_print(self, print_settings=None):
        if self.customer:
            contact = frappe.db.get_value("Customer", self.customer, ["email_id", "mobile_no"], as_dict=True)
            if contact:
                self.customer_phone = contact.mobile_no or ""
                self.customer_email = contact.email_id or ""

    def validate_branch_access(self):
        user = frappe.session.user
        if "RMA Manager" in frappe.get_roles(user) or "System Manager" in frappe.get_roles(user):
            return
        employee = frappe.db.get_value("Employee", {"user_id": user}, "branch")
        if employee and self.branch and self.branch != employee:
            frappe.throw(_("You can only create RMA requests for your own branch: {0}").format(employee))

    def validate_replacement_serial(self):
        if self.rma_type == "Replacement" and self.replacement_serial_no:
            existing = frappe.db.exists("RMA Request", {
                "replacement_serial_no": self.replacement_serial_no,
                "status": "Replaced",
                "name": ("!=", self.name),
            })
            if existing:
                frappe.throw(_("Serial {0} is already used in another replacement RMA").format(self.replacement_serial_no))

    def validate_buffer_warranty(self):
        """Validate buffer warranty requirements on save."""
        if self.rma_type != "Replacement":
            return
        if self.warranty_status != "Out of Warranty":
            return
        settings = frappe.get_single("RMA Settings")
        if not settings.allow_buffer_warranty:
            frappe.throw(_("Replacement is only allowed for items within warranty period OR through Buffer Warranty (contact manager)"))
        if not self.buffer_warranty:
            frappe.throw(_("This item is out of warranty. Please enable 'Buffer Warranty' to proceed with replacement (customer invoice required)."))
        if not self.invoice_image:
            frappe.throw(_("Please upload the customer's invoice/bill image for manager verification."))

    def validate_invoice_image(self):
        if self.invoice_image:
            allowed = [".pdf", ".jpg", ".jpeg", ".png", ".webp"]
            ext = os.path.splitext(self.invoice_image)[-1].lower()
            if ext not in allowed:
                frappe.throw(_("Only PDF or Image (JPG, PNG, WEBP) files are allowed for invoice upload. Got: {0}").format(ext))

    def _log_activity(self, action, from_status, to_status, notes=""):
        """Append an audit log entry"""
        self.append("audit_log", {
            "date": now_datetime(),
            "user": frappe.session.user,
            "action": action,
            "from_status": from_status,
            "to_status": to_status,
            "notes": notes,
        })

    def update_serial_statuses(self):
        """
        Update serial number statuses for replacement:
        - Original serial (returned by customer): no status change, kept as-is for record
        - Replacement serial: auto-created if new, or updated if existing
        - Replacement serial gets fresh warranty as a new item
        """
        if not self.replacement_serial_no:
            return

        if not frappe.db.exists("Serial No", self.replacement_serial_no):
            # Replacement serial doesn't exist — auto-create it with fresh warranty
            warranty_days = frappe.db.get_value("Item", self.item_code, "warranty_period_days") or                             frappe.get_single("RMA Settings").default_warranty_days or 365

            new_serial = frappe.get_doc({
                "doctype": "Serial No",
                "serial_no": self.replacement_serial_no,
                "item_code": self.item_code,
                "item_name": self.item_name,
                "customer": self.customer,
                "branch": self.branch,
                "company": self.company,
                "warranty_period_days": warranty_days,
                "warranty_expiry_date": add_days(nowdate(), warranty_days),
                "status": "Active",
            })
            new_serial.insert(ignore_permissions=True)
        else:
            # Replacement serial exists — validate and update
            new_serial = frappe.get_doc("Serial No", self.replacement_serial_no)
            if new_serial.status not in ("Active", "In Store"):
                frappe.throw(_("Replacement serial {0} is not available. Status: {1}").format(
                    self.replacement_serial_no, new_serial.status
                ))

            # Assign replacement serial to customer
            new_serial.customer = self.customer
            new_serial.branch = self.branch
            new_serial.company = self.company
            new_serial.status = "Active"
            new_serial.save(ignore_permissions=True)


@frappe.whitelist()
def get_serial_details(serial_no):
    serial = frappe.get_doc("Serial No", serial_no)
    item = frappe.get_cached_doc("Item", serial.item_code)

    # Read warranty_days from serial stored value first (frozen at dispatch time)
    warranty_days = serial.warranty_period_days or item.warranty_period_days or frappe.get_single("RMA Settings").default_warranty_days or 365

    # Calculate sale_date from warranty data so all 3 fields are internally consistent
    if serial.warranty_expiry_date and serial.warranty_period_days:
        sale_date = add_days(serial.warranty_expiry_date, -serial.warranty_period_days)
    else:
        sale_date = getdate(serial.creation)

    return {
        "item_code": serial.item_code,
        "item_name": serial.item_name,
        "customer": serial.customer,
        "customer_name": frappe.db.get_value("Customer", serial.customer, "customer_name") if serial.customer else "",
        "branch": serial.branch,
        "company": serial.company,
        "sale_date": sale_date,
        "warranty_expiry": serial.warranty_expiry_date,
        "warranty_status": "In Warranty" if serial.warranty_expiry_date and getdate(serial.warranty_expiry_date) >= getdate(nowdate()) else "Out of Warranty",
        "warranty_days": warranty_days,
    }


@frappe.whitelist()
def mark_completed(docname):
    frappe.has_permission("RMA Request", "write", throw=True)
    doc = frappe.get_doc("RMA Request", docname)
    if doc.rma_type != "Repair":
        frappe.throw(_("Only Repair type RMA can be marked completed this way"))
    if doc.status != "Processing":
        frappe.throw(_("Only RMA in 'Processing' status can be marked as repaired"))
    doc.status = "Repaired"
    doc.completed_date = now_datetime()
    doc._log_activity("Completed", "Processing", "Repaired", "Repair completed")
    doc.save(ignore_permissions=True)
    return doc.status


@frappe.whitelist()
def cancel_rma(docname):
    frappe.has_permission("RMA Request", "write", throw=True)
    doc = frappe.get_doc("RMA Request", docname)
    if doc.status == "Cancelled":
        frappe.throw(_("RMA is already cancelled"))
    old_status = doc.status
    doc.status = "Cancelled"
    doc._log_activity("Cancelled", old_status, "Cancelled", "RMA cancelled by user")
    doc.save(ignore_permissions=True)
    return doc.status


@frappe.whitelist()
def share_rma_via_email(docname, recipient_email=None):
    """Send an email to the customer with RMA status details."""
    doc = frappe.get_doc("RMA Request", docname)

    if not recipient_email:
        if doc.customer:
            recipient_email = frappe.db.get_value("Customer", doc.customer, "email_id")
        if not recipient_email:
            frappe.throw(_("No customer email found. Please provide a recipient email address."))

    subject = f"RMA Update: {doc.name} - {doc.status}"

    from frappe.www.printview import get_rendered_template, get_print_format_doc
    pf = get_print_format_doc("RMA", meta=doc.meta)
    if pf:
        message = get_rendered_template(doc=doc, print_format=pf, meta=doc.meta, no_letterhead=1)
    else:
        message = f"<h3>RMA {doc.name}</h3><p>Status: {doc.status}</p>"

    try:
        frappe.sendmail(
            recipients=[recipient_email],
            subject=subject,
            message=message,
            reference_doctype="RMA Request",
            reference_name=doc.name,
        )
        doc._log_activity("Email Sent", doc.status, doc.status, f"RMA status emailed to {recipient_email}")
        doc.save(ignore_permissions=True)
        return {"success": True, "message": f"RMA details emailed to {recipient_email}", "recipient": recipient_email}
    except Exception as e:
        frappe.log_error(f"Failed to send RMA email for {docname}: {str(e)}")
        frappe.throw(_("Failed to send email: {0}").format(str(e)))


@frappe.whitelist()
def get_customer_contact(customer):
    if not customer:
        return {"email_id": "", "mobile_no": ""}
    fields = frappe.db.get_value("Customer", customer, ["email_id", "mobile_no"], as_dict=True)
    return fields or {"email_id": "", "mobile_no": ""}


@frappe.whitelist()
def get_rma_email_preview(docname):
    """Get a preview of the RMA email content for the client to review before sending."""
    doc = frappe.get_doc("RMA Request", docname)
    customer_email = frappe.db.get_value("Customer", doc.customer, "email_id") if doc.customer else ""
    return {
        "name": doc.name,
        "status": doc.status,
        "rma_type": doc.rma_type,
        "customer": doc.customer,
        "customer_name": doc.customer_name,
        "customer_email": customer_email,
        "item_code": doc.item_code,
        "item_name": doc.item_name,
        "serial_no": doc.serial_no,
        "warranty_status": doc.warranty_status,
        "repair_notes": doc.repair_notes,
        "replacement_serial_no": doc.replacement_serial_no,
        "completed_date": str(doc.completed_date) if doc.completed_date else None,
    }
