# Copyright (c) 2026, Varun and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
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
		self._validate_serial_matrix()

	def after_insert(self):
		"""After first save: set processing status and enqueue background job."""
		self.db_set("processing_status", "In Queue", update_modified=False)
		frappe.enqueue(
			"dispatched.dispatch_module.doctype.dispatch_entry.dispatch_entry.process_serial_numbers",
			doc_name=self.name,
			queue="long",
			timeout=7200,
			enqueue_after_commit=True,
		)

	def _set_header_defaults(self):
		"""Set posting date, time, and company defaults."""
		if not self.posting_date:
			self.posting_date = today()
		if not self.posting_time:
			self.posting_time = nowtime()
		if not self.company:
			self.company = frappe.db.get_single_value("Global Defaults", "default_company")
		if not self.company:
			frappe.throw(_("Company is required. Set default_company in Global Defaults first."))

	def _recalculate_product_rows(self):
		posting_date = getdate(self.posting_date or today())
		grand_total = 0
		for row in (self.products or []):
			serials = _parse_serials(row.serial_nos)
			row.qty = len(serials)
			grand_total += row.qty
			if not row.warranty_period_days and row.item_code:
				row.warranty_period_days = cint(
					frappe.db.get_value("Item", row.item_code, "warranty_period_days") or 0
				)
			if row.warranty_period_days:
				row.expiry_date = add_days(posting_date, cint(row.warranty_period_days))
			else:
				row.expiry_date = None
		self.total_qty = grand_total

	def _validate_serial_matrix(self):
		"""Smart Matrix: validate serial batch for anomalies on the server side.
		Checks length consistency, prefix patterns, and sequential gaps."""
		for row in (self.products or []):
			serials = _parse_serials(row.serial_nos)
			if len(serials) < 2:
				continue

			warnings = []

			# --- Check 1: Length consistency ---
			length_counts = {}
			for s in serials:
				length_counts[len(s)] = length_counts.get(len(s), 0) + 1
			most_common_len = max(length_counts, key=length_counts.get)
			unusual = [s for s in serials if len(s) != most_common_len]
			if unusual and len(unusual) < len(serials) / 2:
				show = unusual[:5]
				extra = "...and %d more" % (len(unusual) - 5) if len(unusual) > 5 else ""
				warnings.append(
					"%d serial(s) have unusual length (expected %d chars): %s %s"
					% (len(unusual), most_common_len, ", ".join(show), extra)
				)

			# --- Check 2: Prefix pattern detection ---
			prefixes = {}
			for s in serials:
				match = re.match(r"^([A-Z]+)", s.upper())
				if match:
					prefixes[match.group(1)] = prefixes.get(match.group(1), 0) + 1
			if len(prefixes) > 1:
				main_prefix = max(prefixes, key=prefixes.get)
				outliers = [p for p in prefixes if p != main_prefix]
				warnings.append(
					"Multiple prefixes detected: %s (majority: %s)"
					% (", ".join(outliers), main_prefix)
				)

			# --- Check 3: Sequential gap detection ---
			numbered = []
			for s in serials:
				match = re.match(r"^(.*[A-Za-z])(\d+)$", s)
				if match:
					numbered.append((match.group(1).upper(), int(match.group(2))))
			groups = {}
			for prefix, num in numbered:
				if prefix not in groups:
					groups[prefix] = []
				groups[prefix].append(num)
			for prefix, nums in groups.items():
				if len(nums) < 3:
					continue
				nums.sort()
				for i in range(1, len(nums)):
					if nums[i] - nums[i - 1] > 1:
						for missing in range(nums[i - 1] + 1, nums[i]):
							warnings.append(
								"Possible gap: %s%d is missing" % (prefix, missing)
							)
							if len(warnings) >= 6:
								break
					if len(warnings) >= 6:
						break
				if len(warnings) >= 6:
					break

			# Show warnings if any found
			if warnings:
				frappe.msgprint(
					_("Smart Matrix Validation Warnings for %(item)s:")
					% {"item": row.item_code or "Row"}
					+ "<br>" + "<br>".join(warnings[:5]),
					indicator="orange",
					title=_("Serial Validation Warning"),
				)


def _parse_serials(serial_nos_text):
	if not serial_nos_text:
		return []
	seen = set()
	result = []
	for line in serial_nos_text.splitlines():
		sn = line.strip().upper()
		if sn and sn not in seen:
			seen.add(sn)
			result.append(line.strip())
	return result


def process_serial_numbers(doc_name):
	BATCH_SIZE = 50
	try:
		doc = frappe.get_doc("Dispatch Entry", doc_name)
		posting_date = getdate(doc.posting_date)
		processed_count = 0
		for product_row in (doc.products or []):
			serials = _parse_serials(product_row.serial_nos)
			warranty_days = cint(product_row.warranty_period_days or 0)
			expiry_date = add_days(posting_date, warranty_days) if warranty_days else None

			for sn in serials:
				if frappe.db.exists("Serial No", sn):
					frappe.db.set_value(
						"Serial No", sn,
						{
							"customer": doc.customer,
							"warranty_period_days": warranty_days,
							"warranty_expiry_date": expiry_date,
							"status": "Active",
						},
						update_modified=False,
					)
				else:
					sn_doc = frappe.get_doc({
						"doctype": "Serial No",
						"serial_no": sn,
						"item_code": product_row.item_code,
						"company": doc.company,
						"customer": doc.customer,
						"warranty_period_days": warranty_days,
						"warranty_expiry_date": expiry_date,
						"status": "Active",
					})
					sn_doc.insert(ignore_permissions=True)

				processed_count += 1
				if processed_count % BATCH_SIZE == 0:
					frappe.db.commit()

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
	"""Re-queue processing for a saved Dispatch Entry."""
	doc = frappe.get_doc("Dispatch Entry", doc_name)
	if doc.processing_status not in ("Failed", "Pending"):
		frappe.throw(_("Can only retry entries with Failed or Pending status."))

	frappe.db.set_value("Dispatch Entry", doc_name, "processing_status", "In Queue")
	frappe.db.commit()

	frappe.enqueue(
		"dispatched.dispatch_module.doctype.dispatch_entry.dispatch_entry.process_serial_numbers",
		doc_name=doc_name,
		queue="long",
		timeout=7200,
	)


@frappe.whitelist()
def get_user_branch():
	"""Get the branch linked to the current user's Employee record.
	Ignores permissions since it's called from client script."""
	branch = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "branch")
	return {"branch": branch}


@frappe.whitelist()
def get_user_company():
	"""Get the default company from Global Defaults.
	Ignores permissions since it's called from client script."""
	company = frappe.db.get_single_value("Global Defaults", "default_company")
	return {"company": company}
