import json, uuid
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select, func, or_, String, Text, Integer, Float, Boolean, Date, DateTime, Uuid, JSON, delete
from sqlalchemy.orm import Session
from ..db import get_db
from ..deps import AuthCtx, require_admin, owner_admin, Owner, audit
from ..models import (User, UserSession, AuthToken, PatientProfile, FaceCredential, Medication, Condition, Allergy, Document, AnalysisRun,
                      AuditLog, KBDrug, KBInteraction, EncStr, EncJSON, utcnow)
from ..schemas import AdminAccountIn, SetPasswordIn
from ..security import hash_password, check_password_strength
from ..services import kb as kbsvc
from .auth import purge_user_data
from .patient_data import build, profile_out

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])
router.include_router(build(owner_admin), prefix="/patients/{uid}")

# ----------------------------------------------------------------------------- patients
@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    now = utcnow()
    patients = db.scalar(select(func.count()).select_from(User).where(User.role == "patient"))
    week = db.scalar(select(func.count()).select_from(User).where(User.role == "patient", User.created_at >= now - timedelta(days=7)))
    latest = {}
    for uid, level, ts in db.execute(select(AnalysisRun.user_id, AnalysisRun.level, AnalysisRun.created_at).order_by(AnalysisRun.created_at.desc()).limit(5000)):
        latest.setdefault(uid, level)
    dist = {k: 0 for k in ("Critical", "High", "Moderate", "Low", "None")}
    for lv in latest.values(): dist[lv] = dist.get(lv, 0) + 1
    c = lambda m: db.scalar(select(func.count()).select_from(m))
    return {"patients": patients, "new_this_week": week, "active_patients": db.scalar(select(func.count()).select_from(User).where(User.role == "patient", User.is_active.is_(True))),
            "face_enrolled": c(FaceCredential), "medications": c(Medication), "analyses": c(AnalysisRun), "risk_distribution": dist,
            "never_analysed": max(0, patients - len(latest)), "kb_drugs": c(KBDrug), "kb_interactions": c(KBInteraction)}


@router.get("/patients")
def patients(q: str = "", risk: str = "", page: int = 1, page_size: int = 20, db: Session = Depends(get_db)):
    page_size = max(1, min(page_size, 100)); page = max(1, page)
    stmt = select(User, PatientProfile).join(PatientProfile, PatientProfile.user_id == User.id, isouter=True).where(User.role == "patient")
    if q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(User.email).like(like), func.lower(User.display_name).like(like)))
    rows = db.execute(stmt.order_by(User.created_at.desc())).all()
    out = []
    for u, p in rows:
        last = db.scalar(select(AnalysisRun).where(AnalysisRun.user_id == u.id).order_by(AnalysisRun.created_at.desc()).limit(1))
        lvl = last.level if last else None
        if risk and (lvl or "Never") != risk: continue
        out.append({"id": str(u.id), "email": u.email, "name": u.display_name, "is_active": u.is_active, "age": profile_out(p)["age"] if p else None, "sex": p.sex if p else None,
                    "city": p.city if p else None, "created_at": u.created_at, "last_login_at": u.last_login_at,
                    "medications": db.scalar(select(func.count()).select_from(Medication).where(Medication.user_id == u.id)),
                    "risk_level": lvl, "risk_score": last.score if last else None, "last_analysis_at": last.created_at if last else None})
    total = len(out)
    return {"total": total, "page": page, "page_size": page_size, "items": out[(page - 1) * page_size: page * page_size]}


@router.patch("/patients/{uid}/account")
def account(body: AdminAccountIn, o: Owner = Depends(owner_admin), db: Session = Depends(get_db)):
    u = db.get(User, o.id)
    for k, v in body.model_dump(exclude_unset=True).items(): setattr(u, k, v)
    if body.is_active is False:
        for s in db.scalars(select(UserSession).where(UserSession.user_id == u.id)): s.revoked = True
    db.commit()
    return {"ok": True}


@router.post("/patients/{uid}/set-password")
def set_password(body: SetPasswordIn, o: Owner = Depends(owner_admin), db: Session = Depends(get_db)):
    u = db.get(User, o.id); check_password_strength(body.password, u.email)
    u.password_hash = hash_password(body.password); u.failed_attempts = 0; u.locked_until = None
    for s in db.scalars(select(UserSession).where(UserSession.user_id == u.id)): s.revoked = True
    db.commit()
    return {"ok": True}


@router.post("/patients/{uid}/revoke-sessions")
def revoke(o: Owner = Depends(owner_admin), db: Session = Depends(get_db)):
    for s in db.scalars(select(UserSession).where(UserSession.user_id == o.id)): s.revoked = True
    db.commit()
    return {"ok": True}


@router.delete("/patients/{uid}")
def delete_patient(o: Owner = Depends(owner_admin), db: Session = Depends(get_db)):
    purge_user_data(db, o.id); db.execute(delete(User).where(User.id == o.id)); db.commit()
    return {"ok": True}


# ----------------------------------------------------------------------------- audit / model
@router.get("/audit")
def audit_log(page: int = 1, page_size: int = 50, target: str = "", actor: str = "", action: str = "", db: Session = Depends(get_db)):
    stmt = select(AuditLog)
    if target: stmt = stmt.where(AuditLog.target_user_id == _uuid(target))
    if actor: stmt = stmt.where(func.lower(AuditLog.actor_email).like(f"%{actor.lower()}%"))
    if action: stmt = stmt.where(AuditLog.action.like(f"%{action}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(AuditLog.created_at.desc()).offset((max(page, 1) - 1) * page_size).limit(min(page_size, 200))).all()
    return {"total": total, "items": [{c.name: getattr(r, c.name) for c in AuditLog.__table__.columns} for r in rows]}


@router.get("/model")
def model_info():
    k = kbsvc.get_kb()
    return {"available": bool(k.ml), "meta": k.ml.meta if k.ml else None, "metrics": k.ml.metrics if k.ml else None}


@router.post("/kb/reload")
def kb_reload(ctx: AuthCtx = Depends(require_admin)):
    kbsvc.invalidate(); k = kbsvc.get_kb()
    return {"drugs": len(k.drugs), "pairs": len(k.pairs)}


# ----------------------------------------------------------------------------- generic data explorer
ENUMS = {"role": ["patient", "admin"], "sex": ["male", "female", "other"], "smoker": ["never", "former", "current"], "alcohol": ["none", "occasional", "moderate", "heavy"],
         "status": ["active", "stopped", "resolved", "pending", "applied"], "severity": ["Minor", "Moderate", "Major", "mild", "moderate", "severe"], "kind": ["drug", "food"],
         "level": ["None", "Low", "Moderate", "High", "Critical"], "source": ["manual", "report"]}
TABLES = {
    "users": dict(model=User, hidden={"password_hash"}, readonly={"id", "role", "created_at", "updated_at", "failed_attempts"}, create=False, delete=True),
    "patient_profiles": dict(model=PatientProfile, hidden=set(), readonly={"id", "created_at", "updated_at"}, create=True, delete=True),
    "medications": dict(model=Medication, hidden=set(), readonly={"id", "created_at"}, create=True, delete=True),
    "conditions": dict(model=Condition, hidden=set(), readonly={"id", "created_at"}, create=True, delete=True),
    "allergies": dict(model=Allergy, hidden=set(), readonly={"id", "created_at"}, create=True, delete=True),
    "documents": dict(model=Document, hidden=set(), readonly={"id", "created_at"}, create=False, delete=True),
    "analysis_runs": dict(model=AnalysisRun, hidden=set(), readonly={"id", "created_at", "result", "snapshot", "requested_by"}, create=False, delete=True),
    "face_credentials": dict(model=FaceCredential, hidden={"descriptors"}, readonly={"id", "enrolled_at", "updated_at", "last_verified_at", "photo", "user_id"}, create=False, delete=True),
    "sessions": dict(model=UserSession, hidden={"token_hash", "csrf_token"}, readonly={"id", "user_id", "created_at", "last_seen_at", "ip", "user_agent", "expires_at"}, create=False, delete=True),
    "auth_tokens": dict(model=AuthToken, hidden={"token_hash", "code_hash"}, readonly={"id", "user_id", "purpose", "created_at", "attempts", "expires_at", "used_at"}, create=False, delete=True),
    "audit_logs": dict(model=AuditLog, hidden=set(), readonly={c.name for c in AuditLog.__table__.columns}, create=False, delete=False),   # immutable evidence
    "kb_drugs": dict(model=KBDrug, hidden=set(), readonly={"id"}, create=True, delete=True),
    "kb_interactions": dict(model=KBInteraction, hidden=set(), readonly={"id"}, create=True, delete=True),
}


def _uuid(s):
    try: return uuid.UUID(str(s))
    except ValueError: raise HTTPException(404, "Not found")


def _kind(col):
    t = col.type
    if isinstance(t, EncJSON) or isinstance(t, JSON): return "json"
    if isinstance(t, EncStr): return "text"
    if isinstance(t, Uuid): return "uuid"
    if isinstance(t, Boolean): return "bool"
    if isinstance(t, Integer): return "int"
    if isinstance(t, Float): return "float"
    if isinstance(t, DateTime): return "datetime"
    if isinstance(t, Date): return "date"
    if isinstance(t, Text): return "text"
    return "string"


def _cfg(name):
    if name not in TABLES: raise HTTPException(404, "Unknown table")
    return TABLES[name]


def _cols(cfg):
    out = []
    for c in cfg["model"].__table__.columns:
        if c.name in cfg["hidden"]: continue
        out.append({"name": c.name, "kind": _kind(c), "nullable": c.nullable, "pk": c.primary_key, "editable": not c.primary_key and c.name not in cfg["readonly"],
                    "enum": ENUMS.get(c.name) if c.name in ENUMS else None, "fk": bool(c.foreign_keys), "max": getattr(c.type, "length", None)})
    return out


def _coerce(col, v):
    kind = _kind(col)
    if v is None or (isinstance(v, str) and v.strip() == "" and kind not in ("string", "text")):
        if not col.nullable and col.default is None and col.server_default is None: raise HTTPException(422, f"'{col.name}' is required")
        return None
    try:
        if kind == "uuid": return uuid.UUID(str(v))
        if kind == "bool": return v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes", "on")
        if kind == "int": return int(v)
        if kind == "float": return float(v)
        if kind == "date": return date.fromisoformat(str(v)[:10])
        if kind == "datetime": return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        if kind == "json": return v if isinstance(v, (dict, list)) else json.loads(v)
    except (ValueError, TypeError) as e:
        raise HTTPException(422, f"Invalid value for '{col.name}': {e}")
    v = str(v)
    ln = getattr(col.type, "length", None)
    if ln and len(v) > ln: raise HTTPException(422, f"'{col.name}' is longer than {ln} characters")
    return v


def _pk_value(cfg, s):
    pkcol = next(c for c in cfg["model"].__table__.columns if c.primary_key)
    return _uuid(s) if _kind(pkcol) == "uuid" else int(s)


def _row(cfg, obj):
    return jsonable_encoder({c.name: getattr(obj, c.name) for c in cfg["model"].__table__.columns if c.name not in cfg["hidden"]})


def _target(obj):
    return getattr(obj, "user_id", None) or (obj.id if isinstance(obj, User) else None)


@router.get("/tables")
def tables(db: Session = Depends(get_db)):
    return [{"name": n, "count": db.scalar(select(func.count()).select_from(c["model"])), "create": c["create"], "delete": c["delete"], "columns": _cols(c)} for n, c in TABLES.items()]


@router.get("/tables/{name}")
def table_rows(name: str, request: Request, page: int = 1, page_size: int = 25, q: str = "", sort: str = "", order: str = "desc", db: Session = Depends(get_db), ctx: AuthCtx = Depends(require_admin)):
    cfg = _cfg(name); M = cfg["model"]; cols = {c.name: c for c in M.__table__.columns}
    stmt = select(M)
    for k, v in request.query_params.items():
        if k.startswith("f_") and k[2:] in cols and k[2:] not in cfg["hidden"]:
            stmt = stmt.where(cols[k[2:]] == _coerce(cols[k[2:]], v))
    if q.strip():
        like = f"%{q.strip().lower()}%"
        textcols = [c for c in M.__table__.columns if isinstance(c.type, (String, Text)) and not isinstance(c.type, (EncStr, EncJSON)) and c.name not in cfg["hidden"]]
        if textcols: stmt = stmt.where(or_(*[func.lower(c).like(like) for c in textcols]))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    if sort in cols and sort not in cfg["hidden"]:
        sc = cols[sort]
    else:
        sc = cols["created_at"] if "created_at" in cols else next(iter(M.__table__.primary_key.columns))
    stmt = stmt.order_by(sc.asc() if order == "asc" else sc.desc()).offset((max(page, 1) - 1) * page_size).limit(max(1, min(page_size, 200)))
    rows = [_row(cfg, r) for r in db.scalars(stmt)]
    if name in ("users", "patient_profiles", "face_credentials", "documents", "analysis_runs"):
        audit(ctx.user, f"explorer:list:{name}", table=name, ip=ctx.ip)
    return {"total": total, "page": page, "page_size": page_size, "columns": _cols(cfg), "items": rows}


@router.post("/tables/{name}", status_code=201)
def table_create(name: str, body: dict, db: Session = Depends(get_db), ctx: AuthCtx = Depends(require_admin)):
    cfg = _cfg(name)
    if not cfg["create"]: raise HTTPException(405, "Creating rows in this table is not allowed here")
    cols = {c.name: c for c in cfg["model"].__table__.columns}
    data = {}
    for k, v in body.items():
        if k not in cols or k in cfg["hidden"] or cols[k].primary_key or k in cfg["readonly"]: raise HTTPException(422, f"Field '{k}' cannot be set")
        data[k] = _coerce(cols[k], v)
    if "user_id" in cols and not data.get("user_id"): raise HTTPException(422, "'user_id' is required")
    if "user_id" in data and not db.get(User, data["user_id"]): raise HTTPException(404, "user_id does not exist")
    obj = cfg["model"](**data)
    _post_write(name, obj); db.add(obj); db.commit()
    audit(ctx.user, f"explorer:create:{name}", target=_target(obj), table=name, row_id=_pk(obj), ip=ctx.ip)
    if name.startswith("kb_"): kbsvc.invalidate()
    return _row(cfg, obj)


def _pk(obj):
    return getattr(obj, "id")


def _post_write(name, obj):
    if name == "medications" and obj.name:
        from ..services.kb import get_kb
        d = get_kb().resolve(obj.name); obj.normalized_name = d["name"] if d else None
    if name == "users": obj.email = obj.email.strip().lower()
    if name == "kb_drugs": obj.tags = obj.tags or []; obj.synonyms = obj.synonyms or []


@router.put("/tables/{name}/{pk}")
def table_update(name: str, pk: str, body: dict, db: Session = Depends(get_db), ctx: AuthCtx = Depends(require_admin)):
    cfg = _cfg(name); M = cfg["model"]; cols = {c.name: c for c in M.__table__.columns}
    obj = db.get(M, _pk_value(cfg, pk))
    if not obj: raise HTTPException(404, "Row not found")
    changes = {}
    for k, v in body.items():
        if k not in cols or k in cfg["hidden"] or cols[k].primary_key or k in cfg["readonly"]: raise HTTPException(422, f"Field '{k}' cannot be edited")
        nv = _coerce(cols[k], v)
        if getattr(obj, k) != nv: changes[k] = {"from": jsonable_encoder(getattr(obj, k)) if k not in ("notes", "phone", "address") else "[redacted]", "to": jsonable_encoder(nv) if k not in ("notes", "phone", "address") else "[redacted]"}
        setattr(obj, k, nv)
    if name == "users" and "email" in changes:
        obj.email = obj.email.strip().lower()
        if db.scalar(select(func.count()).select_from(User).where(User.email == obj.email, User.id != obj.id)): raise HTTPException(409, "Email already in use")
    _post_write(name, obj); db.commit()
    audit(ctx.user, f"explorer:update:{name}", target=_target(obj), table=name, row_id=pk, details={"changes": changes}, ip=ctx.ip)
    if name.startswith("kb_"): kbsvc.invalidate()
    return _row(cfg, obj)


@router.delete("/tables/{name}/{pk}")
def table_delete(name: str, pk: str, db: Session = Depends(get_db), ctx: AuthCtx = Depends(require_admin)):
    cfg = _cfg(name)
    if not cfg["delete"]: raise HTTPException(405, "Rows in this table are immutable")
    obj = db.get(cfg["model"], _pk_value(cfg, pk))
    if not obj: raise HTTPException(404, "Row not found")
    target = _target(obj)
    if name == "users":
        if obj.role == "admin": raise HTTPException(400, "Doctor accounts are managed in the server configuration.")
        purge_user_data(db, obj.id)
    db.delete(obj); db.commit()
    audit(ctx.user, f"explorer:delete:{name}", target=target, table=name, row_id=pk, ip=ctx.ip)
    if name.startswith("kb_"): kbsvc.invalidate()
    return {"ok": True}


@router.post("/tables/{name}/swap")
def table_swap(name: str, body: dict, db: Session = Depends(get_db), ctx: AuthCtx = Depends(require_admin)):
    """mode=rows: swap the values of `fields` between two rows.  mode=columns: swap two columns inside one row."""
    cfg = _cfg(name); M = cfg["model"]; cols = {c.name: c for c in M.__table__.columns}
    editable = lambda f: f in cols and f not in cfg["hidden"] and not cols[f].primary_key and f not in cfg["readonly"]
    if body.get("mode") == "columns":
        a, b = body.get("col_a"), body.get("col_b")
        if not (editable(a) and editable(b)) or _kind(cols[a]) != _kind(cols[b]): raise HTTPException(422, "Choose two editable columns of the same type")
        obj = db.get(M, _pk_value(cfg, str(body.get("id"))))
        if not obj: raise HTTPException(404, "Row not found")
        va, vb = getattr(obj, a), getattr(obj, b); setattr(obj, a, vb); setattr(obj, b, va)
        db.commit(); audit(ctx.user, f"explorer:swap-columns:{name}", target=_target(obj), table=name, row_id=body.get("id"), details={"cols": [a, b]}, ip=ctx.ip)
        res = [_row(cfg, obj)]
    else:
        fields = body.get("fields") or []
        if not fields or not all(editable(f) for f in fields): raise HTTPException(422, "Choose editable fields to swap")
        A, B = db.get(M, _pk_value(cfg, str(body.get("id_a")))), db.get(M, _pk_value(cfg, str(body.get("id_b"))))
        if not A or not B or A is B: raise HTTPException(404, "Two different existing rows are required")
        for f in fields:
            va, vb = getattr(A, f), getattr(B, f); setattr(A, f, vb); setattr(B, f, va)
        db.commit(); audit(ctx.user, f"explorer:swap-rows:{name}", table=name, row_id=f"{body.get('id_a')}<->{body.get('id_b')}", details={"fields": fields}, ip=ctx.ip)
        res = [_row(cfg, A), _row(cfg, B)]
    if name.startswith("kb_"): kbsvc.invalidate()
    return {"rows": res}
