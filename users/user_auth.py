import secrets

from flask import Blueprint, jsonify, request

from backend.config import RECORDS_DIR
from backend.json_store import load, new_id, public_user, upsert, utc_now
from backend.region import validate_location
from backend.security import create_session, drop_session, hash_password, require_roles, save_upload, verify_password

user_auth_bp = Blueprint("user_auth", __name__)


def _empty_medical_index():
    return {
        "history_pdfs": [],
        "consultation_pdfs": [],
        "notes": [],
    }


@user_auth_bp.post("/api/users/signup")
def signup():
    payload = request.get_json(silent=True) or {}
    location, loc_error = validate_location(payload)
    if loc_error:
        return jsonify({"error": loc_error}), 400

    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    full_name = (payload.get("full_name") or payload.get("name") or "").strip()
    if not email or not password or not full_name:
        return jsonify({"error": "full_name, email, and password are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if any(row.get("email") == email for row in load("users")):
        return jsonify({"error": "Email already registered"}), 409

    salt, digest = hash_password(password)
    user = {
        "id": new_id("usr"),
        "role": "user",
        "status": "active",
        "full_name": full_name,
        "email": email,
        "phone": (payload.get("phone") or "").strip(),
        "age": payload.get("age"),
        "sex": payload.get("sex"),
        "location": location,
        "password_salt": salt,
        "password_hash": digest,
        "medical_records": _empty_medical_index(),
        "medical_profile": {},
        "doctor_access": [],
        "patient_code": f"PT-{secrets.token_hex(4).upper()}",
        "created_at": utc_now(),
    }
    upsert("users", user)
    token, _ = create_session(user["id"], "user", email)
    response = jsonify({"token": token, "user": public_user(user)})
    response.set_cookie("dhruva_care_session", token, httponly=True, samesite="Lax")
    return response, 201


@user_auth_bp.post("/api/users/login")
def login():
    payload = request.get_json(silent=True) or {}
    login_id = (payload.get("email") or payload.get("username") or "").strip().lower()
    password = payload.get("password") or ""
    user = next((row for row in load("users") if row.get("email") == login_id), None)
    if not user or user.get("status") in ("suspended", "removed"):
        return jsonify({"error": "Invalid credentials or account unavailable"}), 401
    if not verify_password(password, user["password_salt"], user["password_hash"]):
        return jsonify({"error": "Invalid credentials or account unavailable"}), 401
    token, _ = create_session(user["id"], "user", user["email"])
    response = jsonify({"token": token, "user": public_user(user)})
    response.set_cookie("dhruva_care_session", token, httponly=True, samesite="Lax")
    return response


@user_auth_bp.get("/api/users/me")
def me():
    session, error = require_roles("user", "admin")
    if error:
        return jsonify(error[0]), error[1]
    user = next((row for row in load("users") if row.get("id") == session["account_id"]), None)
    if not user and session["role"] == "admin":
        return jsonify({"role": "admin", "email": session["email"]})
    return jsonify(public_user(user))


@user_auth_bp.post("/api/users/logout")
def logout():
    drop_session()
    response = jsonify({"ok": True})
    response.delete_cookie("dhruva_care_session")
    return response


@user_auth_bp.get("/api/users/me/records")
def list_records():
    session, error = require_roles("user", "admin")
    if error:
        return jsonify(error[0]), error[1]
    user = next((row for row in load("users") if row.get("id") == session["account_id"]), None)
    if not user:
        return jsonify({"error": "User profile not found"}), 404
    return jsonify(user.get("medical_records") or _empty_medical_index())


@user_auth_bp.post("/api/users/me/records")
def attach_record_pdf():
    """Store a PDF path on the same users.json record (history or past consultation)."""
    session, error = require_roles("user")
    if error:
        return jsonify(error[0]), error[1]
    user = next((row for row in load("users") if row.get("id") == session["account_id"]), None)
    if not user:
        return jsonify({"error": "User profile not found"}), 404

    kind = (request.form.get("kind") or (request.get_json(silent=True) or {}).get("kind") or "history").strip()
    title = (request.form.get("title") or (request.get_json(silent=True) or {}).get("title") or "Medical document").strip()
    appointment_id = request.form.get("appointment_id") or (request.get_json(silent=True) or {}).get("appointment_id")

    try:
        pdf_path = save_upload(RECORDS_DIR, request.files.get("file"), f"{user['id']}_{kind}") if request.files else None
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    pdf_path = pdf_path or (request.get_json(silent=True) or {}).get("pdf_path")
    if not pdf_path:
        return jsonify({"error": "Upload a PDF or pass pdf_path"}), 400

    entry = {
        "id": new_id("rec"),
        "title": title,
        "pdf_path": pdf_path,
        "appointment_id": appointment_id,
        "uploaded_at": utc_now(),
    }
    records = user.get("medical_records") or _empty_medical_index()
    bucket = "consultation_pdfs" if kind in ("consultation", "consultations") else "history_pdfs"
    records.setdefault(bucket, []).append(entry)
    user["medical_records"] = records
    upsert("users", user)
    return jsonify(public_user(user)), 201
