import os
from .conftest import *  # noqa
from app.db import Base, engine, SessionLocal
from app.services import kb as K, ner, engine as E


def _kb():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        K.seed_kb(db)
    return K.get_kb()


# small hand-written gold set: (text, {type: set(normalized)}) - illustrative, NOT a benchmark
GOLD = [
    ("Patient on Dolo 650 mg SOS and Glycomet 500 mg BD.", {"MEDICATION": {"Acetaminophen", "Metformin"}}),
    ("Tab. Telma 40mg OD, Tab Amlong 5 mg OD", {"MEDICATION": {"Amlodipine"}}),
    ("Denies chest pain. No history of asthma. Known case of hypertension and T2DM.", {"CONDITION": {"High blood pressure", "Diabetes"}}),
    ("Allergic to sulfa and aspirin.", {"ALLERGY": {"Sulfa (sulfonamide) drugs", "Aspirin / NSAIDs"}}),
    ("Allergies: NKDA", {}),
    ("Started warfarin 3 mg daily; ibuprofen discontinued.", {"MEDICATION": {"Warfarin", "Ibuprofen"}}),
    ("Takes Atorvastin 20mg HS and Metoprolol 50 mg BD.", {"MEDICATION": {"Atorvastatin", "Metoprolol"}}),
    ("Family history: father had diabetes. Patient has CKD stage 3.", {"CONDITION": {"Kidney disease / reduced kidney function"}}),
    ("Lisinopril 10 mg once daily, spironolactone 25 mg daily, furosemide 40 mg IV.", {"MEDICATION": {"Lisinopril", "Spironolactone", "Furosemide"}}),
    ("Sertraline 50mg OD for depression. Pregnant, 12 weeks.", {"MEDICATION": {"Sertraline"}, "CONDITION": {"Pregnancy"}}),
]


def test_ner_gold_set_scores():
    kb = _kb(); tp = fp = fn = 0
    for text, gold in GOLD:
        res = ner.extract(text, kb)
        pred = {}
        for e in res["entities"]:
            if e["include"] and e["type"] in ("MEDICATION", "CONDITION", "ALLERGY") and (e["type"] != "MEDICATION" or e.get("in_kb")):
                pred.setdefault(e["type"], set()).add(e["normalized"])
        for t in ("MEDICATION", "CONDITION", "ALLERGY"):
            g, p = gold.get(t, set()), pred.get(t, set())
            tp += len(g & p); fp += len(p - g); fn += len(g - p)
    prec, rec = tp / (tp + fp), tp / (tp + fn)
    print(f"\nNER gold set: precision={prec:.2f} recall={rec:.2f} (tp={tp} fp={fp} fn={fn})")
    assert prec >= 0.9 and rec >= 0.85


def test_engine_sanity_rules():
    kb = _kb()
    r = E.analyze(kb, {"age": 30, "sex": "female", "pregnant": True}, [{"name": "Lisinopril"}, {"name": "Atorvastatin"}], [], [])
    assert any(p["level"] == "Critical" and p["drug"] == "Lisinopril" for p in r["precautions"])
    r = E.analyze(kb, {"age": 50}, [{"name": "Sildenafil"}, {"name": "Isosorbide mononitrate"}], [], [])
    assert r["overall"]["level"] in ("High", "Critical")
    r = E.analyze(kb, {"age": 40, "egfr": 25}, [{"name": "Metformin"}], [], [])
    assert r["precautions"] and r["precautions"][0]["level"] == "Critical"
    r = E.analyze(kb, {"age": 40}, [{"name": "Penicillin V"}, {"name": "Cetirizine"}], [], [])
    assert "Penicillin V" in r["unassessed"] and r["overall"]["level"] == "None"
    r = E.analyze(kb, {"age": 40}, [{"name": "Warfarin"}, {"name": "Rifampicin"}], [], [])
    assert r["interactions"] and r["interactions"][0]["base_severity"] == "Major"
    r = E.analyze(kb, {"age": 40}, [{"name": "Ibuprofen"}], [], [{"allergen": "Ibuprofen"}])
    assert r["allergy_alerts"][0]["level"] == "Critical"
