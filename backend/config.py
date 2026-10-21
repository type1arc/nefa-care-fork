import os

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
# Keep runtime data beside the project, rather than inside the source package.
BASE_DIR = os.path.dirname(BACKEND_DIR)
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
RECORDS_DIR = os.path.join(UPLOAD_DIR, "medical_records")
LICENSE_DIR = os.path.join(UPLOAD_DIR, "licenses")
PHOTO_DIR = os.path.join(UPLOAD_DIR, "photos")

PORT = int(os.environ.get("PORT", 5050))
SECRET_KEY = os.environ.get("DHRUVA_CARE_SECRET", os.environ.get("MEDIAPP_SECRET", "dhruva-care-dev-key"))

ADMIN_EMAIL = os.environ.get("DHRUVA_CARE_ADMIN_EMAIL", os.environ.get("MEDIAPP_ADMIN_EMAIL", "admin@dhruvacare.in"))
ADMIN_PASSWORD = os.environ.get("DHRUVA_CARE_ADMIN_PASSWORD", os.environ.get("MEDIAPP_ADMIN_PASSWORD", "AdminDC#2026"))
ADMIN_CODE = os.environ.get("DHRUVA_CARE_ADMIN_CODE", "DC-ADMIN-2026")

SESSION_TTL_SECONDS = 60 * 60 * 12
PBKDF2_ITERATIONS = 120_000

SERVICE_REGION = "North East India"
APP_NAME = "Dhruva Care"
MODEL_PATH = os.environ.get(
    "DHRUVA_CARE_MODEL_PATH",
    os.path.join(BASE_DIR, "Disease_symptom_predictor.joblib"),
)
ALLOWED_STATES = (
    "Arunachal Pradesh",
    "Assam",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Sikkim",
    "Tripura",
)

JSON_FILES = {
    "admins": "admins.json",
    "users": "users.json",
    "doctors": "doctors.json",
    "pharmacies": "pharmacies.json",
    "hospitals": "hospitals.json",
    "sessions": "sessions.json",
    "appointments": "appointments.json",
    "prescriptions": "prescriptions.json",
    "orders": "orders.json",
    "calorie_logs": "calorie_logs.json",
    "consultations": "consultations.json",
    "messages": "messages.json",
    "call_routes": "call_routes.json",
    "safety_audit": "safety_audit.json",
    "crowdfunding": "crowdfunding.json",
    "presence": "presence.json",
    "queue": "queue.json",
    "tickets": "tickets.json",
}
