import uuid
from datetime import timedelta
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from ..config import get_settings
from ..db import get_db, set_rls
from ..deps import AuthCtx, auth, audit, _aware
from ..models import (User, UserSession, AuthToken, PatientProfile, FaceCredential, Medication, Condition, Allergy, Document, AnalysisRun, utcnow)
from ..schemas import (RegisterIn, LoginIn, FaceLoginIn, OtpIn, EmailIn, ResetIn, TokenIn, ChangePwIn, SecurityIn, DeleteAccountIn)
from ..security import (hash_password, verify_password, check_password_strength, new_token, hash_token, new_otp, make_nonce, check_nonce,
                        make_signed, read_signed, client_ip, limiter)
from ..services import emailer, face as facesvc

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])


def user_out(db: Session, u: User) -> dict:
    enrolled = bool(db.scalar(select(FaceCredential.id).where(FaceCredential.user_id == u.id)))
    return {"id": str(u.id), "email": u.email, "role": u.role, "display_name": u.display_name, "email_verified": u.email_verified,
            "face_enrolled": enrolled, "face_2fa": u.face_2fa, "created_at": u.created_at}


def start_session(db: Session, user: User, request: Request, response: Response) -> str:
    token, csrf = new_token(), new_token()
    hours = settings.admin_session_hours if user.role == "admin" else settings.patient_session_hours
    now = utcnow()
    db.execute(delete(UserSession).where(UserSession.user_id == user.id, UserSession.expires_at < now))
    db.add(UserSession(user_id=user.id, token_hash=hash_token(token), csrf_token=csrf, expires_at=now + timedelta(hours=hours),
                       ip=client_ip(request), user_agent=(request.headers.get("user-agent") or "")[:255]))
    user.last_login_at, user.failed_attempts, user.locked_until = now, 0, None
    db.commit()
    response.set_cookie(settings.session_cookie, token, max_age=hours * 3600, httponly=True, secure=settings.secure_cookies, samesite="lax", path="/")
    return csrf


def register_failure(db: Session, user: User):
    user.failed_attempts = (user.failed_attempts or 0) + 1
    if user.failed_attempts >= settings.max_login_attempts:
        user.locked_until = utcnow() + timedelta(minutes=settings.lockout_minutes); user.failed_attempts = 0
    db.commit()


def check_lock(user: User | None):
    if user and user.locked_until and _aware(user.locked_until) > utcnow():
        raise HTTPException(429, f"Too many failed attempts. Try again in {settings.lockout_minutes} minutes.")


def verify_face(db: Session, user: User, descriptor: list[float], nonce: str):
    if not check_nonce(nonce):
        raise HTTPException(401, "Face check expired. Please try again.")
    facesvc.validate_descriptors([descriptor])
    set_rls(db, user.id, user.role)
    cred = db.scalar(select(FaceCredential).where(FaceCredential.user_id == user.id))
    if not cred or not cred.descriptors:
        raise HTTPException(401, "Face not recognised")
    if facesvc.best_distance(cred.descriptors, descriptor) > settings.face_match_threshold:
        register_failure(db, user)
        raise HTTPException(401, "Face not recognised")
    cred.last_verified_at = utcnow()


def _finish(db, user, request, response):
    csrf = start_session(db, user, request, response)
    audit(user, "login", ip=client_ip(request))
    return {"user": user_out(db, user), "csrf": csrf}


def _start_otp(db: Session, user: User, bg: BackgroundTasks):
    code = new_otp()
    t = AuthToken(user_id=user.id, purpose="otp", token_hash=hash_token(new_token()), code_hash=hash_token(code), expires_at=utcnow() + timedelta(minutes=10))
    db.add(t); db.commit()
    bg.add_task(emailer.send_otp, user.email, code)
    return {"otp_required": True, "otp_token": make_signed(f"{user.id}|{t.id}", 600)}


def purge_user_data(db: Session, uid):
    for m in (AnalysisRun, Document, Allergy, Condition, Medication, FaceCredential, PatientProfile, AuthToken, UserSession):
        db.execute(delete(m).where(m.user_id == uid))


@router.post("/register")
def register(body: RegisterIn, request: Request, response: Response, bg: BackgroundTasks, db: Session = Depends(get_db)):
    limiter.check(f"reg:{client_ip(request)}", 10, 3600)
    if not body.consent:
        raise HTTPException(422, "You must accept the privacy notice to register.")
    email = body.email.lower()
    check_password_strength(body.password, email)
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists.")
    if settings.require_face_at_registration and not body.face:
        raise HTTPException(422, "A live face capture is required to register.")
    descs = facesvc.validate_descriptors(body.face.descriptors) if body.face else None
    photo = facesvc.validate_photo(body.face.photo) if body.face else None
    user = User(email=email, password_hash=hash_password(body.password), role="patient", display_name=body.profile.full_name, consent_at=utcnow())
    db.add(user); db.flush()
    set_rls(db, user.id, "patient")
    db.add(PatientProfile(user_id=user.id, **body.profile.model_dump(exclude_none=True)))
    if descs:
        db.add(FaceCredential(user_id=user.id, descriptors=descs, photo=photo))
    vt = new_token()
    db.add(AuthToken(user_id=user.id, purpose="verify", token_hash=hash_token(vt), expires_at=utcnow() + timedelta(hours=48)))
    db.commit()
    bg.add_task(emailer.send_verification, email, vt)
    audit(user, "register", target=user.id, ip=client_ip(request))
    if settings.require_email_verification:
        return {"verification_required": True}
    return _finish(db, user, request, response)


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, bg: BackgroundTasks, db: Session = Depends(get_db)):
    limiter.check(f"login:{client_ip(request)}", 20, 300)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    check_lock(user)
    if not verify_password(body.password, user.password_hash if user else None) or not user:
        if user: register_failure(db, user)
        raise HTTPException(401, "Incorrect email or password.")
    if not user.is_active:
        raise HTTPException(403, "This account is disabled.")
    if settings.require_email_verification and user.role == "patient" and not user.email_verified:
        raise HTTPException(403, "email_not_verified")
    if user.role == "patient" and user.face_2fa:
        if not body.face:
            raise HTTPException(401, "face_required")
        verify_face(db, user, body.face.descriptor, body.face.nonce)
    if user.role == "admin" and settings.admin_require_otp:
        return _start_otp(db, user, bg)
    return _finish(db, user, request, response)


@router.post("/login/otp")
def login_otp(body: OtpIn, request: Request, response: Response, db: Session = Depends(get_db)):
    limiter.check(f"otp:{client_ip(request)}", 10, 600)
    payload = read_signed(body.otp_token)
    if not payload:
        raise HTTPException(401, "Code expired. Sign in again.")
    uid, tid = payload.split("|")
    t = db.get(AuthToken, uuid.UUID(tid)); user = db.get(User, uuid.UUID(uid))
    if not t or not user or t.used_at or _aware(t.expires_at) < utcnow() or t.attempts >= 5:
        raise HTTPException(401, "Code expired. Sign in again.")
    t.attempts += 1
    if t.code_hash != hash_token(body.code):
        db.commit(); raise HTTPException(401, "Incorrect code.")
    t.used_at = utcnow(); db.commit()
    return _finish(db, user, request, response)


@router.get("/face/challenge")
def face_challenge(request: Request):
    limiter.check(f"fch:{client_ip(request)}", 30, 300)
    return {"nonce": make_nonce()}


@router.post("/face/login")
def face_login(body: FaceLoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = client_ip(request)
    limiter.check(f"face:{ip}", 15, 300); limiter.check(f"face:{body.email.lower()}", 10, 900)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    check_lock(user)
    if not user or user.role != "patient" or not user.is_active:
        raise HTTPException(401, "Face not recognised")
    if settings.require_email_verification and not user.email_verified:
        raise HTTPException(403, "email_not_verified")
    verify_face(db, user, body.descriptor, body.nonce)
    return _finish(db, user, request, response)


@router.get("/me")
def me(ctx: AuthCtx = Depends(auth), db: Session = Depends(get_db)):
    return {"user": user_out(db, ctx.user), "csrf": ctx.sess.csrf_token}


@router.post("/logout")
def logout(response: Response, ctx: AuthCtx = Depends(auth), db: Session = Depends(get_db)):
    ctx.sess.revoked = True; db.commit()
    response.delete_cookie(settings.session_cookie, path="/")
    return {"ok": True}


@router.post("/logout-all")
def logout_all(response: Response, ctx: AuthCtx = Depends(auth), db: Session = Depends(get_db)):
    for s in db.scalars(select(UserSession).where(UserSession.user_id == ctx.user.id, UserSession.revoked.is_(False))):
        s.revoked = True
    db.commit()
    response.delete_cookie(settings.session_cookie, path="/")
    return {"ok": True}


@router.post("/verify-email")
def verify_email(body: TokenIn, db: Session = Depends(get_db)):
    t = db.scalar(select(AuthToken).where(AuthToken.token_hash == hash_token(body.token), AuthToken.purpose == "verify"))
    if not t or t.used_at or _aware(t.expires_at) < utcnow():
        raise HTTPException(400, "This verification link is invalid or has expired.")
    user = db.get(User, t.user_id); user.email_verified = True; t.used_at = utcnow(); db.commit()
    return {"ok": True}


@router.post("/resend-verification")
def resend_verification(body: EmailIn, request: Request, bg: BackgroundTasks, db: Session = Depends(get_db)):
    limiter.check(f"resend:{client_ip(request)}", 5, 3600)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user and not user.email_verified and user.role == "patient":
        vt = new_token()
        db.add(AuthToken(user_id=user.id, purpose="verify", token_hash=hash_token(vt), expires_at=utcnow() + timedelta(hours=48))); db.commit()
        bg.add_task(emailer.send_verification, user.email, vt)
    return {"ok": True}


@router.post("/forgot")
def forgot(body: EmailIn, request: Request, bg: BackgroundTasks, db: Session = Depends(get_db)):
    limiter.check(f"forgot:{client_ip(request)}", 5, 3600)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user and user.is_active:
        t = new_token()
        db.add(AuthToken(user_id=user.id, purpose="reset", token_hash=hash_token(t), expires_at=utcnow() + timedelta(minutes=30))); db.commit()
        bg.add_task(emailer.send_reset, user.email, t)
    return {"ok": True}   # same answer whether or not the account exists


@router.post("/reset")
def reset(body: ResetIn, db: Session = Depends(get_db)):
    t = db.scalar(select(AuthToken).where(AuthToken.token_hash == hash_token(body.token), AuthToken.purpose == "reset"))
    if not t or t.used_at or _aware(t.expires_at) < utcnow():
        raise HTTPException(400, "This reset link is invalid or has expired.")
    user = db.get(User, t.user_id)
    check_password_strength(body.password, user.email)
    user.password_hash = hash_password(body.password); user.failed_attempts = 0; user.locked_until = None
    t.used_at = utcnow()
    for s in db.scalars(select(UserSession).where(UserSession.user_id == user.id)): s.revoked = True
    db.commit()
    audit(user, "password_reset", target=user.id)
    return {"ok": True}


@router.post("/change-password")
def change_password(body: ChangePwIn, ctx: AuthCtx = Depends(auth), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, ctx.user.password_hash):
        raise HTTPException(401, "Current password is incorrect.")
    check_password_strength(body.new_password, ctx.user.email)
    ctx.user.password_hash = hash_password(body.new_password)
    for s in db.scalars(select(UserSession).where(UserSession.user_id == ctx.user.id, UserSession.id != ctx.sess.id)): s.revoked = True
    db.commit(); audit(ctx.user, "password_change", target=ctx.user.id, ip=ctx.ip)
    return {"ok": True}


@router.patch("/security")
def security(body: SecurityIn, ctx: AuthCtx = Depends(auth), db: Session = Depends(get_db)):
    if ctx.user.role != "patient":
        raise HTTPException(403, "Not available")
    if body.face_2fa and not db.scalar(select(FaceCredential.id).where(FaceCredential.user_id == ctx.user.id)):
        raise HTTPException(422, "Register your face first.")
    ctx.user.face_2fa = body.face_2fa; db.commit()
    return {"user": user_out(db, ctx.user)}


@router.delete("/me")
def delete_me(body: DeleteAccountIn, response: Response, ctx: AuthCtx = Depends(auth), db: Session = Depends(get_db)):
    """Right to erasure: permanently deletes the patient account and every record linked to it."""
    if ctx.user.role != "patient":
        raise HTTPException(403, "Doctor accounts are managed in the server configuration.")
    if not verify_password(body.password, ctx.user.password_hash):
        raise HTTPException(401, "Password is incorrect.")
    uid, email = ctx.user.id, ctx.user.email
    audit(ctx.user, "account_deleted_by_user", target=uid, details={"email": email}, ip=ctx.ip)
    purge_user_data(db, uid); db.execute(delete(User).where(User.id == uid)); db.commit()
    response.delete_cookie(settings.session_cookie, path="/")
    return {"ok": True}
