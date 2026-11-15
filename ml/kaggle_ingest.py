"""
Merge an external drug-drug interaction CSV (Kaggle, DDInter, DrugBank-derived exports ...) into the knowledge base.

  # 1) (optional) download from Kaggle with your own API token (~/.kaggle/kaggle.json):
  pip install kaggle && kaggle datasets download -d <owner>/<dataset-slug> -p data/ --unzip
  # 2) merge:
  python ml/kaggle_ingest.py data/interactions.csv                       # auto-detects columns
  python ml/kaggle_ingest.py data/ddinter.csv --a Drug_A --b Drug_B --severity-col Level
  python ml/kaggle_ingest.py data/drugbank_ddi.csv --a "Drug 1" --b "Drug 2" --text-col Interaction
  # 3) load into an existing database:   cd backend && python scripts/import_kb.py

How severity is obtained (be aware of the limits):
  * if the file has a severity/level column (e.g. DDInter: Major/Moderate/Minor) it is mapped directly;
  * otherwise the interaction description is classified with a transparent KEYWORD heuristic (see RULES below).
    This is much cruder than a pharmacist-graded level - review imported rows in the admin Data Explorer.
Imported drugs have no pharmacological tags, so they extend the *curated lookup* (source of truth) but are not used to train the ML fallback.
"""
import argparse, csv, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
APP_DATA = os.path.join(os.path.dirname(HERE), "backend", "app", "data")
RULES = [("Major", r"contraindicat|life.threatening|fatal|serotonin syndrome|torsade|qt.?c? prolong|rhabdomyolysis|hemorrhag|haemorrhag|respiratory depression|hyperkal|severe|toxicity")
         , ("Moderate", r"increase the risk or severity|serum concentration|decrease the (?:therapeutic|metabolism|excretion)|hypotensive|sedative|nephrotoxic|hypoglyc|hepatotoxic|bleeding|anticoagulant|cns depress")]
SEV = {"major": "Major", "severe": "Major", "high": "Major", "contraindicated": "Major", "moderate": "Moderate", "medium": "Moderate", "minor": "Minor", "low": "Minor", "mild": "Minor"}


def guess(cols, *names):
    low = {c.lower().replace(" ", "").replace("_", ""): c for c in cols}
    for n in names:
        if n in low: return low[n]
    return None


def severity(row, sev_col, text_col):
    if sev_col and row.get(sev_col):
        return SEV.get(row[sev_col].strip().lower())
    text = (row.get(text_col) or "").lower() if text_col else ""
    for sev, rx in RULES:
        if re.search(rx, text): return sev
    return "Minor" if text else None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("csv"); ap.add_argument("--a"); ap.add_argument("--b"); ap.add_argument("--severity-col"); ap.add_argument("--text-col"); ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.csv, encoding="utf-8-sig", errors="replace")))
    if not rows: sys.exit("empty file")
    cols = list(rows[0].keys())
    ca = a.a or guess(cols, "drug1", "druga", "drug1name", "druga_name", "drugname1", "name1", "drug1_name", "drug_1")
    cb = a.b or guess(cols, "drug2", "drugb", "drug2name", "drugb_name", "drugname2", "name2", "drug2_name", "drug_2")
    cs = a.severity_col or guess(cols, "level", "severity", "risk", "interactionlevel")
    ct = a.text_col or guess(cols, "description", "interaction", "interactiondescription", "text", "effect", "mechanism")
    if not (ca and cb): sys.exit(f"Could not detect the two drug-name columns in {cols}. Pass --a and --b.")
    print(f"columns -> drug A: {ca} | drug B: {cb} | severity: {cs} | text: {ct}")
    drugs = json.load(open(os.path.join(APP_DATA, "kb_drugs.json"), encoding="utf-8")); inter = json.load(open(os.path.join(APP_DATA, "kb_interactions.json"), encoding="utf-8"))
    known = {d["name"].lower() for d in drugs}
    seen = {frozenset((r["drug_a"].lower(), r["drug_b"].lower())) for r in inter}
    cap = lambda s: s.strip()[:1].upper() + s.strip()[1:]
    added = skipped = 0
    for r in rows[: a.limit or None]:
        x, y = (r.get(ca) or "").strip(), (r.get(cb) or "").strip()
        sev = severity(r, cs, ct)
        if not x or not y or x.lower() == y.lower() or not sev: skipped += 1; continue
        key = frozenset((x.lower(), y.lower()))
        if key in seen: skipped += 1; continue
        seen.add(key)
        for n in (x, y):
            if n.lower() not in known: known.add(n.lower()); drugs.append({"name": cap(n), "class_name": "Imported", "kind": "drug", "tags": []})
        text = (r.get(ct) or "").strip() if ct else ""
        inter.append({"drug_a": cap(x), "drug_b": cap(y), "severity": sev, "mechanism": text or "Imported from an external dataset.", "effect": text[:200] or f"{sev} interaction (imported)",
                      "management": "Imported record - confirm with a pharmacist before acting.", "diet_advice": ""})
        added += 1
    for d in (APP_DATA,):
        json.dump(drugs, open(os.path.join(d, "kb_drugs.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        json.dump(inter, open(os.path.join(d, "kb_interactions.json"), "w", encoding="utf-8"), ensure_ascii=False)
    print(f"added {added} interactions, skipped {skipped}. KB now {len(drugs)} drugs / {len(inter)} interactions.\nNext: cd backend && python scripts/import_kb.py")


if __name__ == "__main__":
    main()
