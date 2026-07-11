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
