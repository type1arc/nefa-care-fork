"""Compatibility launcher. The application server lives in backend/app.py."""

from backend.app import app, create_app


if __name__ == "__main__":
    from backend.config import PORT
    app.run(host="0.0.0.0", port=PORT, debug=False)
