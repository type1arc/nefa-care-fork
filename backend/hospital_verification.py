from flask import Blueprint, jsonify, request

from .config import LICENSE_DIR
from .json_store import find_by_id, load, new_id, upsert, utc_now
from .region import validate_location
from .care_ops import norm_id
from .security import create_session, hash_password, require_roles, save_upload, verify_password

hospital_verification_bp = Blueprint("hospital_verification", __name__)


def public_hospital(row):
    """Never expose password material."""
    return {k: v for k, v in row.items() if not k.startswith("password_")}


def _as_list(value):
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value or []


def _as_bool(value):
    return str(value).strip().lower() in ("1", "true", "yes", "on")


@hospital_verification_bp.post("/api/hospitals/register")
def submit_hospital():
    payload = request.form.to_dict() if request.form else (request.get_json(silent=True) or {})
    location, loc_error = validate_location(payload)
    if loc_error:
        return jsonify({"error": loc_error}), 400
    name = (payload.get("name") or "").strip()
    license_no = (payload.get("license_no") or "").strip()
    hfr_id = (payload.get("hfr_id") or "").strip()
    if not name or not license_no or not hfr_id:
        return jsonify({"error": "Hospital name, registration/license number and HFR ID are required"}), 400
    if any(norm_id(h.get("license_no")) == norm_id(license_no) for h in load("hospitals")):
        return jsonify({"error": "This registration/license number is already registered"}), 409
    if any(norm_id(h.get("hfr_id")) == norm_id(hfr_id) for h in load("hospitals")):
        return jsonify({"error": "This HFR ID is already registered"}), 409
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    if not email:
        return jsonify({"error": "Email is required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    if any(row.get("email") == email for row in load("hospitals")):
        return jsonify({"error": "A hospital application already exists for this email"}), 409
    password_salt, password_hash = hash_password(password)

    try:
        license_path = save_upload(LICENSE_DIR, request.files.get("license"), "hosp_lic") if request.files else None
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    hospital = {
        "id": new_id("hsp"),
        "role": "hospital",
        "name": name,
        "email": email,
        "password_salt": password_salt,
        "password_hash": password_hash,
        "phone": (payload.get("phone") or "").strip(),
        "license_no": license_no,
        "hfr_id": hfr_id,
        "affiliated_to": (payload.get("affiliated_to") or "").strip(),
        "license_document": license_path or payload.get("license_path"),
        "location": location,
        "departments": _as_list(payload.get("departments")),
        "emergency_capable": _as_bool(payload.get("emergency_capable")),
        "status": "pending",
        "verification_status": "pending",
        "created_at": utc_now(),
        "reviewed_at": None,
        "review_note": "",
    }
    upsert("hospitals", hospital)
    return jsonify(public_hospital(hospital)), 201


@hospital_verification_bp.get("/api/admin/hospitals/pending")
def pending_hospitals():
    session, error = require_roles("admin")
    if error:
        return jsonify(error[0]), error[1]
    rows = [row for row in load("hospitals") if row.get("verification_status") == "pending"]
    rows = [public_hospital(row) for row in rows]
    return jsonify({"pending": rows, "count": len(rows)})


@hospital_verification_bp.post("/api/admin/hospitals/<hospital_id>/approve")
def approve_hospital(hospital_id):
    session, error = require_roles("admin")
    if error:
        return jsonify(error[0]), error[1]
    hospital = find_by_id("hospitals", hospital_id)
    if not hospital:
        return jsonify({"error": "Hospital not found"}), 404
    if not hospital.get("license_document"):
        return jsonify({"error": "Hospital license file is required before approval"}), 400
    hospital["verification_status"] = "approved"
    hospital["status"] = "active"
    hospital["reviewed_at"] = utc_now()
    hospital["reviewed_by"] = session["account_id"]
    hospital["review_note"] = (request.get_json(silent=True) or {}).get("note", "")
    upsert("hospitals", hospital)
    return jsonify(public_hospital(hospital))


@hospital_verification_bp.post("/api/admin/hospitals/<hospital_id>/reject")
def reject_hospital(hospital_id):
    session, error = require_roles("admin")
    if error:
        return jsonify(error[0]), error[1]
    hospital = find_by_id("hospitals", hospital_id)
    if not hospital:
        return jsonify({"error": "Hospital not found"}), 404
    hospital["verification_status"] = "rejected"
    hospital["status"] = "rejected"
    hospital["reviewed_at"] = utc_now()
    hospital["reviewed_by"] = session["account_id"]
    hospital["review_note"] = (request.get_json(silent=True) or {}).get("note") or "License rejected"
    upsert("hospitals", hospital)
    return jsonify(public_hospital(hospital))


@hospital_verification_bp.post("/api/hospitals/login")
def hospital_login():
    payload = request.get_json(silent=True) or {}
    lic, hfr = norm_id(payload.get("license_no")), norm_id(payload.get("hfr_id"))
    password = payload.get("password") or ""
    hospital = next((row for row in load("hospitals") if lic and hfr
                     and norm_id(row.get("license_no")) == lic and norm_id(row.get("hfr_id")) == hfr), None)
    if not hospital or hospital.get("status") != "active" or not hospital.get("password_hash"):
        return jsonify({"error": "Invalid credentials or hospital account unavailable"}), 401
    if not verify_password(password, hospital["password_salt"], hospital["password_hash"]):
        return jsonify({"error": "Invalid credentials or hospital account unavailable"}), 401
    token, _ = create_session(hospital["id"], "hospital", hospital["email"])
    response = jsonify({"token": token, "hospital": public_hospital(hospital)})
    response.set_cookie("dhruva_care_session", token, httponly=True, samesite="Lax")
    return response


@hospital_verification_bp.get("/api/hospitals/me")
def hospital_me():
    session, error = require_roles("hospital")
    if error:
        return jsonify(error[0]), error[1]
    hospital = find_by_id("hospitals", session["account_id"])
    if not hospital:
        return jsonify({"error": "Hospital not found"}), 404
    return jsonify(public_hospital(hospital))
