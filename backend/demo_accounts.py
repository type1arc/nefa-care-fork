"""Opt-in helper for local demos:  python -m backend.demo_accounts

Gives the seeded doctors/hospitals identifiers + a password, links each doctor to the hospital in
their state, and creates one demo patient. Nothing here runs automatically; delete the accounts
(or never run this) before any real deployment.
"""
from .care_ops import ensure_patient_code
from .json_store import ensure_layout, load, new_id, save, upsert, utc_now
from .security import hash_password

PASSWORD = "Demo@12345"


def main():
    ensure_layout()
    hospitals, doctors = load("hospitals"), load("doctors")
    print("\n== Hospitals  (license no + HFR ID + password) ==")
    for i, h in enumerate(hospitals, 1):
        h["hfr_id"] = h.get("hfr_id") or f"HFR-DEMO-{i:04d}"
        h["password_salt"], h["password_hash"] = hash_password(PASSWORD)
        print(f"  {h['name']:<40} {h['license_no']:<14} {h['hfr_id']}")
    save("hospitals", hospitals)
    by_state = {h["location"]["state"]: h["id"] for h in hospitals}
    print("\n== Doctors  (SMC no + NMR ID + password) ==")
    for i, d in enumerate(doctors, 1):
        d["smc_number"] = d.get("smc_number") or d["registration_no"]
        d["nmr_id"] = d.get("nmr_id") or f"NMR-DEMO-{i:05d}"
        d["password_salt"], d["password_hash"] = hash_password(PASSWORD)
        d["hospital_id"] = d.get("hospital_id") or by_state.get(d["practice_location"]["state"])
        print(f"  {d['full_name']:<24} {d['smc_number']:<14} {d['nmr_id']:<16} hospital={d['hospital_id']}")
    save("doctors", doctors)
    email = "demo.patient@dhruvacare.in"
    if not any(u.get("email") == email for u in load("users")):
        salt, digest = hash_password(PASSWORD)
        upsert("users", {"id": new_id("usr"), "role": "user", "status": "active", "full_name": "Demo Patient",
                         "email": email, "phone": "9100000099", "password_salt": salt, "password_hash": digest,
                         "location": {"region": "North East India", "state": "Assam", "district": "Guwahati",
                                      "locality": "", "pincode": "", "address": ""},
                         "medical_records": {"history_pdfs": [], "consultation_pdfs": [], "notes": []},
                         "medical_profile": {}, "doctor_access": [], "created_at": utc_now()})
    for u in load("users"):
        if u["email"] == email:
            print(f"\n== Patient ==\n  {email}   Patient ID {ensure_patient_code(u)}")
    print(f"\nAll demo passwords: {PASSWORD}\n")


if __name__ == "__main__":
    main()
