"""Read-only adapter for the supplied symptom-neighbour model.

This is a guidance tool, not a diagnosis. The model is loaded once and cached,
with on-demand loading so the homepage can start without loading the ML model.
"""
from functools import lru_cache
import re
import threading

from flask import Blueprint, jsonify, request

from .config import MODEL_PATH
from .json_store import load
from doctors.doctor_directory import _is_listed, public_doctor

symptom_checker_bp = Blueprint("symptom_checker", __name__)

# Common patient terminology mapped to model symptom tokens
SYNONYM_MAP = {
    "fever": ["AcuteFeverSyndrome", "ChronicFeverDisease", "MildFeverCondition"],
    "headache": ["AcuteHeadacheSyndrome", "SevereHeadacheDisease", "ChronicHeadacheDisorder"],
    "cough": ["AcuteCoughSyndrome", "ChronicCoughDisease"],
    "breath": ["SevereDyspneaMalformation", "ChronicDyspneaDeficiency", "AcuteDyspneaSyndrome"],
    "shortness of breath": ["SevereDyspneaMalformation", "ChronicDyspneaDeficiency"],
    "breathless": ["SevereDyspneaMalformation", "ChronicDyspneaDeficiency"],
    "chest pain": ["CongenitalPalpitationsSyndrome", "AcuteHypertensionCondition"],
    "palpitation": ["CongenitalPalpitationsSyndrome", "SevereTachycardiaDysfunction"],
    "heart": ["CongenitalPalpitationsSyndrome", "AcuteHypertensionCondition", "SevereTachycardiaDysfunction"],
    "dizzy": ["ChronicDizzinessSyndrome", "HereditaryDizzinessMalformation"],
    "dizziness": ["ChronicDizzinessSyndrome", "HereditaryDizzinessMalformation"],
    "vomit": ["SevereVomitingDisorder", "HereditaryVomitingCondition"],
    "vomiting": ["SevereVomitingDisorder", "HereditaryVomitingCondition"],
    "nausea": ["CongenitalNauseaDeficiency", "AcuteNauseaSyndrome"],
    "fatigue": ["IdiopathicFatigueSyndrome", "AcuteFatigueSyndrome"],
    "tired": ["IdiopathicFatigueSyndrome", "AcuteFatigueSyndrome"],
    "rash": ["ProgressiveRashCondition", "AcuteRashSyndrome"],
    "skin": ["ProgressiveRashCondition", "SevereSkin ulcerDeficiency"],
    "joint pain": ["AcuteJoint painCondition", "ChronicJoint painDisorder"],
    "joint": ["AcuteJoint painCondition", "ChronicJoint painDisorder"],
    "insomnia": ["SevereInsomniaDysfunction", "MildInsomniaSyndrome"],
    "sleep": ["SevereInsomniaDysfunction", "MildInsomniaSyndrome"],
    "seizure": ["SecondarySeizureMalformation", "AcuteSeizureCondition"],
    "hearing loss": ["HereditaryHearing lossDisease"],
    "ear": ["HereditaryHearing lossDisease"],
}

POPULAR_SYMPTOMS = [
    {"id": "AcuteFeverSyndrome", "label": "Fever (Acute)"},
    {"id": "AcuteHeadacheSyndrome", "label": "Headache"},
    {"id": "AcuteCoughSyndrome", "label": "Persistent Cough"},
    {"id": "SevereDyspneaMalformation", "label": "Shortness of Breath"},
    {"id": "CongenitalPalpitationsSyndrome", "label": "Heart Palpitations"},
    {"id": "IdiopathicFatigueSyndrome", "label": "Fatigue & Weakness"},
    {"id": "ChronicDizzinessSyndrome", "label": "Dizziness"},
    {"id": "ProgressiveRashCondition", "label": "Skin Rash"},
    {"id": "AcuteJoint painCondition", "label": "Joint Pain"},
    {"id": "AcuteNauseaSyndrome", "label": "Nausea"},
]


def _readable(value):
    clean = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", str(value)).replace("_", " ").strip()
    return clean


def _key(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


@lru_cache(maxsize=1)
def _model_data():
    try:
        import joblib
    except ImportError as exc:
        raise RuntimeError("The symptom model dependencies are not installed") from exc
    try:
        bundle = joblib.load(MODEL_PATH, mmap_mode="r")
        model = bundle["model"]
        symptoms = list(bundle["symptom_columns"])
        diseases = bundle["disease_names"]
        return model, symptoms, diseases
    except FileNotFoundError as exc:
        raise RuntimeError(f"The symptom model file could not be found at {MODEL_PATH}") from exc
    except (KeyError, TypeError) as exc:
        raise RuntimeError("The symptom model has an unsupported format") from exc


def warm_model():
    """Background model loader to ensure warm cache without blocking server boot."""
    def _loader():
        try:
            _model_data()
        except Exception as err:
            print(f"[Dhruva Care] Model warm-up error: {err}")
    thread = threading.Thread(target=_loader, daemon=True)
    thread.start()


def _specialist(condition):
    text = str(condition).lower()
    rules = (
        (("skin", "dermat", "rash", "eczema", "psoriasis", "ulcer"), "Dermatologist"),
        (("heart", "cardiac", "hypertension", "blood pressure", "palpitat", "tachycard"), "Cardiologist"),
        (("lung", "respir", "asthma", "cough", "pneum", "dyspnea"), "Pulmonologist"),
        (("bone", "joint", "arthritis", "fracture", "orthop"), "Orthopedic specialist"),
        (("eye", "vision", "retina"), "Eye specialist"),
        (("ear", "hearing", "sinus", "throat"), "ENT specialist"),
        (("pregnan", "gyn", "menstrual"), "Gynecologist"),
        (("child", "pediatric", "infant"), "Pediatrician"),
        (("diabet", "thyroid", "hormone"), "Endocrinologist"),
        (("kidney", "renal", "urine"), "Nephrologist"),
        (("brain", "neuro", "migraine", "seizure", "ataxia", "paresthesia", "insomnia"), "Neurologist"),
        (("stomach", "gastro", "liver", "digest", "vomit", "nausea"), "Gastroenterologist"),
    )
    return next((specialty for keywords, specialty in rules if any(word in text for word in keywords)), "General Medicine doctor")


def _find_matching_doctors(specialty_title):
    title_lower = specialty_title.lower()
    terms = [w for w in title_lower.split() if len(w) > 3 and w not in ("doctor", "specialist")]
    matched = []
    for doc in load("doctors"):
        if not _is_listed(doc):
            continue
        doc_spec = (doc.get("specialty") or "").lower()
        if any(term in doc_spec for term in terms) or "general" in doc_spec or "medicine" in doc_spec:
            matched.append(public_doctor(doc, include_availability=True))
    return matched


@symptom_checker_bp.get("/api/symptom-checker/symptoms")
def search_symptoms():
    query = (request.args.get("q") or "").strip()
    if len(query) < 2:
        return jsonify({"symptoms": POPULAR_SYMPTOMS, "popular": True})
    try:
        _, symptoms, _ = _model_data()
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503

    needle = _key(query)
    results = []
    seen = set()

    # 1. Check synonym mappings first for high-intent matching
    for syn_key, tokens in SYNONYM_MAP.items():
        if needle in _key(syn_key) or _key(syn_key) in needle:
            for token in tokens:
                if token in symptoms and token not in seen:
                    seen.add(token)
                    results.append({"id": token, "label": _readable(token), "priority": True})

    # 2. General substring match across the 12,000 symptoms
    for item in symptoms:
        if item in seen:
            continue
        if needle in _key(item):
            seen.add(item)
            results.append({"id": item, "label": _readable(item), "priority": False})
            if len(results) >= 25:
                break

    return jsonify({"symptoms": results[:20]})


@symptom_checker_bp.post("/api/symptom-checker/assess")
def assess_symptoms():
    selected = (request.get_json(silent=True) or {}).get("symptoms") or []
    if not isinstance(selected, list) or not selected:
        return jsonify({"error": "Choose at least one symptom"}), 400
    try:
        model, columns, diseases = _model_data()
        import numpy as np
        import pandas as pd
    except (RuntimeError, ImportError) as exc:
        return jsonify({"error": str(exc)}), 503

    known = {_key(column): column for column in columns}
    chosen = list(dict.fromkeys(known[_key(item)] for item in selected if _key(item) in known))
    if not chosen:
        return jsonify({"error": "The selected symptoms are not recognised by the model"}), 400

    vector = pd.DataFrame(np.zeros((1, len(columns)), dtype="uint8"), columns=columns)
    vector.loc[0, chosen] = 1
    distances, indices = model.kneighbors(vector, n_neighbors=min(12, len(diseases)))
    suggestions = []
    seen = set()
    for distance, index in zip(distances[0], indices[0]):
        condition = str(diseases.iloc[int(index)] if hasattr(diseases, "iloc") else diseases[int(index)])
        if condition in seen:
            continue
        seen.add(condition)
        spec = _specialist(condition)
        suggestions.append({
            "condition": condition,
            "match_score": round(max(0.0, 1.0 - float(distance)) * 100, 1),
            "specialist": spec,
        })
        if len(suggestions) == 4:
            break

    lead = suggestions[0] if suggestions else {"condition": "No close match", "match_score": 0, "specialist": "General Medicine doctor"}
    specialist_recommendation = lead["specialist"]
    matching_doctors = _find_matching_doctors(specialist_recommendation)

    return jsonify({
        "selected_symptoms": [{"id": item, "label": _readable(item)} for item in chosen],
        "recommendation": specialist_recommendation,
        "possible_matches": suggestions,
        "matching_doctors": matching_doctors[:4],
        "disclaimer": "This screening result is provided by the Dhruva Care Machine Learning Model as guidance. It is not a clinical diagnosis. Seek emergency care for severe or worsening symptoms.",
    })

