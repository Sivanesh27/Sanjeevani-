import logging
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text, select
from .config import get_settings
from .db import Base, engine, SessionLocal, enable_rls, _is_pg
from . import models  # noqa: F401  (register tables)
from .data.lexicons import CONDITIONS
from .deps import auth
from .models import KBDrug
from .routers import auth as auth_router, patient_data, admin
from .services import kb as kbsvc, seed

settings = get_settings()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("sanjeevani")
SAFE = {"GET", "HEAD", "OPTIONS"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    if settings.enable_rls and _is_pg:
        with engine.begin() as conn:
            enable_rls(conn)
        log.info("Row-level security enabled on patient tables")
    with SessionLocal() as db:
        kbsvc.seed_kb(db)
        seed.seed_admins(db)
    kbsvc.get_kb()
    log.info("Sanjeevani AI ready (env=%s, rls=%s)", settings.env, settings.enable_rls)
    yield


app = FastAPI(title="Sanjeevani AI API", version="1.0.0", lifespan=lifespan, docs_url=None if settings.is_prod else "/api/docs", redoc_url=None,
              openapi_url=None if settings.is_prod else "/api/openapi.json")
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def guard(request: Request, call_next):
    if request.method not in SAFE:
        origin = request.headers.get("origin")
        if origin and origin.rstrip("/") not in settings.origins:
            return JSONResponse({"detail": "Origin not allowed"}, status_code=403)
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > 6 * 1024 * 1024:
            return JSONResponse({"detail": "Request too large"}, status_code=413)
    resp = await call_next(request)
    h = resp.headers
    h["X-Content-Type-Options"] = "nosniff"; h["X-Frame-Options"] = "DENY"; h["Referrer-Policy"] = "no-referrer"
    h["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=()"
    if request.url.path.startswith("/api"):
        h["Cache-Control"] = "no-store"
    if settings.is_prod:
        h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return resp


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "Something went wrong on our side. Please try again."}, status_code=500)


@app.get("/api/health")
@app.get("/health")
def health():
    return {"status": "ok"}          # cheap endpoint for UptimeRobot (does not touch the database)


@app.get("/api/health/deep")
def health_deep():
    with SessionLocal() as db:
        db.execute(text("select 1"))
        n = db.scalar(select(KBDrug.id).limit(1))
    return {"status": "ok", "database": True, "kb": n is not None, "ml": bool(kbsvc.get_kb().ml)}


@app.get("/api/meta/conditions")
def meta_conditions(ctx=Depends(auth)):
    return [{"key": k, "label": v["label"]} for k, v in CONDITIONS.items() if k != "elderly"]


@app.get("/api/meta/drugs")
def meta_drugs(q: str = "", ctx=Depends(auth)):
    k = kbsvc.get_kb(); q = q.strip().lower()
    names = sorted(d["name"] for d in k.drugs.values() if d["kind"] == "drug")
    if not q:
        return names[:0]
    hits = [d["name"] for key, d in k.drugs.items() if q in key]
    hits += [k.drugs[v]["name"] for a, v in k.alias.items() if q in a and k.drugs[v]["kind"] == "drug"]
    out = []
    for h in hits:
        if h not in out: out.append(h)
    return out[:12]


app.include_router(auth_router.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(patient_data.build(__import__("app.deps", fromlist=["owner_self"]).owner_self), prefix="/api/patient", tags=["patient"])
