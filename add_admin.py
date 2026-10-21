"""Add an admin/moderator.  Run from the project folder:  python add_admin.py"""
import getpass
from backend.json_store import load, save, new_id, utc_now
from backend.security import hash_password
from backend.care_ops import norm_id

name = input("Name: ").strip()
email = input("Email: ").strip().lower()
password = getpass.getpass("Password (8+ chars): ")
code = getpass.getpass("Admin ID code for this person: ")
admins = load("admins")
if any(a["email"] == email for a in admins):
    raise SystemExit("An admin with that email already exists.")
if len(password) < 8 or not norm_id(code):
    raise SystemExit("Password must be 8+ characters and the Admin ID code can't be empty.")
ps, ph = hash_password(password)
cs, ch = hash_password(norm_id(code))
admins.append({"id": new_id("adm"), "email": email, "name": name, "role": "admin", "status": "active",
               "password_salt": ps, "password_hash": ph, "admin_code_salt": cs, "admin_code_hash": ch,
               "created_at": utc_now()})
save("admins", admins)
print("Added", email)
