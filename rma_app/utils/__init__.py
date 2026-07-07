import frappe
from frappe.utils import getdate, nowdate, add_days


def calculate_warranty_expiry(item_code, from_date=None):
    from_date = from_date or nowdate()
    item = frappe.get_cached_doc("Item", item_code)
    days = item.warranty_period_days or frappe.get_single("RMA Settings").default_warranty_days or 365
    return add_days(from_date, days)


def get_staff_branch(user=None):
    user = user or frappe.session.user
    return frappe.db.get_value("Employee", {"user_id": user}, "branch")
