from flask import Blueprint, jsonify, request

from .doctor_directory import _is_listed, public_doctor
from backend.json_store import find_by_id, upsert
from backend.security import require_roles

doctor_availability_bp = Blueprint("doctor_availability", __name__)


@doctor_availability_bp.get("/api/doctors/<doctor_id>/location")
def doctor_location(doctor_id):
    doctor = find_by_id("doctors", doctor_id)
    if not doctor or not _is_listed(doctor):
        return jsonify({"error": "Verified doctor not found"}), 404
    return jsonify({
        "doctor_id": doctor_id,
        "practice_location": doctor.get("practice_location"),
        "availability": doctor.get("availability") or [],
    })


@doctor_availability_bp.get("/api/doctors/<doctor_id>/availability")
def get_availability(doctor_id):
    doctor = find_by_id("doctors", doctor_id)
    if not doctor or not _is_listed(doctor):
        return jsonify({"error": "Verified doctor not found"}), 404
    return jsonify({"doctor_id": doctor_id, "slots": doctor.get("availability") or []})


@doctor_availability_bp.put("/api/doctors/<doctor_id>/availability")
def set_availability(doctor_id):
    session, error = require_roles("admin", "doctor")
    if error:
        return jsonify(error[0]), error[1]
    doctor = find_by_id("doctors", doctor_id)
    if not doctor:
        return jsonify({"error": "Doctor not found"}), 404
    if session["role"] == "doctor" and session["account_id"] != doctor_id:
        return jsonify({"error": "Can only edit your own roster"}), 403
    payload = request.get_json(silent=True) or {}
    slots = payload.get("slots") or payload.get("availability") or []
    cleaned = []
    for slot in slots:
        cleaned.append({
            "day": slot.get("day"),
            "start": slot.get("start"),
            "end": slot.get("end"),
            "mode": slot.get("mode") or "in_person",
            "open": slot.get("open", True),
        })
    doctor["availability"] = cleaned
    upsert("doctors", doctor)
    return jsonify(public_doctor(doctor, include_availability=True))
