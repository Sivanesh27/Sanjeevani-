"""Runtime knowledge base: drugs/foods, curated interaction rules (editable in the admin console) and the ML fallback."""
import json, os, threading, logging
import numpy as np
from rapidfuzz import process, fuzz
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from ..models import KBDrug, KBInteraction

log = logging.getLogger("sanjeevani.kb")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")
ART = os.path.join(HERE, "ml_artifacts")
_lock = threading.Lock()
_kb = None


def norm(s: str) -> str:
    return " ".join((s or "").lower().replace("_", " ").split())


class MLModel:
    def __init__(self):
        import xgboost as xgb
        self.xgb = xgb
        self.meta = json.load(open(os.path.join(ART, "meta.json")))
        self.metrics = json.load(open(os.path.join(ART, "metrics.json")))
        self.booster = xgb.Booster(); self.booster.load_model(os.path.join(ART, "model.json"))
        self.tag_i = {t: i for i, t in enumerate(self.meta["tags"])}
        self.cls_i = {c: i for i, c in enumerate(self.meta["classes"])}

    def predict(self, da: dict, db: dict):
        n = len(self.tag_i)
        a = np.zeros(n); b = np.zeros(n)
        for t in da["tags"]:
            if t in self.tag_i: a[self.tag_i[t]] = 1
        for t in db["tags"]:
            if t in self.tag_i: b[self.tag_i[t]] = 1
        ci = sorted([self.cls_i.get(da["class_name"], 0), self.cls_i.get(db["class_name"], 0)])
        x = np.concatenate([np.maximum(a, b), np.minimum(a, b), ci]).reshape(1, -1)
        p = self.booster.predict(self.xgb.DMatrix(x))[0]
        k = int(np.argmax(p))
        return self.meta["labels"][k], float(p[k])


class KB:
    def __init__(self, drugs, interactions):
        self.drugs, self.alias, self.pairs = {}, {}, {}
        for d in drugs:
            rec = {"name": d.name, "class_name": d.class_name, "kind": d.kind, "tags": list(d.tags or [])}
            self.drugs[norm(d.name)] = rec
            self.alias[norm(d.name)] = norm(d.name)
            for s in d.synonyms or []:
                self.alias.setdefault(norm(s), norm(d.name))
        for r in interactions:
            a, b = norm(r.drug_a), norm(r.drug_b)
            self.pairs[frozenset((a, b))] = {"drug_a": r.drug_a, "drug_b": r.drug_b, "severity": r.severity, "mechanism": r.mechanism,
                                             "effect": r.effect, "management": r.management, "diet_advice": r.diet_advice}
        self.alias_keys = [k for k in self.alias if len(k) >= 5]
        try:
            self.ml = MLModel()
        except Exception as e:  # service keeps working on curated rules only
            log.error("ML model unavailable: %s", e); self.ml = None

    def resolve(self, name: str, fuzzy: bool = True):
        """Map free text (brand, generic, misspelling) to a canonical KB drug record, or None."""
        key = norm(name)
        if key in self.alias:
            return self.drugs[self.alias[key]]
        if fuzzy and len(key) >= 5 and " " not in key:
            hit = process.extractOne(key, self.alias_keys, scorer=fuzz.ratio, score_cutoff=88)
            if hit:
                return self.drugs[self.alias[hit[0]]]
        return None

    def pair(self, a: str, b: str):
        return self.pairs.get(frozenset((norm(a), norm(b))))

    def classes_of(self, name: str):
        d = self.drugs.get(norm(name)); return d["class_name"] if d else None


def seed_kb(db: Session) -> int:
    if db.scalar(select(func.count()).select_from(KBDrug)):
        return 0
    syn = json.load(open(os.path.join(DATA, "synonyms.json")))
    for d in json.load(open(os.path.join(DATA, "kb_drugs.json"), encoding="utf-8")):
        db.add(KBDrug(name=d["name"], class_name=d["class_name"], kind=d["kind"], tags=d["tags"], synonyms=syn.get(d["name"], [])))
    for r in json.load(open(os.path.join(DATA, "kb_interactions.json"), encoding="utf-8")):
        db.add(KBInteraction(**r))
    db.commit()
    return 1


def get_kb(db: Session | None = None) -> KB:
    global _kb
    if _kb is None:
        with _lock:
            if _kb is None:
                from ..db import SessionLocal
                own = db is None
                s = db or SessionLocal()
                try:
                    _kb = KB(s.scalars(select(KBDrug)).all(), s.scalars(select(KBInteraction)).all())
                finally:
                    if own: s.close()
    return _kb


def invalidate():
    global _kb
    with _lock:
        _kb = None
