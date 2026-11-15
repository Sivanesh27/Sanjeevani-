import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
import hmac
from .config import get_settings
from .db import get_db, set_rls, SessionLocal
from .models import User, UserSession, AuditLog, utcnow
from .security import hash_token, client_ip

settings = get_settings()
SAFE = {"GET", "HEAD", "OPTIONS"}


@dataclass
class AuthCtx:
    user: User
    sess: UserSession
    ip: str


def _aware(dt):
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def audit(actor: User | None, action: str, *, target=None, table=None, row_id=None, details=None, ip=None):
    """Written in its own transaction so the trail survives even if the request later fails."""
    with SessionLocal() as s:
        s.add(AuditLog(actor_id=actor.id if actor else None, actor_email=actor.email if actor else None, actor_role=actor.role if actor else None,
                       action=action, target_user_id=target, table_name=table, row_id=str(row_id) if row_id else None, details=details, ip=ip))
        s.commit()


def auth(request: Request, db: Session = Depends(get_db)) -> AuthCtx:
    token = request.cookies.get(settings.session_cookie)
    if not token:
        raise HTTPException(401, "Not signed in")
    sess = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    now = utcnow()
    if not sess or sess.revoked or _aware(sess.expires_at) < now:
        raise HTTPException(401, "Session expired")
    user = db.get(User, sess.user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "Account disabled")
    idle = settings.admin_idle_minutes if user.role == "admin" else settings.patient_idle_minutes
    if now - _aware(sess.last_seen_at) > timedelta(minutes=idle):
        sess.revoked = True; db.commit()
        raise HTTPException(401, "Session timed out")
    if request.method not in SAFE:
        sent = request.headers.get("x-csrf-token", "")
        if not hmac.compare_digest(sent, sess.csrf_token):
            raise HTTPException(403, "Security check failed (CSRF). Please refresh the page.")
    if now - _aware(sess.last_seen_at) > timedelta(seconds=60):
        sess.last_seen_at = now; db.commit()
    set_rls(db, user.id, user.role)
    return AuthCtx(user, sess, client_ip(request))


def require_admin(ctx: AuthCtx = Depends(auth)) -> AuthCtx:
    if ctx.user.role != "admin":
        raise HTTPException(403, "Doctor access required")
    return ctx


def require_patient(ctx: AuthCtx = Depends(auth)) -> AuthCtx:
    if ctx.user.role != "patient":
        raise HTTPException(403, "Patient account required")
    return ctx


@dataclass
class Owner:
    id: uuid.UUID
    actor: User
    ip: str
    by_admin: bool


def owner_self(ctx: AuthCtx = Depends(require_patient)) -> Owner:
    return Owner(ctx.user.id, ctx.user, ctx.ip, False)


def owner_admin(uid: uuid.UUID, request: Request, ctx: AuthCtx = Depends(require_admin), db: Session = Depends(get_db)) -> Owner:
    target = db.get(User, uid)
    if not target or target.role != "patient":
        raise HTTPException(404, "Patient not found")
    audit(ctx.user, f"{request.method} {request.url.path.split('/api', 1)[-1]}", target=uid, ip=ctx.ip)
    return Owner(uid, ctx.user, ctx.ip, True)
