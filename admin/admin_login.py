from flask import Blueprint, jsonify, request

from backend.config import ADMIN_EMAIL, ADMIN_PASSWORD
from backend.json_store import load, new_id, public_user, save, utc_now
from backend.care_ops import norm_id
from backend.security import create_session, drop_session, hash_password, require_roles, verify_password

admin_login_bp = Blueprint("admin_login", __name__)


def bootstrap_admin():
    admins = load("admins")
    if any(row.get("email") == ADMIN_EMAIL for row in admins):
        return
    salt, digest = hash_password(ADMIN_PASSWORD)
    admins.append({
        "id": new_id("adm"),
        "email": ADMIN_EMAIL,
        "name": "Dhruva Care Admin",
        "role": "admin",
        "status": "active",
        "password_salt": salt,
        "password_hash": digest,
        "created_at": utc_now(),
    })
    save("admins", admins)


@admin_login_bp.post("/api/admin/login")
def admin_login():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    admin = next((row for row in load("admins") if row.get("email") == email), None)
    if not admin or admin.get("status") != "active":
        return jsonify({"error": "Invalid admin credentials"}), 401
    if not verify_password(password, admin["password_salt"], admin["password_hash"]):
        return jsonify({"error": "Invalid admin credentials"}), 401
    code = norm_id(payload.get("admin_code"))
    if not admin.get("admin_code_hash") or not code or not verify_password(code, admin["admin_code_salt"], admin["admin_code_hash"]):
        return jsonify({"error": "Invalid admin credentials"}), 401
    token, session = create_session(admin["id"], "admin", admin["email"])
    response = jsonify({
        "token": token,
        "admin": public_user(admin),
        "session_id": session["id"],
    })
    response.set_cookie("dhruva_care_session", token, httponly=True, samesite="Lax")
    return response


@admin_login_bp.get("/api/admin/session")
def admin_session():
    session, error = require_roles("admin")
    if error:
        return jsonify(error[0]), error[1]
    admin = next((row for row in load("admins") if row.get("id") == session["account_id"]), None)
    return jsonify({"authenticated": True, "admin": public_user(admin)})


@admin_login_bp.post("/api/admin/logout")
def admin_logout():
    drop_session()
    response = jsonify({"ok": True})
    response.delete_cookie("dhruva_care_session")
    return response
