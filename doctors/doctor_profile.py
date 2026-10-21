from flask import Blueprint, jsonify

from .doctor_directory import _is_listed, public_doctor
from backend.json_store import find_by_id, load

doctor_profile_bp = Blueprint("doctor_profile", __name__)


@doctor_profile_bp.get("/api/doctors/<doctor_id>/profile")
def doctor_profile(doctor_id):
    doctor = find_by_id("doctors", doctor_id)
    if not doctor or not _is_listed(doctor):
        return jsonify({"error": "Verified doctor not found"}), 404

    upcoming = [
        {
            "id": row.get("id"),
            "scheduled_for": row.get("scheduled_for"),
            "mode": row.get("mode"),
            "status": row.get("status"),
        }
        for row in load("appointments")
        if row.get("doctor_id") == doctor_id and row.get("status") in ("booked", "confirmed")
    ]
    profile = public_doctor(doctor, include_availability=True)
    profile.update({
        "registration_no": doctor.get("registration_no"),
        "upcoming_slots_held": len(upcoming),
        "hospital_id": doctor.get("hospital_id"),
    })
    return jsonify(profile)
