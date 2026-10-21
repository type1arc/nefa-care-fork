"""Service-area rules: this backend only accepts North East India locations."""

from .config import ALLOWED_STATES, SERVICE_REGION

STATE_DISTRICTS = {
    "Arunachal Pradesh": ["Itanagar", "Tawang", "Pasighat", "Ziro", "Naharlagun"],
    "Assam": ["Guwahati", "Dibrugarh", "Silchar", "Jorhat", "Tezpur", "Nagaon", "Tinsukia"],
    "Manipur": ["Imphal East", "Imphal West", "Churachandpur", "Thoubal", "Ukhrul"],
    "Meghalaya": ["East Khasi Hills", "West Garo Hills", "Ri Bhoi", "Shillong"],
    "Mizoram": ["Aizawl", "Lunglei", "Champhai", "Kolasib"],
    "Nagaland": ["Kohima", "Dimapur", "Mokokchung", "Tuensang"],
    "Sikkim": ["Gangtok", "Namchi", "Gyalshing", "Mangan"],
    "Tripura": ["West Tripura", "Agartala", "Unakoti", "Dhalai", "South Tripura"],
}


def normalize_state(value):
    if not value:
        return ""
    text = str(value).strip()
    for state in ALLOWED_STATES:
        if text.lower() == state.lower():
            return state
    return text


def is_northeast_state(state):
    return normalize_state(state) in ALLOWED_STATES


def validate_location(payload, required=True):
    state = normalize_state(payload.get("state"))
    district = (payload.get("district") or "").strip()
    locality = (payload.get("locality") or payload.get("city") or "").strip()
    pincode = str(payload.get("pincode") or "").strip()

    if required and not state:
        return None, "State is required"

    if state and not is_northeast_state(state):
        return None, f"Service is limited to {SERVICE_REGION}. '{state}' is outside the coverage area."

    return {
        "region": SERVICE_REGION,
        "state": state,
        "district": district,
        "locality": locality,
        "pincode": pincode,
        "address": (payload.get("address") or "").strip(),
    }, None
