"""Permission matrix. Four primary roles only; Hotel Admin may grant extra permissions per user."""
from __future__ import annotations

PERMISSIONS: dict[str, str] = {
    "dashboard.view": "View the operational dashboard",
    "hotel.manage": "Edit hotel profile and booking settings",
    "settings.payments": "Edit payment, deposit and refund settings",
    "rooms.view": "View rooms and categories",
    "rooms.manage": "Create/edit rooms and room categories",
    "media.manage": "Upload and manage media library",
    "website.manage": "Edit and publish website content",
    "pricing.manage": "Manage prices, taxes and pricing rules",
    "promotions.manage": "Manage offers and promo codes",
    "availability.view": "View availability calendar",
    "reservations.view": "View reservations",
    "reservations.create": "Create reservations (walk-in / manual)",
    "reservations.manage": "Modify, charge and cancel reservations",
    "reservations.assign": "Assign and reassign rooms",
    "guests.view": "View guest profiles",
    "guests.manage": "Create and update guest details",
    "guests.notes": "View/edit internal guest notes",
    "payments.view": "View payments and balances",
    "payments.record": "Record offline payments",
    "refunds.view": "View refunds",
    "refunds.manage": "Request, approve and process refunds",
    "checkin.manage": "Check guests in and out",
    "housekeeping.view": "View housekeeping board",
    "housekeeping.manage": "Update housekeeping status",
    "maintenance.manage": "Manage maintenance requests and blocks",
    "reports.operational": "View operational reports",
    "reports.financial": "View financial reports",
    "staff.manage": "Manage staff accounts",
    "audit.view": "View audit logs",
    "system.manage": "Platform-owner controls (Super Admin only)",
}
ALL = set(PERMISSIONS)

ROLES = ("super_admin", "hotel_admin", "hotel_manager", "receptionist")
HOTEL_ROLES = ("hotel_admin", "hotel_manager", "receptionist")
ROLE_LABELS = {
    "super_admin": "Super Admin",
    "hotel_admin": "Hotel Admin",
    "hotel_manager": "Hotel Manager",
    "receptionist": "Receptionist",
}

ROLE_DEFAULTS: dict[str, set[str]] = {
    "super_admin": set(ALL),
    "hotel_admin": ALL - {"system.manage"},
    "hotel_manager": {
        "dashboard.view", "rooms.view", "availability.view",
        "reservations.view", "reservations.create", "reservations.manage", "reservations.assign",
        "guests.view", "guests.manage", "payments.view", "refunds.view",
        "checkin.manage", "housekeeping.view", "housekeeping.manage", "maintenance.manage",
        "reports.operational",
    },
    "receptionist": {
        "dashboard.view", "rooms.view", "availability.view",
        "reservations.view", "reservations.create", "reservations.assign",
        "guests.view", "guests.manage", "payments.view", "payments.record",
        "checkin.manage", "housekeeping.view",
    },
}

# Permissions the Hotel Admin may NOT hand out as extras
NON_GRANTABLE = {"system.manage", "settings.payments", "staff.manage"}


def effective_permissions(user: dict) -> set[str]:
    role = user.get("role")
    if role == "super_admin":
        return set(ALL)
    base = set(ROLE_DEFAULTS.get(role, set()))
    extras = set(user.get("extra_permissions") or []) & (ALL - {"system.manage"})
    return base | extras
