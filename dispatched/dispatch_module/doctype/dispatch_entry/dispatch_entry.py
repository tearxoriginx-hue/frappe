# Copyright (c) 2026, Varun and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import today, nowtime, add_days, getdate, cint


class DispatchEntry(Document):

	def autoname(self):
		"""Generate readable names: DISP-DELHI-05-03-26-0001"""
		branch_code = (self.branch or "GEN").upper().replace(" ", "")[:6]
		posting = self.posting_date or today()
		date_str = frappe.utils.formatdate(posting, "dd-MM-yy")
		prefix = f"DISP-{branch_code}-{date_str}-"
		self.name = frappe.model.naming.make_autoname(prefix + ".####")

	def before_insert(self):
		self._set_header_defaults()

	def validate(self):
		self._set_header_defaults()
		self._recalculate_product_rows()

	def on_submit(self):
		self.db_set("processing_status", "In Queue", update_modified=False)
		frappe.enqueue(
			"dispatched.dispatch_module.doctype.dispatch_entry.dispatch_entry.process_serial_numbers",
			doc_name=self.name,
			queue="long",
			timeout=7200,
			enqueue_after_commit=True,
		)

	# ------------------------------------------------------------------
	# Helpers
	# ------------------------------------------------------------------

	def _set_header_defaults(self):
		"""Auto-fill fields the operator should never have to touch."""
		if not self.posting_date:
			self.posting_date = today()
		if not self.posting_time:
			self.posting_time = nowtime()

		if not self.company:
			user_defaults = frappe.defaults.get_defaults(frappe.session.user)
			self.company = (
				user_defaults.get("company")
				or frappe.db.get_single_value("Global Defaults", "default_company")
			)

		# Branch is set by the user manually (or via User Permissions defaults)

	def _recalculate_product_rows(self):
		"""
		For each product row, count serials from serial_nos text and
		auto-calculate expiry_date from posting_date + warranty_period_days.
		Also update the header total_qty.
		"""
		posting_date = getdate(self.posting_date or today())
		grand_total = 0

		for row in (self.products or []):
			# Count serials (non-empty lines)
			serials = _parse_serials(row.serial_nos)
			row.qty = len(serials)
			grand_total += row.qty

			# Fetch warranty period if missing
			if not row.warranty_period_days and row.item_code:
				row.warranty_period_days = cint(
					frappe.db.get_value("Item", row.item_code, "warranty_period") or 0
				)

			# Calculate expiry date
			if row.warranty_period_days:
				row.expiry_date = add_days(posting_date, cint(row.warranty_period_days))
			else:
				row.expiry_date = None

		self.total_qty = grand_total


# ------------------------------------------------------------------
# Utility
# ------------------------------------------------------------------

def _parse_serials(serial_nos_text):
	"""Return a deduplicated, stripped list of serial numbers from Long Text."""
	if not serial_nos_text:
		return []
	seen = set()
	result = []
	for line in serial_nos_text.splitlines():
		sn = line.strip().upper()
		if sn and sn not in seen:
			seen.add(sn)
			result.append(line.strip())  # preserve original case
	return result


# ------------------------------------------------------------------
# Background Job – runs in a long-queue worker
# ------------------------------------------------------------------

def process_serial_numbers(doc_name):
	"""
	Scan-to-Exist Engine (background job):
	  - For each product row in the Dispatch Entry, parse the serial_nos text.
	  - If serial exists → update warranty + customer.
	  - If serial missing → auto-create Serial No record.
	  - Commits every BATCH_SIZE rows to prevent row-lock timeouts at 5,000+ scale.
	"""
	BATCH_SIZE = 50

	try:
		doc = frappe.get_doc("Dispatch Entry", doc_name)
		posting_date = getdate(doc.posting_date)
		processed_count = 0

		for product_row in (doc.products or []):
			serials = _parse_serials(product_row.serial_nos)
			warranty_days = cint(product_row.warranty_period_days or 0)
			expiry_date = add_days(posting_date, warranty_days) if warranty_days else None
			customer_name = frappe.db.get_value("Customer", doc.customer, "customer_name")

			for idx, sn in enumerate(serials):
				if frappe.db.exists("Serial No", sn):
					# Update existing
					frappe.db.set_value(
						"Serial No",
						sn,
						{
							"customer": doc.customer,
							"customer_name": customer_name,
							"warranty_period": warranty_days,
							"warranty_expiry_date": expiry_date,
							"status": "Active",
						},
						update_modified=False,
					)
				else:
					# Auto-create
					sn_doc = frappe.get_doc(
						{
							"doctype": "Serial No",
							"serial_no": sn,
							"item_code": product_row.item_code,
							"company": doc.company,
							"customer": doc.customer,
							"customer_name": customer_name,
							"warranty_period": warranty_days,
							"warranty_expiry_date": expiry_date,
							"status": "Active",
						}
					)
					sn_doc.insert(ignore_permissions=True)

				processed_count += 1
				if processed_count % BATCH_SIZE == 0:
					frappe.db.commit()

		# Final commit for remainder
		frappe.db.commit()
		frappe.db.set_value("Dispatch Entry", doc_name, "processing_status", "Processed")
		frappe.db.commit()

	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Dispatch Processing Failed: {doc_name}")
		frappe.db.set_value("Dispatch Entry", doc_name, "processing_status", "Failed")
		frappe.db.commit()
		raise


@frappe.whitelist()
def retry_processing(doc_name):
	"""Allow Dispatch Manager to retry a failed processing job."""
	doc = frappe.get_doc("Dispatch Entry", doc_name)
	if doc.docstatus != 1:
		frappe.throw("Can only retry submitted Dispatch Entries.")
	if doc.processing_status not in ("Failed", "Pending"):
		frappe.throw("Can only retry entries with Failed or Pending status.")

	frappe.db.set_value("Dispatch Entry", doc_name, "processing_status", "In Queue")
	frappe.db.commit()

	frappe.enqueue(
		"dispatched.dispatch_module.doctype.dispatch_entry.dispatch_entry.process_serial_numbers",
		doc_name=doc_name,
		queue="long",
		timeout=7200,
	)
