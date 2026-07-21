import frappe


def notify_on_create(doc, method):
    _notify_managers(
        f"New Dispatch Entry: {doc.name}",
        f"Customer: {doc.customer or ''} - Status: {doc.processing_status or ''}"
    )


def notify_on_update(doc, method):
    before = doc.get_doc_before_save()
    if before and before.processing_status != doc.processing_status:
        _notify_user(
            doc.owner,
            f"Dispatch {doc.name} status changed",
            f"Status: {before.processing_status} -> {doc.processing_status}"
        )


def _notify_user(user, title, body):
    try:
        from pwa_app.api.push_notification import send_push_to_user
        send_push_to_user(user, title, body, url="/dispatch")
    except ImportError:
        pass
    except Exception:
        pass


def _notify_managers(title, body):
    managers = frappe.db.sql_list("""
        SELECT DISTINCT parent
        FROM `tabHas Role`
        WHERE role IN ('Dispatch Manager', 'System Manager')
          AND parent != 'Administrator'
    """)
    for user in managers:
        _notify_user(user, title, body)
