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
        self.set_warranty_status()
        self.validate_branch_access()
        self.validate_replacement_serial()
        self.validate_buffer_warranty()
        self.validate_invoice_image()

    def before_insert(self):
        self.posting_date = nowdate()

    def on_submit(self):
        if self.rma_type == "Repair":
            self.status = "In Repair"
            self._log_activity("Submitted", "Draft", "In Repair", "Repair submitted")
        elif self.rma_type == "Replacement":
            self.handle_replacement_submit()

    def on_cancel(self):
        self.status = "Cancelled"
        self._log_activity("Cancelled", self.status, "Cancelled", "RMA cancelled")

    def set_warranty_status(self):
        if self.warranty_expiry:
            if getdate(self.warranty_expiry) >= getdate(nowdate()):
                self.warranty_status = "In Warranty"
            else:
                self.warranty_status = "Out of Warranty"

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
                "docstatus": 1,
                "name": ("!=", self.name),
            })
            if existing:
                frappe.throw(_("Serial {0} is already used in another replacement RMA").format(self.replacement_serial_no))

    def validate_buffer_warranty(self):
        if self.rma_type != "Replacement" or self.docstatus != 0:
            return
        settings = frappe.get_single("RMA Settings")
        if self.warranty_status == "Out of Warranty":
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

    def handle_replacement_submit(self):
        settings = frappe.get_single("RMA Settings")
        user_roles = frappe.get_roles(frappe.session.user)
        is_staff = "RMA Staff" in user_roles
        is_manager = "RMA Manager" in user_roles or "System Manager" in user_roles

        needs_approval = False

        if self.warranty_status == "In Warranty":
            if settings.require_manager_approval_for_replace:
                approval_setting = settings.approval_required_for_warranty_status
                if approval_setting in ("In Warranty", "In Warranty and Out of Warranty"):
                    if is_staff:
                        needs_approval = True

        elif self.warranty_status == "Out of Warranty":
            if self.buffer_warranty:
                if not self.invoice_image:
                    frappe.throw(_("Invoice image is required for buffer warranty replacement."))
                needs_approval = True

        if needs_approval and is_staff:
            self.status = "Pending Approval"
            self.db_set("status", "Pending Approval")
            self._log_activity("Pending Approval", "Draft", "Pending Approval", "Awaiting manager approval")
            frappe.msgprint(_("This replacement requires manager approval. Notification sent."))
            return

        if is_manager and self.warranty_status == "Out of Warranty" and self.buffer_warranty:
            if self.invoice_image and not self.invoice_verified:
                frappe.throw(_("Invoice must be verified before proceeding. Use 'Verify Invoice' button."))
            elif self.invoice_verified and self.replacement_serial_no:
                self._log_activity("Manager Verified", "Pending Approval", "Verified", "Invoice verified by manager")
                self.complete_replacement()
            else:
                self.status = "Pending Approval"
                self.db_set("status", "Pending Approval")
                frappe.msgprint(_("Please verify the invoice first, then scan replacement serial."))
                return

        if self.replacement_serial_no:
            self.complete_replacement()

    def complete_replacement(self):
        old_status = self.status
        self.status = "Replaced"
        self.completed_date = now_datetime()
        self._log_activity("Completed", old_status, "Replaced", "Replacement completed")
        self.create_replacement_dispatch()

    def create_replacement_dispatch(self):
        if not self.replacement_serial_no:
            return
        new_serial = frappe.get_doc("Serial No", self.replacement_serial_no)
        if new_serial.status not in ("Active", "In Store"):
            frappe.throw(_("Replacement serial {0} is not available. Status: {1}").format(
                self.replacement_serial_no, new_serial.status
            ))
        item = frappe.get_cached_doc("Item", self.item_code)
        warranty_days = item.warranty_period_days or frappe.get_single("RMA Settings").default_warranty_days or 365
        new_serial.customer = self.customer
        new_serial.branch = self.branch
        new_serial.company = self.company
        new_serial.warranty_expiry_date = add_days(nowdate(), warranty_days)
        new_serial.status = "Dispatched"
        new_serial.save(ignore_permissions=True)

        dispatch = frappe.get_doc({
            "doctype": "Dispatch Entry",
            "customer": self.customer,
            "branch": self.branch,
            "company": self.company,
            "posting_date": nowdate(),
            "products": [{
                "item_code": self.item_code,
                "qty": 1,
                "serial_nos": self.replacement_serial_no,
            }]
        })
        dispatch.insert(ignore_permissions=True)
        dispatch.submit()
        self.replacement_dispatch_entry = dispatch.name
        self.db_set("replacement_dispatch_entry", dispatch.name)


@frappe.whitelist()
def get_serial_details(serial_no):
    serial = frappe.get_doc("Serial No", serial_no)
    item = frappe.get_cached_doc("Item", serial.item_code)
    warranty_days = item.warranty_period_days or frappe.get_single("RMA Settings").default_warranty_days or 365
    return {
        "item_code": serial.item_code,
        "item_name": serial.item_name,
        "customer": serial.customer,
        "customer_name": frappe.db.get_value("Customer", serial.customer, "customer_name") if serial.customer else "",
        "branch": serial.branch,
        "company": serial.company,
        "sale_date": getdate(serial.creation),
        "warranty_expiry": serial.warranty_expiry_date,
        "warranty_status": "In Warranty" if serial.warranty_expiry_date and getdate(serial.warranty_expiry_date) >= getdate(nowdate()) else "Out of Warranty",
        "warranty_days": warranty_days,
    }


@frappe.whitelist()
def create_replacement(docname, new_serial):
    frappe.has_permission("RMA Request", "write", throw=True)
    doc = frappe.get_doc("RMA Request", docname)
    if doc.docstatus != 0:
        frappe.throw(_("Can only set replacement on a draft document"))
    new_serial_doc = frappe.get_doc("Serial No", new_serial)
    if new_serial_doc.status not in ("Active", "In Store"):
        frappe.throw(_("Serial {0} is not available (status: {1})").format(new_serial, new_serial_doc.status))
    doc.replacement_serial_no = new_serial
    doc.replacement_item_code = new_serial_doc.item_code
    doc.save(ignore_permissions=True)
    return {"replacement_serial_no": new_serial, "replacement_item_code": new_serial_doc.item_code}


@frappe.whitelist()
def mark_completed(docname):
    frappe.has_permission("RMA Request", "write", throw=True)
    doc = frappe.get_doc("RMA Request", docname)
    if doc.rma_type != "Repair":
        frappe.throw(_("Only Repair type RMA can be marked completed this way"))
    doc.status = "Completed"
    doc.completed_date = now_datetime()
    doc._log_activity("Completed", "In Repair", "Completed", "Repair completed")
    doc.save(ignore_permissions=True)
    return doc.status


@frappe.whitelist()
def approve_replacement(docname):
    frappe.has_permission("RMA Request", "write", throw=True)
    user_roles = frappe.get_roles(frappe.session.user)
    if "RMA Manager" not in user_roles and "System Manager" not in user_roles:
        frappe.throw(_("Only RMA Manager can approve replacements"))
    doc = frappe.get_doc("RMA Request", docname)
    if doc.status != "Pending Approval":
        frappe.throw(_("Document is not in 'Pending Approval' status"))
    old_status = doc.status
    doc.status = "Approved for Replacement"
    doc._log_activity("Approved", old_status, "Approved for Replacement", "Manager approved replacement")
    doc.save(ignore_permissions=True)
    frappe.msgprint(_("RMA {0} approved for replacement. Please scan the replacement serial.").format(docname))
    return doc.status


@frappe.whitelist()
def verify_invoice(docname):
    frappe.has_permission("RMA Request", "write", throw=True)
    user_roles = frappe.get_roles(frappe.session.user)
    if "RMA Manager" not in user_roles and "System Manager" not in user_roles:
        frappe.throw(_("Only RMA Manager can verify invoices"))
    doc = frappe.get_doc("RMA Request", docname)
    if not doc.buffer_warranty:
        frappe.throw(_("This is not a buffer warranty request"))
    if not doc.invoice_image:
        frappe.throw(_("No invoice image uploaded to verify"))
    doc.invoice_verified = 1
    doc.manager_verified_by = frappe.session.user
    old_status = doc.status
    doc.status = "Approved for Replacement"
    doc._log_activity("Invoice Verified", old_status, "Approved for Replacement", "Invoice verified by manager")
    doc.save(ignore_permissions=True)
    frappe.msgprint(_("Invoice verified. RMA is now approved for replacement."))
    return {"status": doc.status, "invoice_verified": 1, "manager_verified_by": frappe.session.user}
