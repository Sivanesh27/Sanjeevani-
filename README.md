# Sanjeevani AI

Personalised drug–drug interaction checking, medical-report NER and diet guidance, with patient and doctor portals.
**React + Tailwind** (Vercel) · **FastAPI** (Render) · **PostgreSQL** (Neon) · **Brevo** e-mail · **UptimeRobot** keep-alive.

> **Decision-support prototype - not a certified medical device.** It has not been clinically validated. Never use it as the sole basis for a medical decision. See [Limitations](#honest-limitations).

## What it does

| Area | Features |
|---|---|
| **Patients** | Register with e-mail + password + **live face capture** (liveness: blink / head-turn). Sign in with password, **face**, or both (face as second factor). Edit all demographics, lifestyle, labs, vitals, medicines, conditions, allergies. Upload/paste a report → **NER** extracts medicines, conditions, allergies and lab values → review → save. Run a **personalised interaction analysis** (risk score, why, alerts, monitoring, diet plan, questions for the doctor). Export all data, delete the account. |
| **Doctors (admin)** | Login only - **no admin registration exists**; accounts come from server env vars. See every patient, edit any record, view the face photo, run analyses, disable/reset/delete accounts, **edit every database table** (add / update / delete / swap), edit the interaction knowledge base live, read the immutable **audit log**. Optional e-mail OTP. |
| **Everyone** | Responsive for desktop, Android and iOS browsers (bottom tab bar on phones, safe-area aware, installable as a PWA), light/dark theme, print-to-PDF reports. |

## Architecture

```
Browser ──https──▶ Vercel (React SPA, /models face weights)
                      │  /api/*  (Vercel rewrite → same-origin, first-party cookies; works on iOS Safari)
                      ▼
                 Render: FastAPI ──▶ Neon PostgreSQL
                      │  └─ Brevo (verification / reset / OTP e-mails)
                 UptimeRobot pings /api/health every 5 min
```
```
backend/app   main.py · config.py · db.py · models.py · security.py · deps.py · schemas.py
              routers/ auth.py · patient_data.py (mounted for patient AND doctor) · admin.py
              services/ kb.py · engine.py · ner.py · face.py · emailer.py · seed.py
              data/ kb_drugs.json · kb_interactions.json · synonyms.json · lexicons.py
              ml_artifacts/ model.json · meta.json · metrics.json     ← the trained model
backend/tests          20 end-to-end tests        backend/scripts  generate_secrets.py · import_kb.py
frontend/src           pages/ components/ lib/    frontend/vercel.json   rewrites + headers
ml/                    kb_source.py · train.py · kaggle_ingest.py        docs/  figures, screenshots, metrics
```

## Methods (what is actually inside)

### 1. Knowledge base - the source of truth
75 drug/food classes, 209 drugs/foods, **138 authored class-level rules** expanded to **1,391 drug-pair records** (mechanism, severity, clinical effect, management, diet advice), plus **~200 brand/generic synonyms including Indian brands** (Dolo, Ecosprin, Glycomet, Telma…). Stored in PostgreSQL and **editable by doctors at runtime**. Built by `ml/kb_source.py` from established clinical pharmacology; it is *not* scraped from DrugBank/Micromedex.

### 2. Machine learning (fallback only)
For drug pairs with no curated rule, an **XGBoost** classifier predicts severity (None/Minor/Moderate/Major) from 112 features: shared / union **mechanism tags** (CYP inhibition, QT risk, serotonergic, bleeding, hyperkalaemia…) + class pair. Evaluated honestly:

| Model | Random split acc. | 5-fold CV | **Leave-class-pair-out acc.** (unseen drug classes) |
|---|---|---|---|
| Random Forest | 97.4 % | 97.8 % | 53.1 % |
| **XGBoost (served)** | **97.9 %** | 97.6 % | **54.7 %** (F1 0.51) |
| Logistic Regression | 81.8 % | 83.9 % | 59.3 % |

Macro ROC-AUC 0.999 on the random split. **Read this carefully:** labels come from the same rules that generate the data, so random-split scores are inflated; the leave-class-pair-out column is the realistic generalisation estimate and it is only slightly better than guessing. Therefore ML predictions are shown to users only when confidence ≥ 0.75 and severity ≥ Moderate, are labelled **“unverified estimate”**, are capped at *Moderate*, and never count towards the headline risk. Figures: `docs/figures/`.

### 3. Personalisation engine (`services/engine.py`)
Transparent, rule-based, explainable - **not** trained on patient outcomes. Base severity (Minor 18 / Moderate 42 / Major 62) + points for: age, **CKD-EPI 2021 eGFR** (estimated from creatinine if not entered), liver enzymes, pregnancy, 17 conditions, K⁺ / INR / HbA1c / heart-rate / BP, alcohol, smoking (CYP1A2), polypharmacy → 0-100 → Low/Moderate/High/Critical. Every point is listed to the user (“+15 Kidney function (eGFR 37)”). Also: **42 drug-condition precautions** (e.g. NSAID + CKD, ACEi + pregnancy, metformin + eGFR<30), **drug-allergy cross-reaction alerts**, a **monitoring plan**, and a **personalised diet plan** (foods to avoid / limit / keep consistent / timing / good choices, with Indian examples). Unknown medicines are reported as *not checked*, never silently ignored. “No interaction found” is never presented as “safe”.

### 4. Medical NER (`services/ner.py`)
Lexicon + rules, fully offline and deterministic: regex over KB names and synonyms (longest match), **RapidFuzz** fuzzy matching for misspellings (only with a dose cue), unknown-drug detection (“Telma 40 mg”), dose / frequency (OD, BD, TDS, 1-0-1, SOS…) / route parsing, **NegEx-style negation**, stopped-medicine detection, **family-history filtering**, section awareness (Allergies / Medications…), **lab & vital extraction** with unit conversion and plausibility limits. On a 10-snippet hand-written set: precision 1.00, recall 0.94 (`tests/test_ner_engine.py`) - a smoke test, **not a benchmark**. It is not a trained neural NER; scanned images/photos are not supported (no OCR). A hook (`recognizers=`) lets you plug in a trained spaCy/transformer model.

### 5. Face verification
Runs **in the browser** with face-api.js (TinyFaceDetector + 68-point landmarks + 128-d recognition net; weights served from your own domain). Flow: align → descriptor #1 → **random liveness challenge** (blink via eye-aspect-ratio, or head turn via landmark yaw) → descriptor #2 → consistency check. The server stores only encrypted descriptors + one small JPEG, compares with Euclidean distance (threshold 0.5), uses a signed one-time-ish **nonce**, rate limits and account lockout. Face sign-in works on desktop webcams too, and is recommended as a **second factor** (Settings → “Require face check”).

## Security design
Argon2id passwords · opaque **server-side sessions** (SHA-256-hashed token in an `HttpOnly; Secure; SameSite=Lax` cookie; idle + absolute expiry; doctor 30 min idle) · **CSRF token** on every write + Origin check · lockout after 5 failures · rate limits · generic errors (no account enumeration on reset) · strict pydantic schemas (`extra=forbid`, anti mass-assignment) · **Fernet field encryption** for phone, address, emergency contact, notes, report text, face data · **patient data isolation**: every patient endpoint takes the owner from the session, never from the client, enforced by tests; optional **PostgreSQL row-level security** as defence in depth (verified: with no identity the app role sees 0 rows) · immutable **audit log** for every doctor access/change · security headers · `no-store` on API responses · right to export and erase.

## Run locally
```bash
# 1) PostgreSQL (or skip: SQLite is used when DATABASE_URL is not set)
# 2) backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # set ADMIN_EMAIL / ADMIN_PASSWORD; secrets optional in development
uvicorn app.main:app --reload --port 8000        # API docs: http://localhost:8000/api/docs
# 3) frontend (new terminal)
cd frontend && npm install && npm run dev        # http://localhost:5173  (proxies /api to :8000)
```
Camera access needs HTTPS or `localhost`. To test on a phone, use an HTTPS tunnel (e.g. `cloudflared`/`ngrok`) or deploy to Vercel.

```bash
cd backend && pytest -q          # 20 tests (SQLite by default)
DATABASE_URL=postgresql://... ENABLE_RLS=true pytest -q    # against Postgres with RLS
```

## Retrain / extend the data
```bash
python ml/kb_source.py            # rebuild KB + training CSV  → ml/out/ and copy kb_*.json into backend/app/data/
python ml/train.py                # retrain, rewrite backend/app/ml_artifacts + docs/figures
python ml/kaggle_ingest.py FILE.csv [--a COL --b COL --severity-col Level]   # merge Kaggle/DDInter/DrugBank-style CSVs
cd backend && python scripts/import_kb.py
```
**About Kaggle:** the build environment had no access to Kaggle, so **no Kaggle dataset was used to train the shipped model** - it is trained on the curated KB above. `ml/kaggle_ingest.py` is provided (tested only on small synthetic files) to merge any DDI CSV with drug-A / drug-B / severity-or-description columns (DDInter exports map directly). Imported pairs extend the curated lookup; they carry no mechanism tags, so they do not train the ML fallback. Check each dataset’s licence before use.

## Honest limitations
- **Not clinically validated, not a regulated device** (CDSCO/FDA/CE). Needs pharmacist/physician review before any real-world use.
- Coverage is broad but finite: 209 drugs/foods. It cannot cover “every drug and disease”; unknown drugs are flagged as not checked. Growing it means adding rows (Data Explorer) or importing licensed data.
- Rule-based severity is class-level and **dose-agnostic**; ML fallback is weak on unseen drug classes (see table).
- NER is lexicon/rule-based; no OCR for scans/photos.
- Face recognition runs client-side: a determined attacker with a modified client or a high-quality video replay could attempt to fool it. It is **not** certified biometric presentation-attack detection - use it as a second factor, not the only protection, for sensitive accounts.
- Biometric + health data is highly sensitive: obtain proper consent, a privacy policy, and review DPDP Act (India) / GDPR / HIPAA duties before real patients use it.
- Schema is created with `create_all`; adopt Alembic migrations before changing tables in production.
