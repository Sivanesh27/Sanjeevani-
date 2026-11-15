import json
from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"                      # development | production | test
    database_url: str = "sqlite:///./dev.db"
    secret_key: str = ""                          # signs face-login nonces / OTP tokens
    field_encryption_keys: str = ""               # comma separated Fernet keys (first = active)

    frontend_url: str = "http://localhost:5173"
    allowed_origins: str = ""                     # comma separated; frontend_url is always allowed
    cookie_secure: bool | None = None             # default: True in production
    session_cookie: str = "sj_session"

    patient_session_hours: int = 24
    patient_idle_minutes: int = 720
    admin_session_hours: int = 8
    admin_idle_minutes: int = 30

    admin_email: str = ""
    admin_password: str = ""
    admin_name: str = "Doctor"
    admin_accounts: str = ""                      # JSON: [{"email":..,"password":..,"name":..}]
    admin_sync_password: bool = False             # re-apply env password to existing admins at boot
    admin_require_otp: bool = False               # email OTP for admin login (needs Brevo)

    brevo_api_key: str = ""
    brevo_sender_email: str = ""
    brevo_sender_name: str = "Sanjeevani AI"

    require_email_verification: bool = False
    require_face_at_registration: bool = True
    face_match_threshold: float = 0.5             # euclidean distance, face-api.js descriptors
    enable_rls: bool = False                      # Postgres row-level security (see DEPLOYMENT.md)
    max_login_attempts: int = 5
    lockout_minutes: int = 15
    max_upload_mb: int = 3

    @field_validator("database_url")
    @classmethod
    def _fix_url(cls, v: str) -> str:
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://"):]
        if v.startswith("postgresql://"):
            v = "postgresql+psycopg://" + v[len("postgresql://"):]
        return v

    @property
    def is_prod(self) -> bool:
        return self.env == "production"

    @property
    def secure_cookies(self) -> bool:
        return self.is_prod if self.cookie_secure is None else self.cookie_secure

    @property
    def origins(self) -> list[str]:
        o = [self.frontend_url.rstrip("/")] + [x.strip().rstrip("/") for x in self.allowed_origins.split(",") if x.strip()]
        return sorted(set(o))

    def admin_list(self) -> list[dict]:
        out = []
        if self.admin_email and self.admin_password:
            out.append({"email": self.admin_email, "password": self.admin_password, "name": self.admin_name})
        if self.admin_accounts.strip():
            out += json.loads(self.admin_accounts)
        return out


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.is_prod:
        missing = [n for n in ("secret_key", "field_encryption_keys") if not getattr(s, n)]
        if missing:
            raise RuntimeError(f"Missing required production settings: {', '.join(m.upper() for m in missing)}")
    return s
