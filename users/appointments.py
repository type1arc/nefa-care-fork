from flask import Blueprint, jsonify, request

from doctors.doctor_directory import _is_listed
from backend.json_store import find_by_id, load, new_id, upsert, utc_now
from backend.security import require_roles

appointments_bp = Blueprint("appointments", __name__)


def _slot_open(doctor, scheduled_for):
    taken = [
        row for row in load("appointments")
        if row.get("doctor_id") == doctor["id"]
        and row.get("scheduled_for") == scheduled_for
        and row.get("status") not in ("cancelled", "rejected")
    ]
    return not taken


@appointments_bp.post("/api/appointments")
def book_appointment():
    session, error = require_roles("user", "admin")
    if error:
        return jsonify(error[0]), error[1]
    payload = request.get_json(silent=True) or {}
    doctor_id = payload.get("doctor_id")
    scheduled_for = payload.get("scheduled_for")
    mode = payload.get("mode") or "in_person"
    if not doctor_id or not scheduled_for:
        return jsonify({"error": "doctor_id and scheduled_for are required"}), 400
    doctor = find_by_id("doctors", doctor_id)
    if not doctor or not _is_listed(doctor):
        return jsonify({"error": "Only verified North East doctors can be booked"}), 400
    if not _slot_open(doctor, scheduled_for):
        return jsonify({"error": "That slot is already taken"}), 409

    patient_id = payload.get("user_id") if session["role"] == "admin" else session["account_id"]
    appointment = {
        "id": new_id("apt"),
        "user_id": patient_id,
        "doctor_id": doctor_id,
        "scheduled_for": scheduled_for,
        "mode": mode,
        "reason": (payload.get("reason") or "").strip(),
        "status": "booked",
        "location": doctor.get("practice_location"),
        "created_at": utc_now(),
    }
    upsert("appointments", appointment)
    return jsonify(appointment), 201


@appointments_bp.get("/api/appointments")
def list_appointments():
    session, error = require_roles("user", "admin", "doctor")
    if error:
        return jsonify(error[0]), error[1]
    rows = load("appointments")
    if session["role"] == "user":
        rows = [row for row in rows if row.get("user_id") == session["account_id"]]
    elif session["role"] == "doctor":
        rows = [row for row in rows if row.get("doctor_id") == session["account_id"]]
    return jsonify({"appointments": rows, "count": len(rows)})


@appointments_bp.post("/api/appointments/<appointment_id>/cancel")
def cancel_appointment(appointment_id):
    session, error = require_roles("user", "admin", "doctor")
    if error:
        return jsonify(error[0]), error[1]
    row = find_by_id("appointments", appointment_id)
    if not row:
        return jsonify({"error": "Appointment not found"}), 404
    if session["role"] == "user" and row.get("user_id") != session["account_id"]:
        return jsonify({"error": "Not your appointment"}), 403
    row["status"] = "cancelled"
    row["cancelled_at"] = utc_now()
    upsert("appointments", row)
    return jsonify(row)
