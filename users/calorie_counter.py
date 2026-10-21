from flask import Blueprint, jsonify, request

from backend.json_store import load, new_id, save, utc_now
from backend.security import require_roles

calorie_counter_bp = Blueprint("calorie_counter", __name__)

# Everyday items plus a few North East staples for local logging.
FOOD_CATALOG = {
    "steamed rice": 130,
    "brown rice": 111,
    "roti": 80,
    "dal": 116,
    "chicken curry": 190,
    "fish curry": 140,
    "egg": 78,
    "milk tea": 60,
    "banana": 89,
    "apple": 52,
    "boiled potato": 87,
    "green salad": 25,
    "thukpa": 160,
    "momos (4 pcs)": 220,
    "axone with pork": 280,
    "bamboo shoot fry": 90,
    "eromba": 110,
    "jadoh": 250,
    "khar": 95,
    "pukhlein": 180,
    "smoked fish": 150,
    "black rice pudding": 170,
}


def _lookup_kcal(name, grams=100):
    key = name.strip().lower()
    per_100 = FOOD_CATALOG.get(key)
    if per_100 is None:
        return None
    return round(per_100 * (float(grams) / 100.0), 1)


@calorie_counter_bp.get("/api/calories/foods")
def foods():
    catalog = [{"name": name, "kcal_per_100g": kcal} for name, kcal in sorted(FOOD_CATALOG.items())]
    return jsonify({"foods": catalog, "region_note": "Includes common North East dishes alongside everyday items"})


@calorie_counter_bp.post("/api/calories/log")
def log_meal():
    session, error = require_roles("user", "admin")
    if error:
        return jsonify(error[0]), error[1]
    payload = request.get_json(silent=True) or {}
    items = payload.get("items") or []
    if not items:
        return jsonify({"error": "Provide items: [{name, grams}]"}), 400

    lines = []
    unknown = []
    total = 0.0
    for item in items:
        name = item.get("name") or ""
        grams = item.get("grams") or 100
        kcal = item.get("kcal")
        if kcal is None:
            kcal = _lookup_kcal(name, grams)
        if kcal is None:
            unknown.append(name)
            continue
        kcal = float(kcal)
        total += kcal
        lines.append({"name": name, "grams": grams, "kcal": kcal})

    if unknown and not lines:
        return jsonify({"error": "Unknown foods", "unknown": unknown}), 400

    entry = {
        "id": new_id("cal"),
        "user_id": session["account_id"] if session["role"] == "user" else payload.get("user_id") or session["account_id"],
        "eaten_on": payload.get("eaten_on") or utc_now()[:10],
        "meal": payload.get("meal") or "unspecified",
        "items": lines,
        "unknown": unknown,
        "total_kcal": round(total, 1),
        "created_at": utc_now(),
    }
    rows = load("calorie_logs")
    rows.append(entry)
    save("calorie_logs", rows)
    return jsonify(entry), 201


@calorie_counter_bp.get("/api/calories/summary")
def summary():
    session, error = require_roles("user", "admin")
    if error:
        return jsonify(error[0]), error[1]
    day = request.args.get("date")
    user_id = session["account_id"] if session["role"] == "user" else (request.args.get("user_id") or session["account_id"])
    rows = [row for row in load("calorie_logs") if row.get("user_id") == user_id]
    if day:
        rows = [row for row in rows if row.get("eaten_on") == day]
    total = round(sum(row.get("total_kcal") or 0 for row in rows), 1)
    return jsonify({"user_id": user_id, "date": day, "entries": rows, "total_kcal": total})
