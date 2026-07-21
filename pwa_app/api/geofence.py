import frappe
import math


def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance in meters between two lat/lng points using Haversine formula."""
    R = 6371000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_employee_geofence_type(employee):
    """Get the geofence enforcement type for an employee."""
    return frappe.db.get_value("Employee", employee, "checkin_geofence_type") or "SOFT"


def validate_geofence(employee, latitude, longitude):
    """
    Check if location is within any active geofence area.
    Returns (is_allowed, flag) where flag is None (allowed), 'OUTSIDE_GEOFENCE' (soft), or raises error (hard).
    """
    geofence_type = get_employee_geofence_type(employee)
    if geofence_type == "DISABLED":
        return True, None

    try:
        areas = frappe.get_all(
            "Geofence Area",
            {"is_active": 1},
            ["name", "latitude", "longitude", "radius_meters"],
        )
    except Exception:
        areas = []
    if not areas:
        return True, None

    lat, lng = float(latitude), float(longitude)
    for area in areas:
        distance = haversine(lat, lng, float(area.latitude), float(area.longitude))
        if distance <= float(area.radius_meters):
            return True, None

    if geofence_type == "HARD":
        frappe.throw(
            frappe._("You are outside the designated check-in area. Check-in is not allowed.")
        )

    return True, "OUTSIDE_GEOFENCE"


@frappe.whitelist()
def get_geofence_areas():
    """Return all active geofence areas (for client-side map display)."""
    try:
        areas = frappe.get_all(
            "Geofence Area",
            {"is_active": 1},
            ["name", "latitude", "longitude", "radius_meters", "area_name", "branch"],
        )
    except Exception:
        areas = []
    return areas
