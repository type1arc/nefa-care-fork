"""Public pharmacy directory for Dhruva Care."""

from flask import Blueprint, jsonify, request

from .json_store import load
from .region import is_northeast_state, normalize_state

pharmacy_directory_bp = Blueprint("pharmacy_directory", __name__)


def public_pharmacy(pharmacy):
    location = pharmacy.get("location") or {}
    return {
        "id": pharmacy.get("id"),
        "name": pharmacy.get("name"),
        "kind": pharmacy.get("kind", "pharmacy"),
        "location": location,
        "inventory": pharmacy.get("inventory") or [],
        "delivery_time_mins": pharmacy.get("delivery_time_mins"),
        "verified": pharmacy.get("verification_status") == "approved",
    }


@pharmacy_directory_bp.get("/api/pharmacies")
def find_verified_pharmacies():
    state = normalize_state(request.args.get("state"))
    district = (request.args.get("district") or "").strip().lower()
    query = (request.args.get("q") or "").strip().lower()
    medicine = (request.args.get("medicine") or "").strip().lower()

    results = []
    for pharmacy in load("pharmacies"):
        if pharmacy.get("verification_status") != "approved" or pharmacy.get("status") != "active":
            continue
        location = pharmacy.get("location") or {}
        if not is_northeast_state(location.get("state")):
            continue
        if state and location.get("state") != state:
            continue
        if district and district not in (location.get("district") or "").lower():
            continue
        blob = f"{pharmacy.get('name', '')} {location.get('locality', '')} {location.get('district', '')}".lower()
        if query and query not in blob:
            continue
        inventory = [str(item).lower() for item in pharmacy.get("inventory") or []]
        if medicine and not any(medicine in item or item in medicine for item in inventory):
            continue
        results.append(public_pharmacy(pharmacy))

    return jsonify({"region": "North East India", "count": len(results), "pharmacies": results})
