import frappe


def notify_on_create(doc, method):
    _notify_managers(
        f"New RMA Request: {doc.name}",
        f"{doc.serial_no} - {doc.item_name or ''} ({doc.status})"
    )


def notify_on_update(doc, method):
    if doc.get_doc_before_save() and doc.get_doc_before_save().status != doc.status:
        _notify_user(
            doc.owner,
            f"RMA {doc.name} status changed",
            f"Status: {doc.get_doc_before_save().status} -> {doc.status}"
        )


def _notify_user(user, title, body):
    try:
        from pwa_app.api.push_notification import send_push_to_user
        send_push_to_user(user, title, body, url="/rma")
    except ImportError:
        pass
    except Exception:
        pass


def _notify_managers(title, body):
    managers = frappe.db.sql_list("""
        SELECT DISTINCT parent
        FROM `tabHas Role`
        WHERE role IN ('RMA Manager', 'System Manager')
          AND parent != 'Administrator'
    """)
    for user in managers:
        _notify_user(user, title, body)
