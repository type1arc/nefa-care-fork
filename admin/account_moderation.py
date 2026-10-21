from flask import Blueprint, jsonify, request

from backend.json_store import find_by_id, upsert, utc_now, delete_by_id
from backend.care_ops import strip_secrets
from backend.security import require_roles

account_moderation_bp = Blueprint("account_moderation", __name__)

STORES = {
    "user": "users",
    "doctor": "doctors",
    "pharmacy": "pharmacies",
    "hospital": "hospitals",
}


def _load_account(kind, account_id):
    store = STORES.get(kind)
    if not store:
        return None, None, (jsonify({"error": "Unknown account kind"}), 400)
    row = find_by_id(store, account_id)
    if not row:
        return store, None, (jsonify({"error": "Account not found"}), 404)
    return store, row, None


@account_moderation_bp.post("/api/admin/accounts/<kind>/<account_id>/suspend")
def suspend_account(kind, account_id):
    session, error = require_roles("admin")
    if error:
        return jsonify(error[0]), error[1]
    store, row, fail = _load_account(kind, account_id)
    if fail:
        return fail
    note = (request.get_json(silent=True) or {}).get("note") or "Suspended by admin"
    row["status"] = "suspended"
    row["suspended_at"] = utc_now()
    row["suspended_by"] = session["account_id"]
    row["moderation_note"] = note
    upsert(store, row)
    return jsonify(strip_secrets(row))


@account_moderation_bp.post("/api/admin/accounts/<kind>/<account_id>/restore")
def restore_account(kind, account_id):
    session, error = require_roles("admin")
    if error:
        return jsonify(error[0]), error[1]
    store, row, fail = _load_account(kind, account_id)
    if fail:
        return fail
    row["status"] = "active" if row.get("verification_status") in (None, "approved") else row.get("status") or "active"
    row["restored_at"] = utc_now()
    row["restored_by"] = session["account_id"]
    upsert(store, row)
    return jsonify(strip_secrets(row))


@account_moderation_bp.post("/api/admin/accounts/<kind>/<account_id>/remove")
def remove_account(kind, account_id):
    session, error = require_roles("admin")
    if error:
        return jsonify(error[0]), error[1]
    store, row, fail = _load_account(kind, account_id)
    if fail:
        return fail
    payload = request.get_json(silent=True) or {}
    hard = bool(payload.get("hard_delete"))
    if hard:
        delete_by_id(store, account_id)
        return jsonify({"removed": True, "mode": "deleted", "id": account_id})
    row["status"] = "removed"
    row["removed_at"] = utc_now()
    row["removed_by"] = session["account_id"]
    row["moderation_note"] = payload.get("note") or "Account removed"
    upsert(store, row)
    return jsonify({"removed": True, "mode": "soft", "account": strip_secrets(row)})
