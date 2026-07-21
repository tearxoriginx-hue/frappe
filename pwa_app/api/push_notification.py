import json
import frappe
from base64 import urlsafe_b64encode


@frappe.whitelist(allow_guest=True)
def get_vapid_public_key():
    settings = frappe.get_single("PWA Settings")
    return settings.get("vapid_public_key") or ""


@frappe.whitelist()
def generate_vapid_keys():
    frappe.only_for("System Manager")
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization

        private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
        public_key = private_key.public_key()

        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode("utf-8")

        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint
        )
        public_b64 = urlsafe_b64encode(public_bytes).rstrip(b"=").decode("utf-8")

        settings = frappe.get_single("PWA Settings")
        settings.db_set("vapid_private_key", private_pem)
        settings.db_set("vapid_public_key", public_b64)
        frappe.db.commit()
        return {"success": True, "public_key": public_b64}
    except Exception as e:
        frappe.log_error(f"VAPID key generation failed: {str(e)}")
        return {"success": False, "error": str(e)}


def _get_vapid_claims_and_key():
    from cryptography.hazmat.primitives import serialization
    settings = frappe.get_single("PWA Settings")
    private_pem = settings.get("vapid_private_key")
    if not private_pem:
        return None, None
    vapid_claims = {"sub": "mailto:hello@krystaa.com"}
    return vapid_claims, private_pem


@frappe.whitelist(allow_guest=True)
def subscribe():
    user = frappe.session.user
    if user == "Guest":
        return {"success": False, "error": "Not authenticated"}
    subscription_json = frappe.local.form_dict.get("subscription")
    device_name = frappe.local.form_dict.get("device_name", "")
    if not subscription_json:
        return {"success": False, "error": "Missing subscription"}
    existing = frappe.db.exists("PWA Push Subscription",
        {"user": user, "subscription": subscription_json})
    if existing:
        return {"success": True}
    doc = frappe.get_doc({
        "doctype": "PWA Push Subscription",
        "user": user,
        "subscription": subscription_json,
        "device_name": device_name
    })
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"success": True}


@frappe.whitelist()
def unsubscribe():
    user = frappe.session.user
    if user == "Guest":
        return {"success": False}
    subscription_json = frappe.local.form_dict.get("subscription")
    if subscription_json:
        frappe.db.delete("PWA Push Subscription",
            {"user": user, "subscription": subscription_json})
    else:
        frappe.db.delete("PWA Push Subscription", {"user": user})
    return {"success": True}


def send_push_to_user(user, title, body, url="/install/app"):
    from pywebpush import webpush, WebPushException
    vapid_claims, private_key = _get_vapid_claims_and_key()
    if not vapid_claims or not private_key:
        return
    subscriptions = frappe.get_all("PWA Push Subscription",
        filters={"user": user}, fields=["subscription"])
    for sub in subscriptions:
        try:
            sub_data = json.loads(sub.subscription)
            webpush(
                subscription_info=sub_data,
                data=json.dumps({
                    "title": title,
                    "body": body,
                    "data": {"url": url}
                }),
                vapid_private_key=private_key,
                vapid_claims=vapid_claims
            )
        except WebPushException as e:
            if e.response and e.response.status_code in (404, 410):
                frappe.db.delete("PWA Push Subscription",
                    {"user": user, "subscription": sub.subscription})
        except Exception:
            pass


def notify_on_notification_log(doc, method):
    if doc.type == "Alert" and doc.for_user and doc.for_user != "Guest":
        send_push_to_user(
            user=doc.for_user,
            title=doc.subject or "Notification",
            body=doc.email_content or doc.subject or "",
            url="/install/app"
        )


def notify_on_incoming_email(doc, method):
    """Create Notification Log when a new email is received (like Gmail push)"""
    if doc.get("sent_or_received") != "Received":
        return
    if doc.get("communication_type") != "Communication":
        return
    if doc.get("communication_medium") != "Email" and not doc.get("email_account"):
        return

    recipient_user = None

    # Method 1: Find user via Email Account owner
    if doc.get("email_account"):
        email_owner = frappe.db.get_value("Email Account", doc.email_account, "owner")
        if email_owner and email_owner not in ("Guest", "Administrator"):
            recipient_user = email_owner

    # Method 2: Fallback — parse recipients and match to a User email
    if not recipient_user and doc.get("recipients"):
        import re
        emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', doc.recipients)
        for email in emails:
            user = frappe.db.get_value("User", {"email": email}, "name")
            if user and user not in ("Guest", "Administrator"):
                recipient_user = user
                break

    if not recipient_user:
        return

    # Build display name for the sender (like Gmail shows "From: Name")
    sender_display = doc.get("sender_full_name") or doc.get("sender") or "Unknown"
    subject = doc.get("subject") or "(no subject)"

    # Truncate subject for the notification body
    if len(subject) > 80:
        subject = subject[:77] + "..."

    notification = frappe.get_doc({
        "doctype": "Notification Log",
        "subject": f"📧 {sender_display}",
        "email_content": subject,
        "type": "Alert",
        "for_user": recipient_user,
        "document_type": "Communication",
        "document_name": doc.name
    })
    notification.insert(ignore_permissions=True)
