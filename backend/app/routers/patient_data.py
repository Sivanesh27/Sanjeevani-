"""
Patient-data endpoints, built once and mounted twice:
  /api/patient/...              owner = the signed-in patient (id comes from the session, never from the client)
  /api/admin/patients/{uid}/... owner = chosen patient, doctor only, every call written to the audit log
"""
import io, json
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from ..config import get_settings
from ..data.lexicons import CONDITIONS
from ..db import get_db
from ..deps import Owner
from ..models import (User, PatientProfile, FaceCredential, Medication, Condition, Allergy, Document, AnalysisRun)
from ..schemas import (ProfileIn, FaceIn, MedIn, MedPatch, CondIn, CondPatch, AllergyIn, AllergyPatch, TextDocIn, ApplyIn)
from ..services import engine, ner, face as facesvc
from ..services.kb import get_kb, norm

settings = get_settings()
PROFILE_FIELDS = list(ProfileIn.model_fields)
KEY_FIELDS = ["full_name", "dob", "sex", "height_cm", "weight_kg", "phone", "city", "country", "blood_group", "smoker", "alcohol", "diet_preference", "emergency_contact_phone"]
ALLOWED_EXT = (".txt", ".md", ".csv", ".json", ".pdf")


def guess_condition_key(name: str) -> str | None:
    n = norm(name)
    for k, v in CONDITIONS.items():
        if n == norm(v["label"]) or n in v["terms"]:
            return k
    return None


def profile_dict(p: PatientProfile | None) -> dict:
    return {f: getattr(p, f, None) for f in PROFILE_FIELDS} if p else {}


def profile_out(p: PatientProfile | None) -> dict:
    d = profile_dict(p)
    d["age"] = engine.age_from(d.get("dob"))
    d["bmi"] = round(d["weight_kg"] / ((d["height_cm"] / 100) ** 2), 1) if d.get("weight_kg") and d.get("height_cm") else None
    d["completeness"] = round(100 * sum(1 for k in KEY_FIELDS if d.get(k)) / len(KEY_FIELDS))
    return d


def med_out(m: Medication):
    return {"id": m.id, "name": m.name, "normalized_name": m.normalized_name, "in_kb": bool(m.normalized_name), "dose": m.dose, "frequency": m.frequency, "route": m.route,
            "start_date": m.start_date, "end_date": m.end_date, "status": m.status, "source": m.source, "created_at": m.created_at}


def cond_out(c: Condition):
    return {"id": c.id, "name": c.name, "condition_key": c.condition_key, "status": c.status, "since": c.since, "source": c.source}


def allergy_out(a: Allergy):
    return {"id": a.id, "allergen": a.allergen, "reaction": a.reaction, "severity": a.severity, "source": a.source}


def get_or_create_profile(db: Session, uid) -> PatientProfile:
    p = db.scalar(select(PatientProfile).where(PatientProfile.user_id == uid))
    if not p:
        p = PatientProfile(user_id=uid); db.add(p); db.flush()
    return p


def load_context(db: Session, uid):
    p = db.scalar(select(PatientProfile).where(PatientProfile.user_id == uid))
    prof = profile_dict(p); prof["age"] = engine.age_from(prof.get("dob"))
    meds = [{"name": m.name, "dose": m.dose, "frequency": m.frequency, "status": m.status} for m in db.scalars(select(Medication).where(Medication.user_id == uid))]
    conds = [{"name": c.name, "condition_key": c.condition_key or guess_condition_key(c.name), "status": c.status} for c in db.scalars(select(Condition).where(Condition.user_id == uid))]
    alls = [{"allergen": a.allergen, "reaction": a.reaction} for a in db.scalars(select(Allergy).where(Allergy.user_id == uid))]
    return prof, meds, conds, alls


def extract_text(file: UploadFile) -> str:
    name = (file.filename or "").lower()
    if not name.endswith(ALLOWED_EXT):
        raise HTTPException(415, "Supported files: PDF (text-based), TXT, CSV, JSON, MD. For photos or scans, type or paste the text instead.")
    data = file.file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File is larger than {settings.max_upload_mb} MB.")
    if name.endswith(".pdf"):
        if not data.startswith(b"%PDF"):
            raise HTTPException(415, "That file is not a valid PDF.")
        try:
            from pypdf import PdfReader
            r = PdfReader(io.BytesIO(data))
            if r.is_encrypted: raise HTTPException(422, "This PDF is password-protected.")
            text = "\n".join((pg.extract_text() or "") for pg in r.pages[:30])
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(422, "Could not read this PDF.")
        if len(text.strip()) < 10:
            raise HTTPException(422, "No text found - this looks like a scanned image. Please paste the text instead (OCR is not enabled).")
        return text
    return data.decode("utf-8", errors="replace")


def build(owner_dep) -> APIRouter:
    r = APIRouter()

    # ----------------------------------------------------------- profile / summary
    @r.get("/profile")
    def get_profile(o: Owner = Depends(owner_dep), db: Session = Depends(get_db)):
        return profile_out(db.scalar(select(PatientProfile).where(PatientProfile.user_id == o.id)))

    @r.put("/profile")
    def put_profile(body: ProfileIn, o: Owner = Depends(owner_dep), db: Session = Depends(get_db)):
        p = get_or_create_profile(db, o.id)
        for k, v in body.model_dump(exclude_unset=True).items():
            setattr(p, k, v)
        if body.full_name:
            db.get(User, o.id).display_name = body.full_name
        db.commit()
        return profile_out(p)

    @r.get("/summary")
    def summary(o: Owner = Depends(owner_dep), db: Session = Depends(get_db)):
        u = db.get(User, o.id)
        p = db.scalar(select(PatientProfile).where(PatientProfile.user_id == o.id))
        cnt = lambda m: db.scalar(select(func.count()).select_from(m).where(m.user_id == o.id))
        last = db.scalar(select(AnalysisRun).where(AnalysisRun.user_id == o.id).order_by(AnalysisRun.created_at.desc()).limit(1))
        face = db.scalar(select(FaceCredential).where(FaceCredential.user_id == o.id))
        return {"user": {"id": str(u.id), "email": u.email, "display_name": u.display_name, "is_active": u.is_active, "email_verified": u.email_verified, "face_2fa": u.face_2fa,
                         "created_at": u.created_at, "last_login_at": u.last_login_at},
                "profile": profile_out(p), "face_enrolled": bool(face),
                "counts": {"medications": cnt(Medication), "conditions": cnt(Condition), "allergies": cnt(Allergy), "documents": cnt(Document), "analyses": cnt(AnalysisRun)},
                "latest_analysis": {"id": last.id, "created_at": last.created_at, "score": last.score, "level": last.level} if last else None}

    # ----------------------------------------------------------- meds / conditions / allergies
    COLL = {"medications": (Medication, MedIn, MedPatch, med_out), "conditions": (Condition, CondIn, CondPatch, cond_out), "allergies": (Allergy, AllergyIn, AllergyPatch, allergy_out)}

    def prepare(key, data: dict):
        if key == "medications" and data.get("name"):
            d = get_kb().resolve(data["name"])
            data["normalized_name"] = d["name"] if d else None
        if key == "conditions" and "condition_key" in data or (key == "conditions" and data.get("name")):
            if not data.get("condition_key") and data.get("name"):
                data["condition_key"] = guess_condition_key(data["name"])
        return data

    for key, (Model, In, Patch, out) in COLL.items():
        def _list(o: Owner = Depends(owner_dep), db: Session = Depends(get_db), Model=Model, out=out):
            return [out(x) for x in db.scalars(select(Model).where(Model.user_id == o.id).order_by(Model.created_at))]

        def _create(body: In, o: Owner = Depends(owner_dep), db: Session = Depends(get_db), Model=Model, out=out, key=key):
            if db.scalar(select(func.count()).select_from(Model).where(Model.user_id == o.id)) >= 200:
                raise HTTPException(422, "Limit of 200 records reached.")
            row = Model(user_id=o.id, **prepare(key, body.model_dump()))
            db.add(row); db.commit()
            return out(row)

        def _update(item_id: str, body: Patch, o: Owner = Depends(owner_dep), db: Session = Depends(get_db), Model=Model, out=out, key=key):
            row = db.get(Model, _uuid(item_id))
            if not row or row.user_id != o.id:
                raise HTTPException(404, "Not found")
            for k, v in prepare(key, body.model_dump(exclude_unset=True)).items():
                setattr(row, k, v)
            db.commit()
            return out(row)

        def _delete(item_id: str, o: Owner = Depends(owner_dep), db: Session = Depends(get_db), Model=Model):
            row = db.get(Model, _uuid(item_id))
            if not row or row.user_id != o.id:
                raise HTTPException(404, "Not found")
            db.delete(row); db.commit()
            return {"ok": True}

        r.add_api_route(f"/{key}", _list, methods=["GET"], name=f"list_{key}")
        r.add_api_route(f"/{key}", _create, methods=["POST"], name=f"create_{key}", status_code=201)
        r.add_api_route(f"/{key}/{{item_id}}", _update, methods=["PUT"], name=f"update_{key}")
        r.add_api_route(f"/{key}/{{item_id}}", _delete, methods=["DELETE"], name=f"delete_{key}")

    # ----------------------------------------------------------- reports (NER)
    def _store_doc(db, o, text, filename, ctype):
        res = ner.extract(text, get_kb(db))
        doc = Document(user_id=o.id, filename=filename, content_type=ctype, text=text, entities=jsonable_encoder(res), status="pending")
        db.add(doc); db.commit()
        return {"id": doc.id, "filename": filename, "text": text, **res}

    @r.post("/documents/text")
    def doc_text(body: TextDocIn, o: Owner = Depends(owner_dep), db: Session = Depends(get_db)):
        return _store_doc(db, o, body.text, body.filename or "pasted-text", "text/plain")

    @r.post("/documents/upload")
    def doc_upload(file: UploadFile = File(...), o: Owner = Depends(owner_dep), db: Session = Depends(get_db)):
        text = extract_text(file)
        return _store_doc(db, o, text, (file.filename or "upload")[:200], file.content_type)

    @r.get("/documents")
    def docs(o: Owner = Depends(owner_dep), db: Session = Depends(get_db)):
        return [{"id": d.id, "filename": d.filename, "status": d.status, "created_at": d.created_at,
                 "n_entities": len((d.entities or {}).get("entities", []))} for d in db.scalars(select(Document).where(Document.user_id == o.id).order_by(Document.created_at.desc()))]

    @r.get("/documents/{doc_id}")
    def doc_get(doc_id: str, o: Owner = Depends(owner_dep), db: Session = Depends(get_db)):
        d = db.get(Document, _uuid(doc_id))
        if not d or d.user_id != o.id: raise HTTPException(404, "Not found")
        return {"id": d.id, "filename": d.filename, "text": d.text, "status": d.status, **(d.entities or {})}

    @r.post("/documents/{doc_id}/apply")
    def doc_apply(doc_id: str, body: ApplyIn, o: Owner = Depends(owner_dep), db: Session = Depends(get_db)):
        d = db.get(Document, _uuid(doc_id))
        if not d or d.user_id != o.id: raise HTTPException(404, "Not found")
        kb = get_kb(db)
        have_m = {norm(m.normalized_name or m.name) for m in db.scalars(select(Medication).where(Medication.user_id == o.id))}
        have_c = {norm(c.name) for c in db.scalars(select(Condition).where(Condition.user_id == o.id))}
        have_a = {norm(a.allergen) for a in db.scalars(select(Allergy).where(Allergy.user_id == o.id))}
        added = {"medications": 0, "conditions": 0, "allergies": 0, "profile_fields": 0}
        for m in body.medications:
            rec = kb.resolve(m.name); k = norm(rec["name"] if rec else m.name)
            if k in have_m: continue
            have_m.add(k); added["medications"] += 1
            db.add(Medication(user_id=o.id, normalized_name=rec["name"] if rec else None, source="report", **m.model_dump()))
        for c in body.conditions:
            if norm(c.name) in have_c: continue
            have_c.add(norm(c.name)); added["conditions"] += 1
            data = c.model_dump(); data["condition_key"] = data.get("condition_key") or guess_condition_key(c.name)
            db.add(Condition(user_id=o.id, source="report", **data))
        for a in body.allergies:
            if norm(a.allergen) in have_a: continue
            have_a.add(norm(a.allergen)); added["allergies"] += 1
            db.add(Allergy(user_id=o.id, source="report", **a.model_dump()))
        if body.profile:
            p = get_or_create_profile(db, o.id)
            for k, v in body.profile.model_dump(exclude_unset=True, exclude_none=True).items():
                setattr(p, k, v); added["profile_fields"] += 1
        d.status = "applied"; db.commit()
        return {"ok": True, "added": added}

    @r.delete("/documents/{doc_id}")
    def doc_delete(doc_id: str, o: Owner = Depends(owner_dep), db: Session = Depends(get_db)):
        d = db.get(Document, _uuid(doc_id))
        if not d or d.user_id != o.id: raise HTTPException(404, "Not found")
        db.delete(d); db.commit()
        return {"ok": True}

    # ----------------------------------------------------------- analysis
    @r.post("/analysis/run")
    def run(o: Owner = Depends(owner_dep), db: Session = Depends(get_db)):
        prof, meds, conds, alls = load_context(db, o.id)
        if not [m for m in meds if m["status"] == "active"]:
            raise HTTPException(422, "Add at least one active medicine first.")
        result = jsonable_encoder(engine.analyze(get_kb(db), prof, meds, conds, alls))
        snap = jsonable_encoder({"profile": {k: v for k, v in prof.items() if k not in ("phone", "address", "notes", "full_name", "emergency_contact_name", "emergency_contact_phone")},
                                 "medications": meds, "conditions": conds, "allergies": alls})
        run_ = AnalysisRun(user_id=o.id, requested_by=o.actor.id, score=result["overall"]["score"], level=result["overall"]["level"], result=result, snapshot=snap)
        db.add(run_); db.commit()
        return {"id": run_.id, "created_at": run_.created_at, **result}

    @r.get("/analysis")
    def runs(o: Owner = Depends(owner_dep), db: Session = Depends(get_db)):
        return [{"id": x.id, "created_at": x.created_at, "score": x.score, "level": x.level,
                 "n_interactions": len(x.result.get("interactions", [])), "n_medicines": x.result["overall"].get("n_medicines")}
                for x in db.scalars(select(AnalysisRun).where(AnalysisRun.user_id == o.id).order_by(AnalysisRun.created_at.desc()).limit(50))]

    @r.get("/analysis/{run_id}")
    def run_get(run_id: str, o: Owner = Depends(owner_dep), db: Session = Depends(get_db)):
        x = db.get(AnalysisRun, _uuid(run_id))
        if not x or x.user_id != o.id: raise HTTPException(404, "Not found")
        return {"id": x.id, "created_at": x.created_at, **x.result}

    # ----------------------------------------------------------- face
    @r.get("/face")
    def face_get(o: Owner = Depends(owner_dep), db: Session = Depends(get_db)):
        f = db.scalar(select(FaceCredential).where(FaceCredential.user_id == o.id))
        return {"enrolled": bool(f), "photo": f.photo if f else None, "enrolled_at": f.enrolled_at if f else None, "last_verified_at": f.last_verified_at if f else None}

    @r.put("/face")
    def face_put(body: FaceIn, o: Owner = Depends(owner_dep), db: Session = Depends(get_db)):
        descs = facesvc.validate_descriptors(body.descriptors); photo = facesvc.validate_photo(body.photo)
        f = db.scalar(select(FaceCredential).where(FaceCredential.user_id == o.id))
        if f: f.descriptors, f.photo = descs, photo or f.photo
        else: db.add(FaceCredential(user_id=o.id, descriptors=descs, photo=photo))
        db.commit()
        return {"enrolled": True}

    @r.delete("/face")
    def face_delete(o: Owner = Depends(owner_dep), db: Session = Depends(get_db)):
        f = db.scalar(select(FaceCredential).where(FaceCredential.user_id == o.id))
        if f: db.delete(f)
        db.get(User, o.id).face_2fa = False
        db.commit()
        return {"ok": True}

    # ----------------------------------------------------------- export (portability)
    @r.get("/export")
    def export(o: Owner = Depends(owner_dep), db: Session = Depends(get_db)):
        u = db.get(User, o.id)
        prof, meds, conds, alls = load_context(db, o.id)
        return jsonable_encoder({"exported_at": date.today(), "account": {"email": u.email, "created_at": u.created_at},
                                 "profile": profile_dict(db.scalar(select(PatientProfile).where(PatientProfile.user_id == o.id))),
                                 "medications": [med_out(m) for m in db.scalars(select(Medication).where(Medication.user_id == o.id))],
                                 "conditions": [cond_out(c) for c in db.scalars(select(Condition).where(Condition.user_id == o.id))],
                                 "allergies": [allergy_out(a) for a in db.scalars(select(Allergy).where(Allergy.user_id == o.id))],
                                 "analyses": [{"id": x.id, "created_at": x.created_at, "result": x.result} for x in db.scalars(select(AnalysisRun).where(AnalysisRun.user_id == o.id))]})
    return r


def _uuid(s: str):
    import uuid
    try:
        return uuid.UUID(s)
    except ValueError:
        raise HTTPException(404, "Not found")
