import frappe


@frappe.whitelist()
def global_search(text, limit=20):
    """Bridge to Frappe global search — returns structured results."""
    if not text or len(text.strip()) < 1:
        return []

    try:
        results = frappe.desk.global_search.search(text, limit=limit)
        return [
            {
                "label": r.get("title") or r.get("name") or "",
                "description": r.get("description") or "",
                "doctype": r.get("doctype") or "",
                "name": r.get("name") or "",
                "route": r.get("route") or "",
                "published": r.get("published") or 0,
            }
            for r in results
        ]
    except Exception:
        return []


@frappe.whitelist()
def get_customers(query=None):
    """Fetch customers safely - bypasses REST API issues."""
    try:
        filters = {"disabled": 0}
        if query:
            filters["customer_name"] = ["like", f"%{query}%"]
        return frappe.get_list("Customer", filters=filters, fields=["name","customer_name","customer_group","territory","email","phone","creation"], order_by="creation desc", limit_page_length=200)
    except Exception as e:
        frappe.log_error(f"get_customers failed: {e}")
        return []

@frappe.whitelist()
def get_items(query=None):
    """Fetch items safely - bypasses REST API issues."""
    try:
        filters = {"disabled": 0}
        if query:
            filters["item_name"] = ["like", f"%{query}%"]
        return frappe.get_list("Item", filters=filters, fields=["name","item_name","item_group","stock_uom","warranty_period_days","creation"], order_by="creation desc", limit_page_length=200)
    except Exception as e:
        frappe.log_error(f"get_items failed: {e}")
        return []

@frappe.whitelist()
def get_employees_list():
    try:
        return frappe.get_list("Employee",
            filters={"status": "Active"},
            fields=["name", "employee_name", "designation", "department", "branch", "attendance_type"],
            order_by="employee_name asc",
            limit_page_length=500)
    except Exception as e:
        frappe.log_error(f"get_employees_list failed: {e}")
        return []

@frappe.whitelist()
def get_doctype_list(doctype, fields=None, filters=None, limit=200):
    """Generic safe list fetch for reference doctypes like Customer Group, Territory, Item Group."""
    try:
        fields = fields or ["name"]
        filters = filters or {}
        return frappe.get_list(doctype, filters=filters, fields=fields, limit_page_length=limit)
    except Exception:
        return []
