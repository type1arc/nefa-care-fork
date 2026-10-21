"""Patient-owned JSON profiles and explicit clinician access grants."""

from flask import Blueprint, jsonify, request

from backend.json_store import find_by_id, load, public_user, upsert, utc_now
from backend.security import require_roles
from doctors.doctor_directory import _is_listed

patient_records_bp = Blueprint("patient_records", __name__)

PROFILE_FIELDS = {"full_name", "phone", "age", "sex", "location", "emergency_contact", "medical_profile"}


def _patient(user_id):
    return find_by_id("users", user_id)


def _grant_for(patient, doctor_id):
    return next((item for item in patient.get("doctor_access") or []
                 if item.get("doctor_id") == doctor_id and item.get("status") == "approved"), None)


@patient_records_bp.put("/api/users/me/profile")
def update_profile():
    session, error = require_roles("user")
    if error:
        return jsonify(error[0]), error[1]
    patient = _patient(session["account_id"])
    if not patient:
        return jsonify({"error": "User profile not found"}), 404
    payload = request.get_json(silent=True) or {}
    changes = {key: value for key, value in payload.items() if key in PROFILE_FIELDS}
    if not changes:
        return jsonify({"error": "No editable profile fields supplied"}), 400
    patient.update(changes)
    patient["profile_updated_at"] = utc_now()
    upsert("users", patient)
    return jsonify(public_user(patient))


@patient_records_bp.post("/api/users/me/doctors/<doctor_id>/access")
def set_doctor_access(doctor_id):
    """The patient is the only party that can approve or revoke profile access."""
    session, error = require_roles("user")
    if error:
        return jsonify(error[0]), error[1]
    patient = _patient(session["account_id"])
    doctor = find_by_id("doctors", doctor_id)
    if not patient or not doctor or not _is_listed(doctor):
        return jsonify({"error": "Verified doctor or patient not found"}), 404
    approved = bool((request.get_json(silent=True) or {}).get("approved"))
    grants = patient.setdefault("doctor_access", [])
    grant = next((item for item in grants if item.get("doctor_id") == doctor_id), None)
    if grant is None:
        grant = {"doctor_id": doctor_id}
        grants.append(grant)
    grant.update({"status": "approved" if approved else "revoked", "updated_at": utc_now()})
    upsert("users", patient)
    return jsonify({"doctor_id": doctor_id, "status": grant["status"]})


@patient_records_bp.get("/api/doctors/me/patients/<patient_id>")
def doctor_patient_profile(patient_id):
    session, error = require_roles("doctor")
    if error:
        return jsonify(error[0]), error[1]
    patient = _patient(patient_id)
    if not patient or not _grant_for(patient, session["account_id"]):
        # Do not reveal whether a patient exists when consent is missing.
        return jsonify({"error": "Patient approval is required before this profile can be viewed"}), 403
    return jsonify(public_user(patient))
