"""
Clinical NER for patient reports (medications, conditions, allergies, labs/vitals).

Method (no training data required, fully offline, deterministic):
  1. Lexicon matching   - regex over KB drug names + brand/Indian-brand synonyms, condition and allergen lexicons (longest match wins)
  2. Fuzzy matching     - RapidFuzz (ratio >= 90) for misspelt drug names, only when a dose / 'tab' cue follows (limits false positives)
  3. Unknown-drug rule  - "<Word> 40 mg" patterns -> flagged as a medication that is NOT covered by the interaction KB
  4. Attribute parsing  - dose, frequency (OD/BD/TDS/QID/1-0-1/PRN ...), route
  5. Context            - NegEx-style negation, stopped/held meds, family-history filter, section awareness (Allergies / Medications ...)
  6. Lab & vital regex  - creatinine, eGFR, ALT/AST, K+, INR, HbA1c, BP, HR, weight, height (+ unit conversion, plausibility checks)
The `Recognizer` hook at the bottom lets you plug in a trained model (spaCy / transformer) later.
"""
import re
from rapidfuzz import process, fuzz
from ..data.lexicons import CONDITIONS, ALLERGENS, NO_ALLERGY
from .kb import KB, norm

MAX_CHARS = 60_000
STOP = set("""creatinine potassium sodium weight height hemoglobin haemoglobin glucose sugar pressure pulse cholesterol platelets calcium magnesium
temperature oxygen saturation bmi hba1c egfr urea blood heart rate dose tablet tablets capsule capsules daily patient history diagnosis
plan assessment review follow medicine medicines medication medications allergy allergies year years male female""".split())
HEADER = re.compile(r"^[ \t]*(allerg(?:y|ies)|(?:current |home |discharge )?medications?|medicines|drug history|rx|past medical history|pmh|medical history|"
                    r"diagnos(?:is|es)|family history|fh|social history|labs?|investigations?|vitals?|plan|assessment|history of present illness|hpi)[ \t]*[:\-]", re.I | re.M)
NEG = re.compile(r"\b(no|denies|denied|without|negative for|not on|never|free of|ruled out|rule out|no evidence of|no history of|no h/o|nil|absent)\b", re.I)
STOPPED = re.compile(r"\b(stopped|discontinued|d/c|dc'd|held|on hold|withheld|off|ceased|previously on|was on|completed)\b", re.I)
FAMILY = re.compile(r"\b(family history|fh|mother|father|sister|brother|grandmother|grandfather|parents?)\b", re.I)
DOSE = re.compile(r"(\d+(?:[.,]\d+)?)\s?(mg|mcg|µg|ug|g|ml|iu|units?|u)\b", re.I)
FREQ = [(r"\b(?:od|qd|once (?:a |per )?(?:day|daily)|daily|1-0-0|0-1-0|every morning|in the morning)\b", "once daily"),
        (r"\b(?:bd|bid|b\.i\.d|twice (?:a |per )?(?:day|daily)|1-0-1|two times daily)\b", "twice daily"),
        (r"\b(?:tds|tid|t\.i\.d|thrice (?:a |per )?(?:day|daily)|three times (?:a )?(?:day|daily)|1-1-1)\b", "three times daily"),
        (r"\b(?:qid|q\.i\.d|four times (?:a )?(?:day|daily))\b", "four times daily"),
        (r"\b(?:hs|qhs|at night|bedtime|nocte|0-0-1)\b", "at bedtime"),
        (r"\b(?:prn|sos|as needed|when required)\b", "as needed"),
        (r"\bweekly|once a week|once weekly\b", "weekly"),
        (r"\bq\s?(\d{1,2})\s?h\b", None)]
ROUTE = [(r"\b(?:po|oral(?:ly)?|by mouth)\b", "oral"), (r"\b(?:iv|intravenous)\b", "IV"), (r"\b(?:im|intramuscular)\b", "IM"),
         (r"\b(?:sc|subcut(?:aneous)?|s/c)\b", "SC"), (r"\b(?:topical|cream|ointment)\b", "topical"), (r"\b(?:inhaled|inhaler|nebuli[sz]ed)\b", "inhaled"), (r"\b(?:sl|sublingual)\b", "sublingual")]
CUE = re.compile(r"^\s*(?:tab(?:let)?s?\.?|cap(?:sule)?s?\.?|inj\.?|syp\.?|syrup)?\s*\(?\s*\d|\b(tab|tablet|cap|capsule|inj|syp)\b", re.I)
REACT = ["anaphylaxis", "angioedema", "hives", "urticaria", "rash", "swelling", "itching", "breathlessness", "wheeze", "vomiting", "nausea", "cough", "shock"]

LABS = [  # key, regex, converter, (min,max), label
    ("serum_creatinine", r"\b(?:serum\s+)?creatinine\b[^\d\n]{0,12}(\d+(?:\.\d+)?)\s*(mg/dl|µmol/l|umol/l|mmol/l)?", "creat", (0.2, 15), "Creatinine"),
    ("egfr", r"\be?gfr\b[^\d\n]{0,12}(\d+(?:\.\d+)?)", None, (3, 150), "eGFR"),
    ("alt", r"\b(?:alt|sgpt)\b[^\d\n]{0,10}(\d+(?:\.\d+)?)", None, (3, 3000), "ALT"),
    ("ast", r"\b(?:ast|sgot)\b[^\d\n]{0,10}(\d+(?:\.\d+)?)", None, (3, 3000), "AST"),
    ("potassium", r"(?:\bpotassium\b|\bserum k\b|(?<![a-z])k\+?)[^\d\n]{0,10}(\d\.\d{1,2})\b", None, (2, 8), "Potassium"),
    ("inr", r"\binr\b[^\d\n]{0,10}(\d+(?:\.\d+)?)", None, (0.5, 10), "INR"),
    ("hba1c", r"\bhba1c\b[^\d\n]{0,10}(\d+(?:\.\d+)?)", None, (3, 18), "HbA1c"),
    ("heart_rate", r"\b(?:heart rate|pulse|hr)\b[^\d\n]{0,8}(\d{2,3})\b", None, (30, 220), "Heart rate"),
    ("weight_kg", r"\b(?:weight|wt)\b[^\d\n]{0,8}(\d+(?:\.\d+)?)\s*(kg|kgs|lb|lbs)?", "wt", (2, 300), "Weight"),
    ("height_cm", r"\b(?:height|ht)\b[^\d\n]{0,8}(\d+(?:\.\d+)?)\s*(cm|m|ft)?", "ht", (40, 250), "Height"),
]
BP = re.compile(r"\b(?:bp|blood pressure)\b[^\d\n]{0,8}(\d{2,3})\s*/\s*(\d{2,3})", re.I)
AGE = re.compile(r"\b(\d{1,3})\s*(?:y/?o|yo|yrs?|years?)[\s\-]*(?:old)?\b|\bage[:\s]+(\d{1,3})\b", re.I)


def _conv(kind, val, unit):
    unit = (unit or "").lower()
    if kind == "creat" and unit in ("µmol/l", "umol/l"): return round(val / 88.4, 2)
    if kind == "wt" and unit.startswith("lb"): return round(val * 0.4536, 1)
    if kind == "ht":
        if unit == "m" or (not unit and val < 3): return round(val * 100, 1)
        if unit == "ft": return round(val * 30.48, 1)
    return val


def _compile(kb: KB):
    if getattr(kb, "_ner", None):
        return kb._ner
    def alt(terms):
        terms = sorted({t for t in terms if len(t) >= 3}, key=len, reverse=True)
        return re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(t) for t in terms) + r")(?![a-z0-9])", re.I)
    cond_terms = {t: k for k, v in CONDITIONS.items() for t in v["terms"]}
    kb._ner = {"drug": alt(kb.alias.keys()), "cond": alt(cond_terms.keys()), "cond_map": cond_terms}
    return kb._ner


def _attrs(text, end):
    seg = re.split(r"[\n;]", text[end:end + 90])[0]
    seg = re.split(r"\b(?:and|with|,)\b", seg, maxsplit=1)[0] if len(DOSE.findall(seg)) > 1 else seg
    out = {"dose": None, "frequency": None, "route": None}
    m = DOSE.search(seg)
    if m: out["dose"] = f"{m.group(1).replace(',', '.')} {m.group(2).lower()}"
    for pat, label in FREQ:
        f = re.search(pat, seg, re.I)
        if f: out["frequency"] = label or f"every {f.group(1)} hours"; break
    for pat, label in ROUTE:
        if re.search(pat, seg, re.I): out["route"] = label; break
    return out


def _sections(text):
    marks = [(m.start(), m.group(1).lower()) for m in HEADER.finditer(text)]
    def at(pos):
        cur = None
        for s, name in marks:
            if s <= pos: cur = name
            else: break
        return cur
    return at, marks


def _window_before(text, start, n=60):
    seg = text[max(0, start - n):start]
    return re.split(r"[.;\n]", seg)[-1]


def extract(text: str, kb: KB, recognizers=()) -> dict:
    text = (text or "")[:MAX_CHARS]
    low = text.lower()
    if len(low) != len(text):  # rare unicode case-folding length change: fall back to ASCII-safe copy
        low = "".join(c.lower() if len(c.lower()) == 1 else c for c in text)
    rx = _compile(kb)
    section_at, marks = _sections(low)
    ents, taken = [], []

    def free(s, e): return all(e <= a or s >= b for a, b in taken)

    # ---- allergies first (their spans suppress medication/condition matches) ----
    allergy_spans = []
    for m in re.finditer(r"(?:allerg(?:ic|y|ies)|hypersensitiv\w*|intoleran\w*)\s*(?:to|:|-)\s*([^.;\n]{2,100})", low):
        allergy_spans.append((m.start(1), m.end(1)))
    for i, (s, name) in enumerate(marks):
        if name.startswith("allerg"):
            hs = low.index(":", s) + 1 if ":" in low[s:s + 20] else s
            end = next((marks[j][0] for j in range(i + 1, len(marks))), len(low))
            blank = re.search(r"\n\s*\n", low[hs:end]); end = hs + blank.start() if blank else end
            allergy_spans.append((hs, end))
    skip_nkda = any(n in low for n in NO_ALLERGY)
    for (s, e) in allergy_spans:
        for part in re.finditer(r"[^,;/\n•\*]+?(?=,|;|/|\n|•|\*|\band\b|$)", low[s:e]):
            raw = part.group(0)
            item = re.sub(r"\(.*?\)|[-–:]", " ", raw).strip(" .-")
            if len(item) < 3 or item in NO_ALLERGY or re.fullmatch(r"(?:and|etc|none|nil)", item):
                continue
            a, b = s + part.start() + (len(raw) - len(raw.lstrip())), s + part.end()
            key = next((k for k, v in ALLERGENS.items() if any(re.search(rf"(?<![a-z]){re.escape(t)}(?![a-z])", item) for t in v["terms"])), None)
            reaction = next((r for r in REACT if r in low[s + part.start():min(len(low), s + part.end() + 40)]), None)
            if not free(a, b): continue
            taken.append((a, b))
            ents.append({"type": "ALLERGY", "text": text[a:b].strip(" ."), "start": a, "end": a + len(text[a:b].strip(" .")), "normalized": ALLERGENS[key]["label"] if key else item.title(),
                         "key": key, "confidence": 0.9 if key else 0.7, "attrs": {"reaction": reaction}})

    # ---- lexicon matches ----
    cands = []
    for m in rx["drug"].finditer(low):
        d = kb.resolve(m.group(0), fuzzy=False)
        if d: cands.append((m.start(), m.end(), "FOOD" if d["kind"] == "food" else "MEDICATION", d, 1.0, "lexicon"))
    for m in rx["cond"].finditer(low):
        cands.append((m.start(), m.end(), "CONDITION", rx["cond_map"][m.group(0)], 1.0, "lexicon"))
    for s, e, typ, payload, conf, src in sorted(cands, key=lambda c: (-(c[1] - c[0]), c[0])):
        if free(s, e):
            taken.append((s, e))
            if typ == "CONDITION":
                v = CONDITIONS[payload]
                ents.append({"type": typ, "text": text[s:e], "start": s, "end": e, "normalized": v["label"], "key": payload, "confidence": conf, "attrs": {}})
            else:
                ents.append({"type": typ, "text": text[s:e], "start": s, "end": e, "normalized": payload["name"], "key": payload["name"], "in_kb": True, "confidence": conf,
                             "attrs": _attrs(low, e) if typ == "MEDICATION" else {}, "source": src})

    # ---- fuzzy (misspellings) - requires a dose/tab cue ----
    for m in re.finditer(r"[a-z][a-z\-]{5,}", low):
        s, e = m.span()
        if not free(s, e) or m.group(0) in STOP: continue
        after, before = low[e:e + 25], low[max(0, s - 6):s]
        if not (CUE.search(after) or re.search(r"\b(tab|cap|inj|t)\.?\s*$", before)): continue
        d = kb.resolve(m.group(0), fuzzy=True)
        if d:
            taken.append((s, e))
            ents.append({"type": "MEDICATION", "text": text[s:e], "start": s, "end": e, "normalized": d["name"], "key": d["name"], "in_kb": True, "confidence": 0.75,
                         "attrs": _attrs(low, e), "source": "fuzzy"})

    # ---- unknown drugs: "<Word> 40 mg" ----
    for m in re.finditer(r"(?<![a-z0-9])([a-z][a-z\-]{3,})\s+(\d+(?:\.\d+)?)\s?(?:mg|mcg|µg|ug|g|ml|iu|units?)\b", low):
        s, e = m.start(1), m.end(1)
        if free(s, e) and m.group(1) not in STOP and not re.search(r"(?:serum|level|hr|bp)\s*$", low[max(0, s - 10):s]):
            taken.append((s, e))
            ents.append({"type": "MEDICATION", "text": text[s:e], "start": s, "end": e, "normalized": text[s:e].title(), "key": None, "in_kb": False, "confidence": 0.5,
                         "attrs": _attrs(low, e), "source": "pattern"})

    for rec in recognizers:  # optional trained models
        for ent in rec(text) or []:
            if free(ent["start"], ent["end"]):
                taken.append((ent["start"], ent["end"])); ents.append(ent)

    # ---- context: negation / stopped / family / section ----
    for en in ents:
        win = _window_before(low, en["start"])
        sec = section_at(en["start"])
        line_start = low.rfind("\n", 0, en["start"]) + 1
        after_line = low[en["end"]:low.find("\n", en["end"]) if "\n" in low[en["end"]:] else len(low)]
        en["negated"] = bool(NEG.search(win[-40:])) and en["type"] in ("CONDITION", "ALLERGY", "MEDICATION") and not (en["type"] == "ALLERGY" and "no known" not in win)
        en["family"] = bool(FAMILY.search(win) or sec in ("family history", "fh") or FAMILY.search(low[line_start:en["start"]]))
        en["status"] = "stopped" if en["type"] == "MEDICATION" and (STOPPED.search(win[-30:]) or STOPPED.search(after_line[:40])) else "active"
        en["section"] = sec
        en["include"] = not (en["negated"] or en["family"]) and en["type"] != "FOOD"
    ents.sort(key=lambda x: x["start"])
    for i, en in enumerate(ents, 1):
        en["id"] = f"e{i}"

    # ---- labs & vitals ----
    labs, lab_ents = {}, []
    for key, pat, conv, (lo, hi), label in LABS:
        for m in re.finditer(pat, low):
            try:
                v = float(m.group(1)); v = _conv(conv, v, m.group(2) if m.lastindex and m.lastindex >= 2 else None)
            except (ValueError, TypeError):
                continue
            if lo <= v <= hi and key not in labs:
                labs[key] = v; lab_ents.append({"type": "LAB", "text": text[m.start():m.end()].strip(), "start": m.start(), "end": m.end(), "normalized": label, "key": key, "value": v, "confidence": 0.9, "include": True, "negated": False, "family": False, "attrs": {}})
    bp = BP.search(low)
    if bp and 60 <= int(bp.group(1)) <= 260 and 30 <= int(bp.group(2)) <= 150:
        labs["systolic_bp"], labs["diastolic_bp"] = int(bp.group(1)), int(bp.group(2))
        lab_ents.append({"type": "LAB", "text": text[bp.start():bp.end()], "start": bp.start(), "end": bp.end(), "normalized": "Blood pressure", "key": "bp", "value": f"{bp.group(1)}/{bp.group(2)}", "confidence": 0.9, "include": True, "negated": False, "family": False, "attrs": {}})
    for k in ("heart_rate", "alt", "ast", "systolic_bp", "diastolic_bp"):
        if k in labs: labs[k] = int(labs[k])
    hints = {}
    a = AGE.search(low)
    if a:
        age = int(a.group(1) or a.group(2))
        if 0 < age < 120: hints["age"] = age
    if re.search(r"\bnon[- ]?smoker|never smoked|does not smoke\b", low): hints["smoker"] = "never"
    elif re.search(r"\bex[- ]?smoker|former smoker|quit smoking\b", low): hints["smoker"] = "former"
    elif re.search(r"\bsmoker|smokes|smoking\b", low): hints["smoker"] = "current"
    if re.search(r"\b(?:no alcohol|teetotal|does not drink|non[- ]?drinker)\b", low): hints["alcohol"] = "none"
    elif re.search(r"\b(?:heavy|excess(?:ive)?) (?:alcohol|drinker|drinking)|alcohol abuse|alcohol use disorder\b", low): hints["alcohol"] = "heavy"
    elif re.search(r"\b(?:occasional(?:ly)?|social(?:ly)?|rarely)\b[^.\n]{0,25}(?:alcohol|drink)|(?:alcohol|drinks?)[^.\n]{0,25}\b(?:occasional(?:ly)?|social(?:ly)?|rarely)\b", low): hints["alcohol"] = "occasional"
    elif re.search(r"\b(?:drinks|alcohol|beer|whisky|wine)\b", low): hints["alcohol"] = "moderate"
    ents = sorted(ents + lab_ents, key=lambda x: x["start"])

    # ---- de-duplicated suggestions for the review screen ----
    sug = {"medications": [], "conditions": [], "allergies": []}
    seen = set()
    for en in ents:
        if not en.get("include"): continue
        if en["type"] == "MEDICATION":
            k = ("m", norm(en["normalized"]))
            if k in seen: continue
            seen.add(k)
            sug["medications"].append({"name": en["normalized"], "in_kb": en.get("in_kb", False), **en["attrs"], "status": en["status"], "confidence": en["confidence"], "entity_id": en["id"]})
        elif en["type"] == "CONDITION":
            k = ("c", en["key"])
            if k in seen: continue
            seen.add(k)
            sug["conditions"].append({"name": en["normalized"], "condition_key": en["key"], "confidence": en["confidence"], "entity_id": en["id"]})
        elif en["type"] == "ALLERGY":
            k = ("a", norm(en["normalized"]))
            if k in seen: continue
            seen.add(k)
            sug["allergies"].append({"allergen": en["normalized"], "reaction": en["attrs"].get("reaction"), "confidence": en["confidence"], "entity_id": en["id"]})
    return {"entities": ents, "suggestions": sug, "labs": labs, "hints": hints, "no_known_allergies": skip_nkda and not sug["allergies"],
            "stats": {"chars": len(text), "entities": len(ents)}}
