import json
import os
import threading
import uuid
import secrets
from datetime import datetime, timezone

from .config import DATA_DIR, JSON_FILES, LICENSE_DIR, PHOTO_DIR, RECORDS_DIR, UPLOAD_DIR

_lock = threading.RLock()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _path(name):
    return os.path.join(DATA_DIR, JSON_FILES[name])


def ensure_layout():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(RECORDS_DIR, exist_ok=True)
    os.makedirs(LICENSE_DIR, exist_ok=True)
    os.makedirs(PHOTO_DIR, exist_ok=True)
    for key in JSON_FILES:
        path = _path(key)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as handle:
                json.dump([], handle, indent=2)
    # Lightweight migration for projects created before unique doctor codes.
    doctor_path = _path("doctors")
    with _lock:
        with open(doctor_path, "r", encoding="utf-8") as handle:
            doctors = json.load(handle)
        changed = False
        for doctor in doctors if isinstance(doctors, list) else []:
            if not doctor.get("doctor_code"):
                doctor["doctor_code"] = f"DOC-{secrets.token_hex(5).upper()}"
                changed = True
        if changed:
            with open(doctor_path, "w", encoding="utf-8") as handle:
                json.dump(doctors, handle, indent=2, ensure_ascii=False)


def load(name):
    ensure_layout()
    with _lock:
        with open(_path(name), "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, list) else []


def save(name, rows):
    ensure_layout()
    with _lock:
        tmp = _path(name) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(rows, handle, indent=2, ensure_ascii=False)
        os.replace(tmp, _path(name))


def find_by_id(name, item_id):
    for row in load(name):
        if row.get("id") == item_id:
            return row
    return None


def upsert(name, item, id_field="id"):
    rows = load(name)
    found = False
    for index, row in enumerate(rows):
        if row.get(id_field) == item.get(id_field):
            rows[index] = item
            found = True
            break
    if not found:
        rows.append(item)
    save(name, rows)
    return item


def delete_by_id(name, item_id):
    rows = load(name)
    kept = [row for row in rows if row.get("id") != item_id]
    save(name, kept)
    return len(kept) != len(rows)


def public_user(user):
    if not user:
        return None
    clone = dict(user)
    clone.pop("password_hash", None)
    clone.pop("password_salt", None)
    return clone
