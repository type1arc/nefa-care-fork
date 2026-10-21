from flask import Blueprint, jsonify, request

from backend.config import LICENSE_DIR, PHOTO_DIR
from backend.json_store import find_by_id, load, new_id, save, upsert, utc_now
from backend.region import validate_location
from backend.care_ops import norm_id, strip_secrets
from backend.security import create_session, hash_password, new_doctor_code, require_roles, save_upload, verify_password

doctor_verification_bp = Blueprint("doctor_verification", __name__)


def _doctor_or_404(doctor_id):
    doctor = find_by_id("doctors", doctor_id)
    if not doctor:
        return None, (jsonify({"error": "Doctor not found"}), 404)
    return doctor, None


@doctor_verification_bp.post("/api/doctors/register")
def submit_doctor_application():
    """Doctor self-submits certificate, photo, and practice location for review."""
    payload = request.form.to_dict() if request.form else (request.get_json(silent=True) or {})
    location, loc_error = validate_location(payload)
    if loc_error:
        return jsonify({"error": loc_error}), 400

    payload = dict(payload)
    payload["registration_no"] = (payload.get("smc_number") or payload.get("registration_no") or "").strip()
    required = ("full_name", "email", "registration_no", "nmr_id", "specialty", "password")
    missing = [field for field in required if not (payload.get(field) or "").strip()]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    email = payload["email"].strip().lower()
    password = payload["password"]
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    if any(row.get("email") == email for row in load("doctors")):
        return jsonify({"error": "A doctor application already exists for this email"}), 409
    if any(norm_id(row.get("smc_number") or row.get("registration_no")) == norm_id(payload["registration_no"]) for row in load("doctors")):
        return jsonify({"error": "This State Medical Council number is already registered"}), 409
    if any(norm_id(row.get("nmr_id")) == norm_id(payload["nmr_id"]) for row in load("doctors")):
        return jsonify({"error": "This NMR ID / UID is already registered"}), 409
    hospital_id = (payload.get("hospital_id") or "").strip() or None
    if hospital_id and not any(h["id"] == hospital_id and h.get("verification_status") == "approved" for h in load("hospitals")):
        return jsonify({"error": "Affiliated hospital must be a verified hospital"}), 400

    try:
        certificate_path = save_upload(LICENSE_DIR, request.files.get("certificate"), "doc_cert") if request.files else None
        photo_path = save_upload(PHOTO_DIR, request.files.get("photo"), "doc_photo") if request.files else None
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    password_salt, password_hash = hash_password(password)
    doctor = {
        "id": new_id("doc"),
        "role": "doctor",
        "status": "pending",
        "verification_status": "pending",
        "full_name": payload["full_name"].strip(),
        "email": email,
        "password_salt": password_salt,
        "password_hash": password_hash,
        "phone": (payload.get("phone") or "").strip(),
        "registration_no": payload["registration_no"].strip(),
        "smc_number": payload["registration_no"].strip(),
        "nmr_id": payload["nmr_id"].strip(),
        "hospital_id": hospital_id,
        "doctor_code": new_doctor_code(),
        "specialty": payload["specialty"].strip(),
        "bio": (payload.get("bio") or "").strip(),
        "practice_location": location,
        "documents": {
            "certificate": certificate_path or payload.get("certificate_path"),
            "photo": photo_path or payload.get("photo_path"),
        },
        "availability": payload.get("availability") or [],
        "consultation_fee": int(payload.get("consultation_fee") or 0),
        "created_at": utc_now(),
        "reviewed_at": None,
        "review_note": "",
    }
    upsert("doctors", doctor)
    return jsonify(strip_secrets(doctor)), 201


@doctor_verification_bp.post("/api/doctors/login")
def doctor_login():
    payload = request.get_json(silent=True) or {}
    smc, nmr = norm_id(payload.get("smc_number")), norm_id(payload.get("nmr_id"))
    password = payload.get("password") or ""
    doctor = next((row for row in load("doctors") if smc and nmr
                   and norm_id(row.get("smc_number") or row.get("registration_no")) == smc
                   and norm_id(row.get("nmr_id")) == nmr), None)
    if not doctor or doctor.get("status") != "active" or not doctor.get("password_hash"):
        return jsonify({"error": "Invalid credentials or doctor account unavailable"}), 401
    if not verify_password(password, doctor["password_salt"], doctor["password_hash"]):
        return jsonify({"error": "Invalid credentials or doctor account unavailable"}), 401
    token, _ = create_session(doctor["id"], "doctor", doctor["email"])
    response = jsonify({"token": token, "doctor": strip_secrets(doctor)})
    response.set_cookie("dhruva_care_session", token, httponly=True, samesite="Lax")
    return response


@doctor_verification_bp.get("/api/admin/doctors/pending")
def list_pending_doctors():
    session, error = require_roles("admin")
    if error:
        return jsonify(error[0]), error[1]
    rows = [strip_secrets(row) for row in load("doctors") if row.get("verification_status") == "pending"]
    return jsonify({"pending": rows, "count": len(rows)})


@doctor_verification_bp.get("/api/admin/doctors/<doctor_id>")
def review_packet(doctor_id):
    session, error = require_roles("admin")
    if error:
        return jsonify(error[0]), error[1]
    doctor, fail = _doctor_or_404(doctor_id)
    if fail:
        return fail
    return jsonify({
        "doctor": strip_secrets(doctor),
        "checklist": {
            "certificate": bool((doctor.get("documents") or {}).get("certificate")),
            "photo": bool((doctor.get("documents") or {}).get("photo")),
            "practice_location": bool((doctor.get("practice_location") or {}).get("state")),
        },
    })


@doctor_verification_bp.post("/api/admin/doctors/<doctor_id>/approve")
def approve_doctor(doctor_id):
    session, error = require_roles("admin")
    if error:
        return jsonify(error[0]), error[1]
    doctor, fail = _doctor_or_404(doctor_id)
    if fail:
        return fail
    docs = doctor.get("documents") or {}
    if not docs.get("certificate") or not docs.get("photo"):
        return jsonify({"error": "Certificate and photo must be on file before approval"}), 400
    if not (doctor.get("practice_location") or {}).get("state"):
        return jsonify({"error": "Practice location in North East India is required"}), 400
    note = (request.get_json(silent=True) or {}).get("note", "")
    doctor["verification_status"] = "approved"
    doctor["status"] = "active"
    doctor["reviewed_at"] = utc_now()
    doctor["reviewed_by"] = session["account_id"]
    doctor["review_note"] = note
    upsert("doctors", doctor)
    return jsonify(strip_secrets(doctor))


@doctor_verification_bp.post("/api/admin/doctors/<doctor_id>/reject")
def reject_doctor(doctor_id):
    session, error = require_roles("admin")
    if error:
        return jsonify(error[0]), error[1]
    doctor, fail = _doctor_or_404(doctor_id)
    if fail:
        return fail
    note = (request.get_json(silent=True) or {}).get("note") or "Documents or location did not meet verification rules"
    doctor["verification_status"] = "rejected"
    doctor["status"] = "rejected"
    doctor["reviewed_at"] = utc_now()
    doctor["reviewed_by"] = session["account_id"]
    doctor["review_note"] = note
    upsert("doctors", doctor)
    return jsonify(strip_secrets(doctor))
