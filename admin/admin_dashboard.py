from flask import Blueprint, jsonify

from backend.json_store import load, public_user
from backend.security import require_roles

admin_dashboard_bp = Blueprint("admin_dashboard", __name__)


def _count(rows, **filters):
    total = 0
    for row in rows:
        if all(row.get(key) == value for key, value in filters.items()):
            total += 1
    return total


@admin_dashboard_bp.get("/api/admin/dashboard")
def dashboard():
    session, error = require_roles("admin")
    if error:
        return jsonify(error[0]), error[1]

    users = load("users")
    doctors = load("doctors")
    pharmacies = load("pharmacies")
    hospitals = load("hospitals")
    appointments = load("appointments")
    orders = load("orders")

    return jsonify({
        "region": "North East India",
        "admin_id": session["account_id"],
        "users": {
            "total": len(users),
            "active": _count(users, status="active"),
            "suspended": _count(users, status="suspended"),
        },
        "doctors": {
            "total": len(doctors),
            "pending": _count(doctors, verification_status="pending"),
            "verified": _count(doctors, verification_status="approved"),
            "rejected": _count(doctors, verification_status="rejected"),
        },
        "pharmacies": {
            "total": len(pharmacies),
            "pending": _count(pharmacies, verification_status="pending"),
            "verified": _count(pharmacies, verification_status="approved"),
        },
        "hospitals": {
            "total": len(hospitals),
            "pending": _count(hospitals, verification_status="pending"),
            "verified": _count(hospitals, verification_status="approved"),
        },
        "appointments_today_total": len(appointments),
        "open_orders": _count(orders, status="placed") + _count(orders, status="accepted"),
        "recent_users": [public_user(row) for row in users[-8:][::-1]],
    })
