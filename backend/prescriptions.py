from flask import Blueprint, jsonify, request

from .json_store import find_by_id, load, new_id, public_user, upsert, utc_now
from .security import require_roles

prescriptions_bp = Blueprint("prescriptions", __name__)


def _normalize_meds(items):
    cleaned = []
    for item in items or []:
        name = (item.get("name") if isinstance(item, dict) else str(item)).strip()
        if not name:
            continue
        cleaned.append({
            "name": name,
            "dose": item.get("dose") if isinstance(item, dict) else "",
            "days": item.get("days") if isinstance(item, dict) else None,
            "notes": item.get("notes") if isinstance(item, dict) else "",
        })
    return cleaned


@prescriptions_bp.post("/api/prescriptions")
def write_prescription():
    session, error = require_roles("doctor", "admin")
    if error:
        return jsonify(error[0]), error[1]
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("user_id")
    medicines = _normalize_meds(payload.get("medicines") or payload.get("items"))
    if not user_id or not medicines:
        return jsonify({"error": "user_id and medicines are required"}), 400
    patient = find_by_id("users", user_id)
    if not patient:
        return jsonify({"error": "Patient not found"}), 404

    pdf_path = payload.get("pdf_path")
    prescription = {
        "id": new_id("rx"),
        "user_id": user_id,
        "doctor_id": payload.get("doctor_id") or session["account_id"],
        "appointment_id": payload.get("appointment_id"),
        "medicines": medicines,
        "advice": (payload.get("advice") or "").strip(),
        "pdf_path": pdf_path,
        "status": "issued",
        "created_at": utc_now(),
    }
    upsert("prescriptions", prescription)

    records = patient.get("medical_records") or {"history_pdfs": [], "consultation_pdfs": [], "notes": []}
    records.setdefault("consultation_pdfs", []).append({
        "id": new_id("rec"),
        "title": payload.get("title") or "Consultation prescription",
        "pdf_path": pdf_path,
        "prescription_id": prescription["id"],
        "appointment_id": payload.get("appointment_id"),
        "uploaded_at": utc_now(),
    })
    patient["medical_records"] = records
    upsert("users", patient)
    return jsonify({"prescription": prescription, "patient": public_user(patient)}), 201


@prescriptions_bp.get("/api/prescriptions")
def list_prescriptions():
    session, error = require_roles("user", "doctor", "admin")
    if error:
        return jsonify(error[0]), error[1]
    rows = load("prescriptions")
    if session["role"] == "user":
        rows = [row for row in rows if row.get("user_id") == session["account_id"]]
    elif session["role"] == "doctor":
        rows = [row for row in rows if row.get("doctor_id") == session["account_id"]]
    return jsonify({"prescriptions": rows})


@prescriptions_bp.get("/api/prescriptions/<rx_id>/eligible-medicines")
def eligible_medicines(rx_id):
    session, error = require_roles("user", "admin")
    if error:
        return jsonify(error[0]), error[1]
    rx = find_by_id("prescriptions", rx_id)
    if not rx:
        return jsonify({"error": "Prescription not found"}), 404
    if session["role"] == "user" and rx.get("user_id") != session["account_id"]:
        return jsonify({"error": "Not your prescription"}), 403

    needed = [item["name"].lower() for item in rx.get("medicines") or []]
    matches = []
    for pharmacy in load("pharmacies"):
        if pharmacy.get("verification_status") != "approved" or pharmacy.get("status") != "active":
            continue
        stock = [str(item).lower() for item in (pharmacy.get("inventory") or [])]
        available = [name for name in needed if any(name in entry or entry in name for entry in stock)]
        missing = [name for name in needed if name not in available]
        if available:
            matches.append({
                "pharmacy_id": pharmacy["id"],
                "name": pharmacy.get("name"),
                "kind": pharmacy.get("kind"),
                "location": pharmacy.get("location"),
                "available": available,
                "missing": missing,
                "fill_ratio": round(len(available) / max(len(needed), 1), 2),
            })
    matches.sort(key=lambda row: row["fill_ratio"], reverse=True)
    return jsonify({
        "prescription_id": rx_id,
        "medicines": rx.get("medicines"),
        "eligible_outlets": matches,
    })
