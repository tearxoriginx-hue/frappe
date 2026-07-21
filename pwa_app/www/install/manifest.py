import frappe
import json

no_cache = 1
no_header = True


def get_context(context):
    site_name = frappe.db.get_single_value("Website Settings", "app_name") or "ERP"

    icon_url = "/assets/pwa_app/icons/icon-512.svg"
    try:
        ws = frappe.get_single("Website Settings")
        if ws.splash_image:
            icon_url = ws.splash_image
        elif ws.application_logo:
            icon_url = ws.application_logo
    except Exception:
        pass

    if icon_url and not icon_url.startswith("/"):
        icon_url = "/" + icon_url

    icon_type = "image/png"
    if icon_url.endswith(".svg"):
        icon_type = "image/svg+xml"

    manifest = {
        "name": site_name,
        "short_name": site_name,
        "description": site_name,
        "start_url": "/install/app",
        "display": "standalone",
        "background_color": "#f7f9fb",
        "theme_color": "#004ac6",
        "orientation": "portrait",
        "icons": [
            {
                "src": icon_url,
                "sizes": "192x192",
                "type": icon_type,
                "purpose": "any",
            },
            {
                "src": icon_url,
                "sizes": "512x512",
                "type": icon_type,
                "purpose": "any maskable",
            },
        ],
        "categories": ["business", "productivity"],
        "share_target": {
            "action": "/install/app",
            "method": "GET",
            "enctype": "application/x-www-form-urlencoded",
            "params": {
                "title": "title",
                "text": "text",
                "url": "url",
            },
        },
    }

    context.manifest_json = json.dumps(manifest, indent=2)
    return context
