import hashlib
import hmac
import os
import secrets
import time

from flask import request

from .config import PBKDF2_ITERATIONS, SESSION_TTL_SECONDS
from .json_store import load, new_id, save, utc_now


def new_doctor_code():
    """An opaque, non-sequential code suitable for a patient to enter."""
    return f"DOC-{secrets.token_urlsafe(7).replace('-', '').replace('_', '')[:10].upper()}"


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    ).hex()
    return salt, digest


def verify_password(password, salt, expected_hash):
    _, digest = hash_password(password, salt)
    return hmac.compare_digest(digest, expected_hash)


def create_session(account_id, role, email):
    sessions = load("sessions")
    token = secrets.token_urlsafe(32)
    row = {
        "id": new_id("ses"),
        "token": token,
        "account_id": account_id,
        "role": role,
        "email": email,
        "created_at": utc_now(),
        "expires_at": time.time() + SESSION_TTL_SECONDS,
    }
    sessions.append(row)
    save("sessions", sessions)
    return token, row


def get_session():
    header = request.headers.get("Authorization", "")
    token = ""
    if header.lower().startswith("bearer "):
        token = header.split(" ", 1)[1].strip()
    token = token or request.cookies.get("dhruva_care_session") or request.args.get("token")
    if not token:
        return None
    now = time.time()
    for row in load("sessions"):
        if row.get("token") == token and row.get("expires_at", 0) > now:
            return row
    return None


def drop_session(token=None):
    token = token or (get_session() or {}).get("token")
    if not token:
        return False
    rows = [row for row in load("sessions") if row.get("token") != token]
    save("sessions", rows)
    return True


def require_roles(*roles):
    session = get_session()
    if not session:
        return None, ({"error": "Login required"}, 401)
    if roles and session.get("role") not in roles:
        return None, ({"error": "Not allowed for this role"}, 403)
    return session, None


def save_upload(folder, file_storage, prefix):
    if not file_storage or not file_storage.filename:
        return None
    ext = os.path.splitext(file_storage.filename)[1].lower() or ".bin"
    allowed = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
    if ext not in allowed:
        raise ValueError("Only PDF or image files are accepted")
    os.makedirs(folder, exist_ok=True)
    filename = f"{prefix}_{secrets.token_hex(6)}{ext}"
    path = os.path.join(folder, filename)
    file_storage.save(path)
    return path.replace("\\", "/")
