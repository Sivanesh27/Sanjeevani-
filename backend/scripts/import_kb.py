"""Upsert app/data/kb_drugs.json + kb_interactions.json into the database (safe to re-run; existing rows are kept)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlalchemy import select
from app.db import Base, engine, SessionLocal
from app import models
from app.models import KBDrug, KBInteraction
D = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "data")

Base.metadata.create_all(engine)
syn = json.load(open(os.path.join(D, "synonyms.json")))
with SessionLocal() as db:
    have = {d.name.lower() for d in db.scalars(select(KBDrug))}
    nd = 0
    for d in json.load(open(os.path.join(D, "kb_drugs.json"), encoding="utf-8")):
        if d["name"].lower() not in have:
            db.add(KBDrug(name=d["name"], class_name=d["class_name"], kind=d["kind"], tags=d["tags"], synonyms=syn.get(d["name"], []))); nd += 1
    pairs = {frozenset((r.drug_a.lower(), r.drug_b.lower())) for r in db.scalars(select(KBInteraction))}
    ni = 0
    for r in json.load(open(os.path.join(D, "kb_interactions.json"), encoding="utf-8")):
        k = frozenset((r["drug_a"].lower(), r["drug_b"].lower()))
        if k not in pairs: db.add(KBInteraction(**r)); pairs.add(k); ni += 1
    db.commit()
print(f"imported {nd} new drugs and {ni} new interactions. Restart the API (or press 'Reload KB' in the doctor console).")
