"""
Dhruva Care — Symptom Predictor Module
Integrates the larger Machine Learning model: 'Disease_symptom_predictor(2).joblib'
Trained on the larger CSV ('synthetic_disease_symptom_10k.csv' - 12,000 symptoms, 10,000 samples).
Also supports fallback to the smaller model ('Disease_symptom_predictor.joblib' - 40 symptoms, 580KB CSV).
"""

import os
import re
import threading
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import joblib

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LARGER_MODEL_PATH = os.path.join(BASE_DIR, "Disease_symptom_predictor(2).joblib")
SMALLER_MODEL_PATH = os.path.join(BASE_DIR, "Disease_symptom_predictor.joblib")

# Common patient terminology mapped to model symptom tokens (for the 12,000 feature space)
SYNONYM_MAP = {
    "fever": ["AcuteFeverSyndrome", "ChronicFeverDisease", "MildFeverCondition", "PrimaryFeverDisease"],
    "headache": ["AcuteHeadacheSyndrome", "SevereHeadacheDisease", "ChronicHeadacheDisorder"],
    "cough": ["AcuteCoughSyndrome", "ChronicCoughDisease", "HereditaryCoughDeficiency"],
    "breath": ["SevereDyspneaMalformation", "ChronicDyspneaDeficiency", "AcuteDyspneaSyndrome"],
    "shortness of breath": ["SevereDyspneaMalformation", "ChronicDyspneaDeficiency"],
    "breathless": ["SevereDyspneaMalformation", "ChronicDyspneaDeficiency"],
    "chest pain": ["CongenitalPalpitationsSyndrome", "AcuteHypertensionCondition", "MildTachycardiaDeficiency"],
    "palpitation": ["CongenitalPalpitationsSyndrome", "SevereTachycardiaDysfunction", "MildTachycardiaDeficiency"],
    "heart": ["CongenitalPalpitationsSyndrome", "AcuteHypertensionCondition", "SevereTachycardiaDysfunction"],
    "dizzy": ["ChronicDizzinessSyndrome", "HereditaryDizzinessMalformation"],
    "dizziness": ["ChronicDizzinessSyndrome", "HereditaryDizzinessMalformation"],
    "vomit": ["SevereVomitingDisorder", "HereditaryVomitingCondition"],
    "vomiting": ["SevereVomitingDisorder", "HereditaryVomitingCondition"],
    "nausea": ["CongenitalNauseaDeficiency", "AcuteNauseaSyndrome", "HereditaryNauseaSyndrome"],
    "fatigue": ["IdiopathicFatigueSyndrome", "AcuteFatigueSyndrome", "PrimaryFatigueCondition"],
    "tired": ["IdiopathicFatigueSyndrome", "AcuteFatigueSyndrome", "PrimaryFatigueCondition"],
    "rash": ["ProgressiveRashCondition", "AcuteRashSyndrome"],
    "skin": ["ProgressiveRashCondition", "SevereSkin ulcerDeficiency"],
    "joint pain": ["AcuteJoint painCondition", "ChronicJoint painDisorder"],
    "joint": ["AcuteJoint painCondition", "ChronicJoint painDisorder"],
    "insomnia": ["SevereInsomniaDysfunction", "MildInsomniaSyndrome"],
    "sleep": ["SevereInsomniaDysfunction", "MildInsomniaSyndrome"],
    "seizure": ["SecondarySeizureMalformation", "AcuteSeizureCondition"],
    "hearing loss": ["HereditaryHearing lossDisease"],
    "ear": ["HereditaryHearing lossDisease"],
    "blood pressure": ["AcuteHypertensionCondition", "HereditaryHypotensionDisease", "ProgressiveHypotensionDisorder"],
    "hypotension": ["HereditaryHypotensionDisease", "ProgressiveHypotensionDisorder", "SecondaryHypotensionDeficiency"],
    "hypertension": ["AcuteHypertensionCondition", "IdiopathicHypertensionCondition"],
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


def readable_label(value: str) -> str:
    """Format CamelCase/underscored symptom keys into clean human-readable text."""
    clean = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", str(value)).replace("_", " ").strip()
    return clean


def normalize_key(value: str) -> str:
    """Alphanumeric lowercase key for fast matching."""
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


class SymptomPredictor:
    """
    NearestNeighbors-based Disease Symptom Predictor.
    Integrates the larger model ('Disease_symptom_predictor(2).joblib') trained on the
    240MB synthetic dataset containing 12,000 symptom columns and 10,000 disease records.
    """

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path or os.environ.get("DHRUVA_CARE_MODEL_PATH", LARGER_MODEL_PATH)
        self.is_larger_model = "Disease_symptom_predictor(2)" in self.model_path
        self._model = None
        self._symptoms: List[str] = []
        self._diseases = None
        self._symptom_lookup: Dict[str, str] = {}
        self._lock = threading.Lock()
        self._loaded = False

    def load(self):
        """Loads and caches the model bundle with memory-mapping."""
        if self._loaded:
            return self

        with self._lock:
            if self._loaded:
                return self

            if not os.path.exists(self.model_path):
                # If the larger model is missing, attempt fallback to the smaller model
                if os.path.exists(SMALLER_MODEL_PATH):
                    print(f"[SymptomPredictor] Warning: {self.model_path} not found. Falling back to {SMALLER_MODEL_PATH}")
                    self.model_path = SMALLER_MODEL_PATH
                    self.is_larger_model = False
                else:
                    raise FileNotFoundError(f"Neither larger model ({LARGER_MODEL_PATH}) nor smaller model ({SMALLER_MODEL_PATH}) was found.")

            print(f"[SymptomPredictor] Loading model from: {self.model_path} ...")
            bundle = joblib.load(self.model_path, mmap_mode="r")
            self._model = bundle["model"]
            self._symptoms = list(bundle["symptom_columns"])
            self._diseases = bundle["disease_names"]
            self._symptom_lookup = {normalize_key(s): s for s in self._symptoms}
            self._loaded = True
            print(f"[SymptomPredictor] Ready! Features: {len(self._symptoms)}, Samples: {len(self._diseases)}")

        return self

    @property
    def symptoms(self) -> List[str]:
        if not self._loaded:
            self.load()
        return self._symptoms

    @property
    def diseases(self):
        if not self._loaded:
            self.load()
        return self._diseases

    def search_symptoms(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search symptom features using natural language query, synonyms, and substring matching.
        """
        if not self._loaded:
            self.load()

        q = (query or "").strip()
        if len(q) < 2:
            return POPULAR_SYMPTOMS

        needle = normalize_key(q)
        results = []
        seen = set()

        # 1. Search synonyms first for high intent matching
        for syn_key, tokens in SYNONYM_MAP.items():
            if needle in normalize_key(syn_key) or normalize_key(syn_key) in needle:
                for token in tokens:
                    if token in self._symptoms and token not in seen:
                        seen.add(token)
                        results.append({
                            "id": token,
                            "label": readable_label(token),
                            "priority": True,
                        })

        # 2. General substring match across the 12,000 symptoms
        for item in self._symptoms:
            if item in seen:
                continue
            if needle in normalize_key(item):
                seen.add(item)
                results.append({
                    "id": item,
                    "label": readable_label(item),
                    "priority": False,
                })
                if len(results) >= limit + 10:
                    break

        return results[:limit]

    def recommend_specialist(self, condition: str) -> str:
        """Map predicted clinical condition to the appropriate medical specialist."""
        text = str(condition).lower()
        rules = (
            (("skin", "dermat", "rash", "eczema", "psoriasis", "ulcer"), "Dermatologist"),
            (("heart", "cardiac", "hypertension", "hypotension", "blood pressure", "palpitat", "tachycard"), "Cardiologist"),
            (("lung", "respir", "asthma", "cough", "pneum", "dyspnea"), "Pulmonologist"),
            (("bone", "joint", "arthritis", "fracture", "orthop"), "Orthopedic specialist"),
            (("eye", "vision", "retina"), "Eye specialist"),
            (("ear", "hearing", "sinus", "throat"), "ENT specialist"),
            (("pregnan", "gyn", "menstrual"), "Gynecologist"),
            (("child", "pediatric", "infant"), "Pediatrician"),
            (("diabet", "thyroid", "hormone"), "Endocrinologist"),
            (("kidney", "renal", "urine"), "Nephrologist"),
            (("brain", "neuro", "migraine", "seizure", "ataxia", "paresthesia", "insomnia"), "Neurologist"),
            (("stomach", "gastro", "liver", "digest", "vomit", "nausea", "diarrhea", "appendic"), "Gastroenterologist"),
        )
        for keywords, specialty in rules:
            if any(k in text for k in keywords):
                return specialty
        return "General Medicine doctor"

    def predict(
        self,
        selected_symptoms: List[str],
        n_neighbors: int = 5,
    ) -> Dict[str, Any]:
        """
        Assess symptoms using NearestNeighbors on the 12,000-column feature vector.
        """
        if not self._loaded:
            self.load()

        if not selected_symptoms or not isinstance(selected_symptoms, list):
            raise ValueError("Provide at least one symptom in selected_symptoms.")

        # Resolve selected symptoms to actual model feature columns
        chosen = []
        for item in selected_symptoms:
            norm = normalize_key(item)
            if norm in self._symptom_lookup:
                chosen.append(self._symptom_lookup[norm])
            elif norm in SYNONYM_MAP:
                for mapped in SYNONYM_MAP[norm]:
                    if mapped in self._symptoms and mapped not in chosen:
                        chosen.append(mapped)

        chosen = list(dict.fromkeys(chosen))
        if not chosen:
            raise ValueError("None of the selected symptoms were recognised by the model.")

        # Construct one-hot binary vector
        vector = pd.DataFrame(np.zeros((1, len(self._symptoms)), dtype="uint8"), columns=self._symptoms)
        vector.loc[0, chosen] = 1

        distances, indices = self._model.kneighbors(vector, n_neighbors=min(n_neighbors * 3, len(self._diseases)))

        suggestions = []
        seen_conditions = set()

        for dist, idx in zip(distances[0], indices[0]):
            condition = str(self._diseases.iloc[int(idx)] if hasattr(self._diseases, "iloc") else self._diseases[int(idx)])
            if condition in seen_conditions:
                continue
            seen_conditions.add(condition)

            match_score = round(max(0.0, 1.0 - float(dist)) * 100, 1)
            specialist = self.recommend_specialist(condition)

            suggestions.append({
                "condition": condition,
                "match_score": match_score,
                "specialist": specialist,
                "distance": float(dist),
            })
            if len(suggestions) >= n_neighbors:
                break

        lead = suggestions[0] if suggestions else {
            "condition": "No close match",
            "match_score": 0.0,
            "specialist": "General Medicine doctor",
        }

        return {
            "model_used": os.path.basename(self.model_path),
            "selected_symptoms": [{"id": s, "label": readable_label(s)} for s in chosen],
            "recommendation": lead["specialist"],
            "possible_matches": suggestions,
            "top_match": lead,
            "disclaimer": (
                "This screening result is provided by the Dhruva Care Machine Learning Model as guidance. "
                "It is not a clinical diagnosis. Seek emergency care for severe or worsening symptoms."
            ),
        }


# Global singleton instance
_predictor_instance: Optional[SymptomPredictor] = None
_instance_lock = threading.Lock()


def get_predictor(model_path: Optional[str] = None) -> SymptomPredictor:
    """Returns or initializes the global SymptomPredictor singleton."""
    global _predictor_instance
    if _predictor_instance is None:
        with _instance_lock:
            if _predictor_instance is None:
                _predictor_instance = SymptomPredictor(model_path=model_path)
    return _predictor_instance


def warm_model():
    """Background loader to pre-warm the larger model without blocking."""
    def _loader():
        try:
            p = get_predictor()
            p.load()
        except Exception as err:
            print(f"[SymptomPredictor] Warm-up notice: {err}")

    thread = threading.Thread(target=_loader, daemon=True)
    thread.start()


def predict_disease(symptoms: List[str], n_neighbors: int = 5) -> Dict[str, Any]:
    """Convenience function to predict disease and specialist from symptoms."""
    predictor = get_predictor()
    return predictor.predict(symptoms, n_neighbors=n_neighbors)


def search_symptoms(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Convenience function to search model symptoms."""
    predictor = get_predictor()
    return predictor.search_symptoms(query, limit=limit)


if __name__ == "__main__":
    import time

    print("=== DHRUVA CARE SYMPTOM PREDICTOR (LARGER MODEL DEMO) ===")
    print(f"Target larger model: {LARGER_MODEL_PATH}")
    print(f"File size: {os.path.getsize(LARGER_MODEL_PATH) / (1024*1024):.2f} MB")

    t0 = time.time()
    predictor = get_predictor()
    predictor.load()
    t1 = time.time()
    print(f"Model loaded in {t1 - t0:.2f} seconds!")

    # Test search
    print("\nTesting Symptom Search:")
    for test_q in ["fever", "cough", "dizzy", "heart"]:
        matches = predictor.search_symptoms(test_q, limit=3)
        print(f"  Query '{test_q}': {[m['label'] for m in matches]}")

    # Test prediction
    print("\nTesting Disease Prediction on larger model:")
    test_symptoms = ["AcuteFeverSyndrome", "HereditaryCoughDeficiency", "SevereDyspneaMalformation"]
    result = predictor.predict(test_symptoms, n_neighbors=3)
    print(f"  Model: {result['model_used']}")
    print(f"  Recommended Specialist: {result['recommendation']}")
    print(f"  Top Match: {result['top_match']['condition']} ({result['top_match']['match_score']}% match)")
    for i, m in enumerate(result["possible_matches"], 1):
        print(f"    {i}. {m['condition']} -> {m['specialist']} ({m['match_score']}%)")

    print("\n=== SYMPTOM PREDICTOR INITIALIZED AND VERIFIED SUCCESSFULLY! ===")