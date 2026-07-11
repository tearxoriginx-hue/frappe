import frappe
from frappe import _
from frappe.utils import now_datetime
from pwa_app.api.utils import get_employee as _get_employee
from pwa_app.api.geofence import validate_geofence


@frappe.whitelist(methods=["POST"])
def update_location(latitude=None, longitude=None, accuracy=None, device_id=None):
    """
    Periodic background location update from the PWA.
    Called every ~10 minutes while employee is checked in.

    Stores location in Employee Location Track for audit trail and map display.
    """
    user = frappe.session.user
    employee = _get_employee(user)
    if not employee:
        frappe.throw(_("No employee record found for this user"))

    if not (latitude and longitude):
        frappe.throw(_("Latitude and longitude are required"))

    # Find current active checkin
    today = frappe.utils.today()
    active_checkin = frappe.get_all(
        "Employee Checkin",
        filters={
            "employee": employee,
            "time": [">=", f"{today} 00:00:00"],
            "log_type": "IN",
        },
        fields=["name"],
        order_by="time desc",
        limit_page_length=1,
    )
    checkin_ref = active_checkin[0].name if active_checkin else None

    # Check geofence
    within = None
    try:
        _, flag = validate_geofence(employee, latitude, longitude)
        within = flag is None
    except frappe.ValidationError:
        within = False
    except Exception:
        within = None

    track = frappe.get_doc({
        "doctype": "Employee Location Track",
        "employee": employee,
        "timestamp": now_datetime(),
        "latitude": latitude,
        "longitude": longitude,
        "accuracy_meters": accuracy,
        "device_id": device_id,
        "checkin_ref": checkin_ref,
        "is_within_geofence": 1 if within else 0,
    })
    track.insert(ignore_permissions=True)
    frappe.db.commit()

    return {
        "success": True,
        "within_geofence": within,
    }
