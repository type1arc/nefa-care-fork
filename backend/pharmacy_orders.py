from flask import Blueprint, jsonify, request

from .json_store import find_by_id, load, new_id, upsert, utc_now
from .security import require_roles

pharmacy_orders_bp = Blueprint("pharmacy_orders", __name__)

# Only this server-side catalogue is exempt from the doctor-code check.
OTC_MEDICINES = {"paracetamol", "ibuprofen", "ors", "cetirizine", "vitamin d3"}


def _name(item):
    return (item.get("name") if isinstance(item, dict) else str(item)).strip()


def _is_otc(item):
    return _name(item).lower() in OTC_MEDICINES


@pharmacy_orders_bp.post("/api/orders")
def place_order():
    session, error = require_roles("user", "admin")
    if error:
        return jsonify(error[0]), error[1]
    payload = request.get_json(silent=True) or {}
    pharmacy = find_by_id("pharmacies", payload.get("pharmacy_id") or "")
    if not pharmacy or pharmacy.get("verification_status") != "approved" or pharmacy.get("status") != "active":
        return jsonify({"error": "Choose a verified, active pharmacy or drug house"}), 400

    rx = find_by_id("prescriptions", payload.get("prescription_id") or "")
    items = payload.get("items") or ([item.get("name") for item in (rx or {}).get("medicines") or []])
    if not items:
        return jsonify({"error": "At least one medicine is required"}), 400
    prescription_only = [item for item in items if not _is_otc(item)]
    if prescription_only:
        if not rx:
            return jsonify({"error": "A prescription is required for non-OTC medicines"}), 400
        if session["role"] == "user" and rx.get("user_id") != session["account_id"]:
            return jsonify({"error": "Not your prescription"}), 403
        doctor = find_by_id("doctors", rx.get("doctor_id") or "")
        entered_code = (payload.get("doctor_code") or "").strip().upper()
        if not doctor or not doctor.get("doctor_code") or entered_code != doctor["doctor_code"]:
            return jsonify({"error": "Enter the unique code for the prescribing doctor"}), 403
    elif rx and session["role"] == "user" and rx.get("user_id") != session["account_id"]:
        return jsonify({"error": "Not your prescription"}), 403

    stock = [str(item).lower() for item in (pharmacy.get("inventory") or [])]
    accepted, skipped = [], []
    for item in items:
        name = _name(item)
        (accepted if any(name.lower() in entry or entry in name.lower() for entry in stock) else skipped).append(name)
    if not accepted:
        return jsonify({"error": "None of the requested medicines are in stock at this outlet"}), 400

    order = {"id": new_id("ord"), "user_id": (rx or {}).get("user_id") or session["account_id"],
             "prescription_id": (rx or {}).get("id"), "pharmacy_id": pharmacy["id"],
             "outlet_kind": pharmacy.get("kind"), "items": accepted, "unavailable": skipped,
             "fulfillment": payload.get("fulfillment") or "pickup", "status": "placed",
             "requires_doctor_code": bool(prescription_only), "created_at": utc_now()}
    upsert("orders", order)
    if rx:
        rx["status"] = "ordered"
        upsert("prescriptions", rx)
    return jsonify(order), 201


@pharmacy_orders_bp.get("/api/orders")
def list_orders():
    session, error = require_roles("user", "admin")
    if error:
        return jsonify(error[0]), error[1]
    rows = load("orders")
    if session["role"] == "user":
        rows = [row for row in rows if row.get("user_id") == session["account_id"]]
    return jsonify({"orders": rows})


@pharmacy_orders_bp.post("/api/orders/<order_id>/status")
def update_order(order_id):
    session, error = require_roles("admin")
    if error:
        return jsonify(error[0]), error[1]
    order = find_by_id("orders", order_id)
    if not order:
        return jsonify({"error": "Order not found"}), 404
    status = (request.get_json(silent=True) or {}).get("status")
    allowed = {"placed", "accepted", "packed", "dispatched", "completed", "cancelled"}
    if status not in allowed:
        return jsonify({"error": f"status must be one of {sorted(allowed)}"}), 400
    order["status"], order["updated_at"] = status, utc_now()
    upsert("orders", order)
    return jsonify(order)
