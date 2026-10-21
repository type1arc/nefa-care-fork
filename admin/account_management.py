from flask import Blueprint, jsonify, request

from backend.json_store import load, public_user
from backend.region import is_northeast_state, normalize_state
from backend.care_ops import strip_secrets
from backend.security import require_roles

account_management_bp = Blueprint("account_management", __name__)

COLLECTIONS = {
    "users": "users",
    "doctors": "doctors",
    "pharmacies": "pharmacies",
    "hospitals": "hospitals",
}


@account_management_bp.get("/api/admin/accounts/<kind>")
def list_accounts(kind):
    session, error = require_roles("admin")
    if error:
        return jsonify(error[0]), error[1]
    store = COLLECTIONS.get(kind)
    if not store:
        return jsonify({"error": "Kind must be users, doctors, pharmacies, or hospitals"}), 400

    status = request.args.get("status")
    verification = request.args.get("verification_status")
    state = normalize_state(request.args.get("state"))
    query = (request.args.get("q") or "").strip().lower()

    rows = []
    for row in load(store):
        if status and row.get("status") != status:
            continue
        if verification and row.get("verification_status") != verification:
            continue
        loc = row.get("practice_location") or row.get("location") or {}
        if state and loc.get("state") != state:
            continue
        if loc.get("state") and not is_northeast_state(loc.get("state")):
            continue
        blob = " ".join(str(row.get(key, "")) for key in ("full_name", "name", "email", "phone", "specialty"))
        if query and query not in blob.lower():
            continue
        rows.append(public_user(row) if store == "users" else strip_secrets(row))

    return jsonify({"kind": kind, "count": len(rows), "items": rows})
