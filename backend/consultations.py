"""Privacy-first chat and call routing.

Clients encrypt message and WebRTC signalling payloads before sending them here.
This service stores/routs ciphertext only; it never has chat private keys.
"""
from flask import Blueprint, jsonify, request

from .json_store import find_by_id, load, new_id, upsert, utc_now
from .security import require_roles

consultations_bp = Blueprint("consultations", __name__)


def _consultation_for_member(consultation_id, session):
    row = find_by_id("consultations", consultation_id)
    if not row or session["account_id"] not in (row.get("user_id"), row.get("doctor_id")):
        return None
    return row


@consultations_bp.get("/api/consultations/status")
def status():
    return jsonify({"available": True, "chat": True, "video": True,
                    "encryption": "client-managed end-to-end encryption"})


@consultations_bp.post("/api/consultations")
def open_consultation():
    session, error = require_roles("user", "doctor")
    if error:
        return jsonify(error[0]), error[1]
    payload = request.get_json(silent=True) or {}
    appointment = find_by_id("appointments", payload.get("appointment_id") or "")
    if not appointment or session["account_id"] not in (appointment.get("user_id"), appointment.get("doctor_id")):
        return jsonify({"error": "An appointment participant must open the consultation"}), 403
    existing = next((row for row in load("consultations") if row.get("appointment_id") == appointment["id"]), None)
    if existing:
        return jsonify(existing)
    row = {"id": new_id("con"), "appointment_id": appointment["id"], "user_id": appointment["user_id"],
           "doctor_id": appointment["doctor_id"], "status": "open", "encryption": "e2ee-client-managed",
           "created_at": utc_now()}
    upsert("consultations", row)
    return jsonify(row), 201


@consultations_bp.post("/api/consultations/<consultation_id>/messages")
def send_message(consultation_id):
    session, error = require_roles("user", "doctor")
    if error:
        return jsonify(error[0]), error[1]
    consultation = _consultation_for_member(consultation_id, session)
    if not consultation:
        return jsonify({"error": "Consultation is unavailable"}), 404
    payload = request.get_json(silent=True) or {}
    ciphertext = payload.get("ciphertext")
    algorithm = payload.get("algorithm")
    if not ciphertext or not algorithm:
        return jsonify({"error": "ciphertext and client encryption algorithm are required"}), 400
    message = {"id": new_id("msg"), "consultation_id": consultation_id, "sender_id": session["account_id"],
               "ciphertext": ciphertext, "algorithm": algorithm, "key_version": payload.get("key_version"),
               "safety_envelope": payload.get("safety_envelope"), "created_at": utc_now()}
    upsert("messages", message)
    return jsonify({"id": message["id"], "created_at": message["created_at"]}), 201


@consultations_bp.get("/api/consultations/<consultation_id>/messages")
def list_messages(consultation_id):
    session, error = require_roles("user", "doctor")
    if error:
        return jsonify(error[0]), error[1]
    if not _consultation_for_member(consultation_id, session):
        return jsonify({"error": "Consultation is unavailable"}), 404
    return jsonify({"messages": [row for row in load("messages") if row.get("consultation_id") == consultation_id]})


@consultations_bp.post("/api/consultations/<consultation_id>/call-route")
def create_call_route(consultation_id):
    session, error = require_roles("user", "doctor")
    if error:
        return jsonify(error[0]), error[1]
    if not _consultation_for_member(consultation_id, session):
        return jsonify({"error": "Consultation is unavailable"}), 404
    encrypted_signal = (request.get_json(silent=True) or {}).get("encrypted_signal")
    if not encrypted_signal:
        return jsonify({"error": "Encrypted WebRTC signalling is required"}), 400
    route = {"id": new_id("call"), "consultation_id": consultation_id, "sender_id": session["account_id"],
             "encrypted_signal": encrypted_signal, "created_at": utc_now(), "expires_at": None}
    upsert("call_routes", route)
    return jsonify({"route_id": route["id"], "privacy": "signalling encrypted; media must use WebRTC E2EE"}), 201


@consultations_bp.post("/api/admin/consultations/<consultation_id>/safety-review")
def safety_review(consultation_id):
    """Break-glass metadata access. Normal E2EE ciphertext remains unavailable to admins."""
    session, error = require_roles("admin")
    if error:
        return jsonify(error[0]), error[1]
    reason = (request.get_json(silent=True) or {}).get("reason", "").strip()
    if len(reason) < 20:
        return jsonify({"error": "A specific safety reason of at least 20 characters is required"}), 400
    consultation = find_by_id("consultations", consultation_id)
    if not consultation:
        return jsonify({"error": "Consultation not found"}), 404
    audit = {"id": new_id("audit"), "consultation_id": consultation_id, "admin_id": session["account_id"],
             "reason": reason, "created_at": utc_now(), "action": "safety-envelope-request"}
    upsert("safety_audit", audit)
    envelopes = [{"message_id": row["id"], "safety_envelope": row.get("safety_envelope")}
                 for row in load("messages") if row.get("consultation_id") == consultation_id and row.get("safety_envelope")]
    return jsonify({"audit_id": audit["id"], "safety_envelopes": envelopes,
                    "notice": "Normal chat ciphertext is never disclosed; envelopes must be decrypted outside the service by authorized safety staff."})
