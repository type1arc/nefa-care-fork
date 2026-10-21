from flask import Blueprint, jsonify, request

from .config import LICENSE_DIR
from .json_store import find_by_id, load, new_id, upsert, utc_now
from .region import validate_location
from .security import require_roles, save_upload

pharmacy_verification_bp = Blueprint("pharmacy_verification", __name__)


@pharmacy_verification_bp.post("/api/pharmacies/register")
def submit_pharmacy():
    payload = request.form.to_dict() if request.form else (request.get_json(silent=True) or {})
    location, loc_error = validate_location(payload)
    if loc_error:
        return jsonify({"error": loc_error}), 400
    name = (payload.get("name") or "").strip()
    license_no = (payload.get("license_no") or "").strip()
    if not name or not license_no:
        return jsonify({"error": "Pharmacy name and license number are required"}), 400

    try:
        license_path = save_upload(LICENSE_DIR, request.files.get("license"), "pharm_lic") if request.files else None
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    inventory = payload.get("inventory") or []
    if isinstance(inventory, str):
        inventory = [item.strip() for item in inventory.split(",") if item.strip()]

    pharmacy = {
        "id": new_id("phm"),
        "role": "pharmacy",
        "kind": (payload.get("kind") or "pharmacy").strip().lower(),
        "name": name,
        "email": (payload.get("email") or "").strip().lower(),
        "phone": (payload.get("phone") or "").strip(),
        "license_no": license_no,
        "license_document": license_path or payload.get("license_path"),
        "location": location,
        "inventory": inventory,
        "status": "pending",
        "verification_status": "pending",
        "created_at": utc_now(),
        "reviewed_at": None,
        "review_note": "",
    }
    upsert("pharmacies", pharmacy)
    return jsonify(pharmacy), 201


@pharmacy_verification_bp.get("/api/admin/pharmacies/pending")
def pending_pharmacies():
    session, error = require_roles("admin")
    if error:
        return jsonify(error[0]), error[1]
    rows = [row for row in load("pharmacies") if row.get("verification_status") == "pending"]
    return jsonify({"pending": rows, "count": len(rows)})


@pharmacy_verification_bp.post("/api/admin/pharmacies/<pharmacy_id>/approve")
def approve_pharmacy(pharmacy_id):
    session, error = require_roles("admin")
    if error:
        return jsonify(error[0]), error[1]
    pharmacy = find_by_id("pharmacies", pharmacy_id)
    if not pharmacy:
        return jsonify({"error": "Pharmacy not found"}), 404
    if not pharmacy.get("license_document"):
        return jsonify({"error": "Pharmacy license file is required before approval"}), 400
    pharmacy["verification_status"] = "approved"
    pharmacy["status"] = "active"
    pharmacy["reviewed_at"] = utc_now()
    pharmacy["reviewed_by"] = session["account_id"]
    pharmacy["review_note"] = (request.get_json(silent=True) or {}).get("note", "")
    upsert("pharmacies", pharmacy)
    return jsonify(pharmacy)


@pharmacy_verification_bp.post("/api/admin/pharmacies/<pharmacy_id>/reject")
def reject_pharmacy(pharmacy_id):
    session, error = require_roles("admin")
    if error:
        return jsonify(error[0]), error[1]
    pharmacy = find_by_id("pharmacies", pharmacy_id)
    if not pharmacy:
        return jsonify({"error": "Pharmacy not found"}), 404
    pharmacy["verification_status"] = "rejected"
    pharmacy["status"] = "rejected"
    pharmacy["reviewed_at"] = utc_now()
    pharmacy["reviewed_by"] = session["account_id"]
    pharmacy["review_note"] = (request.get_json(silent=True) or {}).get("note") or "License rejected"
    upsert("pharmacies", pharmacy)
    return jsonify(pharmacy)
