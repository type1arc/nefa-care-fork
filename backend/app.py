"""Dhruva Care API — JSON-backed care guidance and coordination."""

from flask import Flask, Response, jsonify, send_from_directory

from admin.account_management import account_management_bp
from admin.account_moderation import account_moderation_bp
from admin.admin_dashboard import admin_dashboard_bp
from admin.admin_login import admin_login_bp, bootstrap_admin
from users.appointments import appointments_bp
from users.calorie_counter import calorie_counter_bp
from users.patient_records import patient_records_bp
from backend.config import BASE_DIR, PORT, SECRET_KEY, SERVICE_REGION
from backend.care_ops import care_ops_bp, migrate_identities
from backend.consultations import consultations_bp
from doctors.doctor_availability import doctor_availability_bp
from doctors.doctor_directory import doctor_directory_bp
from doctors.doctor_profile import doctor_profile_bp
from doctors.doctor_verification import doctor_verification_bp
from backend.hospital_verification import hospital_verification_bp
from backend.json_store import ensure_layout
from backend.security import drop_session
from backend.pharmacy_orders import pharmacy_orders_bp
from backend.pharmacy_directory import pharmacy_directory_bp
from backend.pharmacy_verification import pharmacy_verification_bp
from backend.prescriptions import prescriptions_bp
from backend.symptom_checker import symptom_checker_bp
from backend.seed_northeast import seed_if_empty
from users.user_auth import user_auth_bp

BLUEPRINTS = (
    admin_login_bp,
    admin_dashboard_bp,
    doctor_verification_bp,
    pharmacy_verification_bp,
    hospital_verification_bp,
    account_management_bp,
    account_moderation_bp,
    user_auth_bp,
    doctor_directory_bp,
    doctor_availability_bp,
    doctor_profile_bp,
    appointments_bp,
    consultations_bp,
    prescriptions_bp,
    pharmacy_directory_bp,
    pharmacy_orders_bp,
    calorie_counter_bp,
    patient_records_bp,
    symptom_checker_bp,
    care_ops_bp,
)
from backend.json_store import load


def create_app():
    ensure_layout()
    bootstrap_admin()
    seed_if_empty()
    migrate_identities()

    app = Flask(__name__)
    app.config["SECRET_KEY"] = SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint)

    @app.get("/")
    def frontend():
        with open(f"{BASE_DIR}/frontend/dhruva-care.html", "r", encoding="utf-8") as page:
            return Response(page.read(), mimetype="text/html")

    @app.get("/assets/<path:filename>")
    def frontend_assets(filename):
        return send_from_directory(f"{BASE_DIR}/frontend", filename)

    @app.get("/api/health")
    def health():
        return jsonify({"ok": True, "region": SERVICE_REGION, "service": "dhruva-care"})

    @app.post("/api/auth/logout")
    def logout_any_role():
        drop_session()
        response = jsonify({"ok": True})
        response.delete_cookie("dhruva_care_session")
        return response

    @app.get("/api/hospitals")
    def list_hospitals():
        rows = [
            {k: v for k, v in h.items() if not k.startswith("password_")}
            for h in load("hospitals")
            if h.get("verification_status") == "approved" or h.get("status") == "active"
        ]
        return jsonify({"region": SERVICE_REGION, "hospitals": rows, "count": len(rows)})

    @app.get("/api/crowdfunding")
    def list_crowdfunding():
        rows = load("crowdfunding")
        return jsonify({"foundation": "Dhruva Care / MediApp Community Health Fund", "campaigns": rows, "count": len(rows)})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=True)
