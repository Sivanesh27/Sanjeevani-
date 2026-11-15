import hashlib, hmac, secrets, time, re
from collections import defaultdict, deque
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError, VerificationError
from fastapi import HTTPException, Request
from .config import get_settings

settings = get_settings()
_ph = PasswordHasher()   # argon2id, library defaults (OWASP-recommended class of parameters)
_DUMMY_HASH = _ph.hash("not-a-real-password")
_COMMON = {"password123", "1234567890", "qwertyuiop", "iloveyou123", "welcome123", "admin12345", "password1234", "letmein1234"}


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(pw: str, hashed: str | None) -> bool:
    try:
        return _ph.verify(hashed or _DUMMY_HASH, pw) and hashed is not None
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False


def check_password_strength(pw: str, email: str = "") -> None:
    errs = []
    if len(pw) < 10: errs.append("at least 10 characters")
    if not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw): errs.append("both letters and numbers")
    if email and email.split("@")[0].lower() in pw.lower() and len(email.split("@")[0]) >= 4: errs.append("must not contain your email name")
    if pw.lower() in _COMMON: errs.append("too common")
    if errs:
        raise HTTPException(422, "Password needs: " + ", ".join(errs))


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


def new_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _sign(msg: str) -> str:
    key = (settings.secret_key or "dev-only-secret").encode()
    return hmac.new(key, msg.encode(), hashlib.sha256).hexdigest()[:32]


def make_nonce() -> str:
    body = f"{int(time.time())}.{secrets.token_hex(8)}"
    return f"{body}.{_sign(body)}"


def check_nonce(nonce: str, ttl: int = 180) -> bool:
    try:
        ts, rnd, sig = nonce.split(".")
        return hmac.compare_digest(sig, _sign(f"{ts}.{rnd}")) and 0 <= time.time() - int(ts) <= ttl
    except Exception:
        return False


def make_signed(payload: str, ttl: int = 600) -> str:
    body = f"{payload}|{int(time.time()) + ttl}"
    return f"{body}|{_sign(body)}"


def read_signed(token: str) -> str | None:
    try:
        payload, exp, sig = token.rsplit("|", 2)
        if hmac.compare_digest(sig, _sign(f"{payload}|{exp}")) and time.time() < int(exp):
            return payload
    except Exception:
        pass
    return None


def client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    return (xff.split(",")[0].strip() if xff else (request.client.host if request.client else "unknown"))[:64]


class RateLimiter:
    """Small in-memory sliding-window limiter (single-instance deployments; swap for Redis when scaling out)."""
    def __init__(self):
        self.hits: dict[str, deque] = defaultdict(deque)

    def check(self, key: str, limit: int, window: int):
        now = time.time(); q = self.hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(429, "Too many attempts. Please wait a moment and try again.")
        q.append(now)

    def reset(self):
        self.hits.clear()


limiter = RateLimiter()
