from flask import Blueprint, jsonify, request

from backend.care_ops import live_summary
from backend.json_store import find_by_id, load
from backend.region import is_northeast_state, normalize_state

doctor_directory_bp = Blueprint("doctor_directory", __name__)


def _is_listed(doctor):
    return (
        doctor.get("verification_status") == "approved"
        and doctor.get("status") == "active"
        and is_northeast_state((doctor.get("practice_location") or {}).get("state"))
    )


def public_doctor(doctor, include_availability=False):
    loc = doctor.get("practice_location") or {}
    card = {
        "id": doctor.get("id"),
        "full_name": doctor.get("full_name"),
        "specialty": doctor.get("specialty"),
        "bio": doctor.get("bio"),
        "consultation_fee": doctor.get("consultation_fee"),
        "photo": (doctor.get("documents") or {}).get("photo"),
        "location": loc,
        "verified": True,
    }
    card["live_presence"], card["patients_ahead"] = live_summary(doctor)
    if include_availability:
        card["availability"] = doctor.get("availability") or []
    return card


@doctor_directory_bp.get("/api/doctors")
def find_verified_doctors():
    specialty = (request.args.get("specialty") or "").strip().lower()
    state = normalize_state(request.args.get("state"))
    district = (request.args.get("district") or "").strip().lower()
    query = (request.args.get("q") or "").strip().lower()

    results = []
    for doctor in load("doctors"):
        if not _is_listed(doctor):
            continue
        loc = doctor.get("practice_location") or {}
        if state and loc.get("state") != state:
            continue
        if district and district not in (loc.get("district") or "").lower():
            continue
        if specialty and specialty not in (doctor.get("specialty") or "").lower():
            continue
        blob = f"{doctor.get('full_name', '')} {doctor.get('specialty', '')} {doctor.get('bio', '')}".lower()
        if query and query not in blob:
            continue
        results.append(public_doctor(doctor, include_availability=True))
    return jsonify({"region": "North East India", "count": len(results), "doctors": results})


@doctor_directory_bp.get("/api/doctors/<doctor_id>")
def doctor_card(doctor_id):
    doctor = find_by_id("doctors", doctor_id)
    if not doctor or not _is_listed(doctor):
        return jsonify({"error": "Verified doctor not found in North East India"}), 404
    return jsonify(public_doctor(doctor, include_availability=True))
