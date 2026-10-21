"""Role identifiers, two-sided doctor presence, hospital queues, record-access requests and support tickets."""

import re
import secrets
from datetime import date

from flask import Blueprint, jsonify, request

from .config import ADMIN_CODE
from .json_store import find_by_id, load, new_id, public_user, save, upsert, utc_now
from .security import hash_password, require_roles

care_ops_bp = Blueprint("care_ops", __name__)

QUEUE_STATES = ("waiting", "in_consultation", "done", "no_show", "removed")
TICKET_STATES = ("open", "in_progress", "resolved")


def norm_id(value):
    """Identifiers are compared without spaces/case so 'asm-med 4412' == 'ASM-MED-4412'."""
    return re.sub(r"[\s]+", "", str(value or "")).upper()


def today():
    return date.today().isoformat()


def strip_secrets(row):
    return {k: v for k, v in (row or {}).items() if not k.startswith(("password_", "admin_code"))}


# ---------- presence (doctor AND hospital must both mark) ----------

def _presence_row(doctor_id, day=None):
    day = day or today()
    return next((r for r in load("presence") if r["doctor_id"] == doctor_id and r["date"] == day), None)


def presence_for(doctor):
    """Presence is confirmed only when doctor and affiliated hospital both marked today."""
    row = _presence_row(doctor["id"])
    hospital_id = doctor.get("hospital_id")
    doctor_marked = bool(row and row.get("doctor_marked_at") and row.get("hospital_id") == hospital_id)
    hospital_marked = bool(row and row.get("hospital_marked_at") and row.get("hospital_id") == hospital_id)
    return {
        "doctor_marked": doctor_marked,
        "hospital_marked": hospital_marked,
        "confirmed": bool(hospital_id and doctor_marked and hospital_marked),
        "hospital_id": hospital_id,
    }


def _set_mark(doctor, field, present):
    row = _presence_row(doctor["id"]) or {"id": new_id("prs"), "doctor_id": doctor["id"], "date": today()}
    if row.get("hospital_id") != doctor.get("hospital_id"):
        row.pop("doctor_marked_at", None)
        row.pop("hospital_marked_at", None)
    row["hospital_id"] = doctor.get("hospital_id")
    if present:
        row[field] = utc_now()
    else:
        row.pop(field, None)
    upsert("presence", row)


def _hospital_name(hospital_id):
    h = find_by_id("hospitals", hospital_id) if hospital_id else None
    return h.get("name") if h else None


def live_summary(doctor):
    """(label, patients_ahead) shown on the public doctor directory."""
    p = presence_for(doctor)
    if not p["confirmed"]:
        return "Not confirmed present today", None
    return f"Available at {_hospital_name(doctor['hospital_id'])}", len(_active_queue(doctor["id"]))


# ---------- queue ----------

def _active_queue(doctor_id, hospital_id=None):
    rows = [q for q in load("queue") if q["doctor_id"] == doctor_id and q["date"] == today()
            and q["status"] in ("waiting", "in_consultation")]
    if hospital_id:
        rows = [q for q in rows if q["hospital_id"] == hospital_id]
    return sorted(rows, key=lambda q: q["token_no"])


def _queue_view(entry, ahead=None):
    out = dict(entry)
    if ahead is not None:
        out["patients_ahead"] = ahead
    return out


def _my_doctors(hospital_id):
    return [d for d in load("doctors") if d.get("hospital_id") == hospital_id
            and d.get("verification_status") == "approved" and d.get("status") == "active"]


def _next_token(doctor_id):
    nums = [q["token_no"] for q in load("queue") if q["doctor_id"] == doctor_id and q["date"] == today()]
    return (max(nums) if nums else 0) + 1


def _add_to_queue(hospital_id, doctor_id, name, source, phone="", patient_id=None, appointment_id=None, note=""):
    entry = {
        "id": new_id("que"), "hospital_id": hospital_id, "doctor_id": doctor_id, "date": today(),
        "token_no": _next_token(doctor_id), "patient_id": patient_id, "patient_name": name, "phone": phone,
        "appointment_id": appointment_id, "source": source, "note": note,
        "status": "waiting", "created_at": utc_now(), "updated_at": utc_now(),
    }
    upsert("queue", entry)
    return entry


@care_ops_bp.get("/api/hospital/roster")
def hospital_roster():
    session, error = require_roles("hospital")
    if error:
        return jsonify(error[0]), error[1]
    rows = []
    for d in _my_doctors(session["account_id"]):
        rows.append({"id": d["id"], "full_name": d["full_name"], "specialty": d.get("specialty"),
                     "smc_number": d.get("smc_number") or d.get("registration_no"),
                     "presence": presence_for(d), "waiting": len(_active_queue(d["id"]))})
    return jsonify({"doctors": rows})


@care_ops_bp.post("/api/hospital/doctors/<doctor_id>/presence")
def hospital_mark_presence(doctor_id):
    session, error = require_roles("hospital")
    if error:
        return jsonify(error[0]), error[1]
    doctor = find_by_id("doctors", doctor_id)
    if not doctor or doctor.get("hospital_id") != session["account_id"]:
        return jsonify({"error": "This doctor is not affiliated with your hospital"}), 403
    _set_mark(doctor, "hospital_marked_at", bool((request.get_json(silent=True) or {}).get("present", True)))
    return jsonify(presence_for(doctor))


@care_ops_bp.get("/api/hospital/queue")
def hospital_queue():
    session, error = require_roles("hospital")
    if error:
        return jsonify(error[0]), error[1]
    hid = session["account_id"]
    docs = {d["id"]: d for d in _my_doctors(hid)}
    apts = {a["id"]: a for a in load("appointments")}
    users = {u["id"]: u for u in load("users")}
    queued_apts = {q.get("appointment_id") for q in load("queue") if q["date"] == today() and q["status"] != "removed"}
    entries = []
    for q in load("queue"):
        if q["hospital_id"] != hid or q["date"] != today() or q["status"] == "removed":
            continue
        a = apts.get(q.get("appointment_id") or "")
        if a and a.get("status") == "cancelled":
            continue
        entries.append(_queue_view(q) | {"doctor_name": (docs.get(q["doctor_id"]) or {}).get("full_name", "")})
    entries.sort(key=lambda q: (q["doctor_id"], q["token_no"]))
    pending = []
    for a in apts.values():
        if a.get("doctor_id") in docs and a.get("status") == "booked" and a["id"] not in queued_apts:
            pending.append({"id": a["id"], "doctor_id": a["doctor_id"], "doctor_name": docs[a["doctor_id"]]["full_name"],
                            "patient_name": (users.get(a.get("user_id")) or {}).get("full_name", "Patient"),
                            "scheduled_for": a.get("scheduled_for"), "mode": a.get("mode"), "reason": a.get("reason", "")})
    return jsonify({"queue": entries, "online_appointments": pending})


@care_ops_bp.post("/api/hospital/queue")
def hospital_add_walkin():
    session, error = require_roles("hospital")
    if error:
        return jsonify(error[0]), error[1]
    p = request.get_json(silent=True) or {}
    doctor = find_by_id("doctors", p.get("doctor_id") or "")
    name = (p.get("patient_name") or "").strip()
    if not doctor or doctor.get("hospital_id") != session["account_id"]:
        return jsonify({"error": "Choose a doctor affiliated with your hospital"}), 400
    if not name:
        return jsonify({"error": "Patient name is required"}), 400
    entry = _add_to_queue(session["account_id"], doctor["id"], name, "walk_in",
                          phone=(p.get("phone") or "").strip(), note=(p.get("note") or "").strip())
    return jsonify(entry), 201


@care_ops_bp.post("/api/hospital/queue/from-appointment")
def hospital_queue_appointment():
    session, error = require_roles("hospital")
    if error:
        return jsonify(error[0]), error[1]
    apt = find_by_id("appointments", (request.get_json(silent=True) or {}).get("appointment_id") or "")
    doctor = find_by_id("doctors", apt["doctor_id"]) if apt else None
    if not apt or not doctor or doctor.get("hospital_id") != session["account_id"]:
        return jsonify({"error": "Appointment not found for a doctor at your hospital"}), 404
    if apt.get("status") != "booked":
        return jsonify({"error": f"Appointment is {apt.get('status')}; only booked ones can be queued"}), 409
    patient = find_by_id("users", apt.get("user_id") or "") or {}
    entry = _add_to_queue(session["account_id"], doctor["id"], patient.get("full_name", "Patient"), "online",
                          phone=patient.get("phone", ""), patient_id=patient.get("id"), appointment_id=apt["id"],
                          note=apt.get("reason", ""))
    apt["status"] = "in_queue"
    upsert("appointments", apt)
    return jsonify(entry), 201


def _set_queue_status(entry_id, allowed):
    entry = find_by_id("queue", entry_id)
    status = (request.get_json(silent=True) or {}).get("status")
    if not entry or not allowed(entry):
        return jsonify({"error": "Queue entry not found"}), 404
    if status not in QUEUE_STATES:
        return jsonify({"error": f"Status must be one of {', '.join(QUEUE_STATES)}"}), 400
    entry["status"], entry["updated_at"] = status, utc_now()
    upsert("queue", entry)
    return jsonify(entry)


@care_ops_bp.post("/api/hospital/queue/<entry_id>/status")
def hospital_queue_status(entry_id):
    session, error = require_roles("hospital")
    if error:
        return jsonify(error[0]), error[1]
    return _set_queue_status(entry_id, lambda e: e["hospital_id"] == session["account_id"])


# ---------- doctor self-service ----------

@care_ops_bp.get("/api/doctors/me")
def doctor_me():
    session, error = require_roles("doctor")
    if error:
        return jsonify(error[0]), error[1]
    d = find_by_id("doctors", session["account_id"])
    out = strip_secrets(d)
    out["presence"] = presence_for(d)
    out["hospital_name"] = _hospital_name(d.get("hospital_id"))
    return jsonify(out)


@care_ops_bp.put("/api/doctors/me/hospital")
def doctor_set_hospital():
    session, error = require_roles("doctor")
    if error:
        return jsonify(error[0]), error[1]
    d = find_by_id("doctors", session["account_id"])
    hid = (request.get_json(silent=True) or {}).get("hospital_id") or None
    if hid:
        h = find_by_id("hospitals", hid)
        if not h or h.get("verification_status") != "approved" or h.get("status") != "active":
            return jsonify({"error": "Choose a verified hospital"}), 400
    if hid != d.get("hospital_id"):
        _set_mark(d, "doctor_marked_at", False)  # new affiliation: yesterday's/other-site marks don't carry over
        d["hospital_id"] = hid
        upsert("doctors", d)
    return doctor_me()


@care_ops_bp.post("/api/doctors/me/presence")
def doctor_mark_presence():
    session, error = require_roles("doctor")
    if error:
        return jsonify(error[0]), error[1]
    d = find_by_id("doctors", session["account_id"])
    if not d.get("hospital_id"):
        return jsonify({"error": "Link yourself to a hospital before marking presence"}), 400
    _set_mark(d, "doctor_marked_at", bool((request.get_json(silent=True) or {}).get("present", True)))
    return jsonify(presence_for(d))


@care_ops_bp.get("/api/doctors/me/queue")
def doctor_queue():
    session, error = require_roles("doctor")
    if error:
        return jsonify(error[0]), error[1]
    rows = [q for q in load("queue") if q["doctor_id"] == session["account_id"] and q["date"] == today()
            and q["status"] != "removed"]
    return jsonify({"queue": sorted(rows, key=lambda q: q["token_no"])})


@care_ops_bp.post("/api/doctors/me/queue/<entry_id>/status")
def doctor_queue_status(entry_id):
    session, error = require_roles("doctor")
    if error:
        return jsonify(error[0]), error[1]
    return _set_queue_status(entry_id, lambda e: e["doctor_id"] == session["account_id"])


def ensure_patient_code(patient):
    if not patient.get("patient_code"):
        patient["patient_code"] = f"PT-{secrets.token_hex(4).upper()}"
        upsert("users", patient)
    return patient["patient_code"]


@care_ops_bp.get("/api/doctors/me/patients")
def doctor_patients():
    session, error = require_roles("doctor")
    if error:
        return jsonify(error[0]), error[1]
    out = []
    for u in load("users"):
        for g in u.get("doctor_access") or []:
            if g.get("doctor_id") == session["account_id"]:
                out.append({"patient_id": u["id"], "full_name": u.get("full_name"), "status": g.get("status"),
                            "updated_at": g.get("updated_at")})
    return jsonify({"patients": out})


@care_ops_bp.post("/api/doctors/me/access-requests")
def doctor_request_access():
    session, error = require_roles("doctor")
    if error:
        return jsonify(error[0]), error[1]
    code = norm_id((request.get_json(silent=True) or {}).get("patient_code"))
    patient = next((u for u in load("users") if norm_id(u.get("patient_code")) == code and code), None)
    if not patient:
        return jsonify({"error": "No patient found with that Patient ID"}), 404
    grants = patient.setdefault("doctor_access", [])
    grant = next((g for g in grants if g.get("doctor_id") == session["account_id"]), None)
    if grant and grant.get("status") == "approved":
        return jsonify({"status": "approved"})
    if grant is None:
        grant = {"doctor_id": session["account_id"]}
        grants.append(grant)
    grant.update({"status": "requested", "updated_at": utc_now()})
    upsert("users", patient)
    return jsonify({"status": "requested"}), 201


# ---------- patient overview ----------

@care_ops_bp.get("/api/patient/overview")
def patient_overview():
    session, error = require_roles("user")
    if error:
        return jsonify(error[0]), error[1]
    patient = find_by_id("users", session["account_id"])
    ensure_patient_code(patient)
    doctors = {d["id"]: d for d in load("doctors")}
    access = [{"doctor_id": g["doctor_id"], "status": g.get("status"), "updated_at": g.get("updated_at"),
               "doctor_name": (doctors.get(g["doctor_id"]) or {}).get("full_name", "Doctor"),
               "specialty": (doctors.get(g["doctor_id"]) or {}).get("specialty", "")}
              for g in patient.get("doctor_access") or []]
    mine = []
    for q in load("queue"):
        if q.get("patient_id") == patient["id"] and q["date"] == today() and q["status"] in ("waiting", "in_consultation"):
            ahead = [x for x in _active_queue(q["doctor_id"], q["hospital_id"]) if x["token_no"] < q["token_no"]]
            mine.append(q | {"patients_ahead": len(ahead), "doctor_name": (doctors.get(q["doctor_id"]) or {}).get("full_name", ""),
                             "hospital_name": _hospital_name(q["hospital_id"])})
    return jsonify({"user": public_user(patient), "access": access, "queue": mine})


# ---------- support tickets ----------

@care_ops_bp.post("/api/tickets")
def create_ticket():
    session, error = require_roles("user", "doctor", "hospital")
    if error:
        return jsonify(error[0]), error[1]
    p = request.get_json(silent=True) or {}
    subject, text = (p.get("subject") or "").strip(), (p.get("description") or "").strip()
    if not subject or not text:
        return jsonify({"error": "Subject and description are required"}), 400
    t = {"id": new_id("tkt"), "raised_by": session["account_id"], "role": session["role"],
         "category": (p.get("category") or "other").strip(), "subject": subject, "description": text,
         "status": "open", "replies": [], "created_at": utc_now(), "updated_at": utc_now()}
    upsert("tickets", t)
    return jsonify(t), 201


@care_ops_bp.get("/api/tickets")
def list_tickets():
    session, error = require_roles("user", "doctor", "hospital", "admin")
    if error:
        return jsonify(error[0]), error[1]
    rows = load("tickets")
    if session["role"] != "admin":
        rows = [t for t in rows if t["raised_by"] == session["account_id"]]
    elif request.args.get("status"):
        rows = [t for t in rows if t["status"] == request.args["status"]]
    return jsonify({"tickets": sorted(rows, key=lambda t: t["created_at"], reverse=True)})


@care_ops_bp.post("/api/tickets/<ticket_id>/reply")
def reply_ticket(ticket_id):
    session, error = require_roles("user", "doctor", "hospital", "admin")
    if error:
        return jsonify(error[0]), error[1]
    t = find_by_id("tickets", ticket_id)
    if not t or (session["role"] != "admin" and t["raised_by"] != session["account_id"]):
        return jsonify({"error": "Ticket not found"}), 404
    msg = ((request.get_json(silent=True) or {}).get("message") or "").strip()
    if not msg:
        return jsonify({"error": "Write a message first"}), 400
    t["replies"].append({"by": "admin" if session["role"] == "admin" else "you", "message": msg, "at": utc_now()})
    t["updated_at"] = utc_now()
    upsert("tickets", t)
    return jsonify(t)


@care_ops_bp.post("/api/tickets/<ticket_id>/status")
def ticket_status(ticket_id):
    session, error = require_roles("admin")
    if error:
        return jsonify(error[0]), error[1]
    t = find_by_id("tickets", ticket_id)
    status = (request.get_json(silent=True) or {}).get("status")
    if not t:
        return jsonify({"error": "Ticket not found"}), 404
    if status not in TICKET_STATES:
        return jsonify({"error": f"Status must be one of {', '.join(TICKET_STATES)}"}), 400
    t["status"], t["updated_at"] = status, utc_now()
    upsert("tickets", t)
    return jsonify(t)


def migrate_identities():
    """Give pre-existing admins an admin ID code (from DHRUVA_CARE_ADMIN_CODE) so the new login works."""
    admins, changed = load("admins"), False
    for a in admins:
        if not a.get("admin_code_hash"):
            a["admin_code_salt"], a["admin_code_hash"] = hash_password(norm_id(ADMIN_CODE))
            changed = True
    if changed:
        save("admins", admins)
