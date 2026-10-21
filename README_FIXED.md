# Dhruva Care — Fixed Local Build

## Quick start (Windows)
1. Extract this ZIP completely.
2. Double-click `RUN_DHRUVA_CARE.bat`.
3. Wait for Flask to start.
4. Open **http://127.0.0.1:5050/**.
5. Keep the black terminal window open while using the site.

## Quick start (Linux/macOS)
Run:

```bash
./run_dhruva_care.sh
```

Then open **http://127.0.0.1:5050/**.

## Important fixes in this build
- Uses the small `Disease_symptom_predictor.joblib` model by default instead of the ~1.8 GB model.
- ML model loading is on-demand; opening the homepage does not load the model.
- Flask debug/reloader is disabled for the launcher.
- Doctor location fields are aligned between backend (`location`) and frontend.
- scikit-learn is pinned to the model's training version (1.7.2).

## Do not open the HTML file directly
Do **not** double-click `frontend/dhruva-care.html`. The page needs the Flask server for `/api/...` and `/assets/...` routes.

## If Windows says Python is missing
Install Python 3.10–3.13 and make sure the Python launcher (`py`) is available, then run the BAT file again.

## Web integration notes (October 2026)

The delivered build includes a refreshed responsive patient-facing web shell while preserving the existing Flask API contracts.

### Integration improvements
- Added `GET /api/pharmacies` as a public, verified-pharmacy directory endpoint.
- Pharmacy cards now load from `data/pharmacies.json` through the backend instead of a duplicated hardcoded frontend catalogue.
- Doctor queue cards no longer invent random queue sizes when backend data is unavailable.
- Added responsive mobile navigation and accessibility skip navigation.
- Added a patient-facing footer with emergency-care guidance and product disclaimers.
- Updated teleconsultation copy to avoid implying a security/compliance certification that the local prototype does not independently establish.
- Updated symptom/privacy wording to describe account/session protection without claiming that all processing is client-side.

### Local production-style setup
Set a strong secret before deploying outside a local demo:

```bash
export DHRUVA_CARE_SECRET="replace-with-a-long-random-secret"
export DHRUVA_CARE_ADMIN_EMAIL="admin@example.com"
export DHRUVA_CARE_ADMIN_PASSWORD="replace-with-a-strong-password"
```

On Windows PowerShell:

```powershell
$env:DHRUVA_CARE_SECRET="replace-with-a-long-random-secret"
$env:DHRUVA_CARE_ADMIN_EMAIL="admin@example.com"
$env:DHRUVA_CARE_ADMIN_PASSWORD="replace-with-a-strong-password"
```

The supplied launcher remains the simplest local start path. The application expects Python 3.10–3.13 and installs the pinned dependencies from `requirements.txt`.
