import uuid
from datetime import datetime, date, timezone
from sqlalchemy import (String, Text, Boolean, Integer, Float, Date, DateTime, JSON, ForeignKey, Uuid, TypeDecorator, Index, func)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from cryptography.fernet import Fernet, MultiFernet, InvalidToken
import json
from .config import get_settings
from .db import Base

_JSON = JSON().with_variant(JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


_fernet = None


def fernet() -> MultiFernet:
    global _fernet
    if _fernet is None:
        keys = [k.strip() for k in get_settings().field_encryption_keys.split(",") if k.strip()]
        if not keys:  # development convenience only (production refuses to boot without keys)
            keys = [Fernet.generate_key().decode()]
        _fernet = MultiFernet([Fernet(k.encode()) for k in keys])
    return _fernet


class EncStr(TypeDecorator):
    """Application-level (Fernet/AES-128-CBC+HMAC) encryption for sensitive text columns."""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value in (None, "") else fernet().encrypt(str(value).encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            return fernet().decrypt(value.encode()).decode()
        except InvalidToken:
            return None


class EncJSON(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return None if value is None else fernet().encrypt(json.dumps(value).encode()).decode()

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            return json.loads(fernet().decrypt(value.encode()).decode())
        except InvalidToken:
            return None


def pk():
    return mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


def fk_user():
    return mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = pk()
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="patient")          # patient | admin
    display_name: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    face_2fa: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AuthToken(Base):
    __tablename__ = "auth_tokens"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk_user()
    purpose: Mapped[str] = mapped_column(String(16))                          # verify | reset | otp
    token_hash: Mapped[str] = mapped_column(String(64), index=True)
    code_hash: Mapped[str | None] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserSession(Base):
    __tablename__ = "sessions"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk_user()
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(255))


class PatientProfile(Base):
    __tablename__ = "patient_profiles"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(120))
    dob: Mapped[date | None] = mapped_column(Date)
    sex: Mapped[str | None] = mapped_column(String(16))
    blood_group: Mapped[str | None] = mapped_column(String(8))
    phone: Mapped[str | None] = mapped_column(EncStr)
    address: Mapped[str | None] = mapped_column(EncStr)
    city: Mapped[str | None] = mapped_column(String(80))
    state: Mapped[str | None] = mapped_column(String(80))
    country: Mapped[str | None] = mapped_column(String(80))
    emergency_contact_name: Mapped[str | None] = mapped_column(EncStr)
    emergency_contact_phone: Mapped[str | None] = mapped_column(EncStr)
    height_cm: Mapped[float | None] = mapped_column(Float)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    smoker: Mapped[str | None] = mapped_column(String(16))                   # never | former | current
    alcohol: Mapped[str | None] = mapped_column(String(16))                   # none | occasional | moderate | heavy
    diet_preference: Mapped[str | None] = mapped_column(String(24))
    pregnant: Mapped[bool] = mapped_column(Boolean, default=False)
    breastfeeding: Mapped[bool] = mapped_column(Boolean, default=False)
    egfr: Mapped[float | None] = mapped_column(Float)
    serum_creatinine: Mapped[float | None] = mapped_column(Float)
    alt: Mapped[float | None] = mapped_column(Float)
    ast: Mapped[float | None] = mapped_column(Float)
    potassium: Mapped[float | None] = mapped_column(Float)
    inr: Mapped[float | None] = mapped_column(Float)
    hba1c: Mapped[float | None] = mapped_column(Float)
    systolic_bp: Mapped[int | None] = mapped_column(Integer)
    diastolic_bp: Mapped[int | None] = mapped_column(Integer)
    heart_rate: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(EncStr)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class FaceCredential(Base):
    __tablename__ = "face_credentials"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    descriptors: Mapped[list | None] = mapped_column(EncJSON)                 # list of 128-d vectors
    photo: Mapped[str | None] = mapped_column(EncStr)                         # small JPEG data-URL captured live
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Medication(Base):
    __tablename__ = "medications"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk_user()
    name: Mapped[str] = mapped_column(String(160))
    normalized_name: Mapped[str | None] = mapped_column(String(160))          # canonical KB name if recognised
    dose: Mapped[str | None] = mapped_column(String(60))
    frequency: Mapped[str | None] = mapped_column(String(60))
    route: Mapped[str | None] = mapped_column(String(30))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(12), default="active")         # active | stopped
    source: Mapped[str] = mapped_column(String(12), default="manual")         # manual | report
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Condition(Base):
    __tablename__ = "conditions"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk_user()
    name: Mapped[str] = mapped_column(String(160))
    condition_key: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(12), default="active")         # active | resolved
    since: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(12), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Allergy(Base):
    __tablename__ = "allergies"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk_user()
    allergen: Mapped[str] = mapped_column(String(120))
    reaction: Mapped[str | None] = mapped_column(String(160))
    severity: Mapped[str | None] = mapped_column(String(12))
    source: Mapped[str] = mapped_column(String(12), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk_user()
    filename: Mapped[str | None] = mapped_column(String(200))
    content_type: Mapped[str | None] = mapped_column(String(80))
    text: Mapped[str | None] = mapped_column(EncStr)
    entities: Mapped[dict | None] = mapped_column(_JSON)
    status: Mapped[str] = mapped_column(String(12), default="pending")        # pending | applied
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk_user()
    requested_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    score: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[str] = mapped_column(String(12), default="None")
    result: Mapped[dict] = mapped_column(_JSON)
    snapshot: Mapped[dict] = mapped_column(_JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[uuid.UUID] = pk()
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    actor_email: Mapped[str | None] = mapped_column(String(254))
    actor_role: Mapped[str | None] = mapped_column(String(16))
    action: Mapped[str] = mapped_column(String(80), index=True)
    target_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    table_name: Mapped[str | None] = mapped_column(String(60))
    row_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict | None] = mapped_column(_JSON)
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class KBDrug(Base):
    __tablename__ = "kb_drugs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    class_name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(8), default="drug")              # drug | food
    tags: Mapped[list] = mapped_column(_JSON, default=list)
    synonyms: Mapped[list] = mapped_column(_JSON, default=list)


class KBInteraction(Base):
    __tablename__ = "kb_interactions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    drug_a: Mapped[str] = mapped_column(String(160), index=True)
    drug_b: Mapped[str] = mapped_column(String(160), index=True)
    severity: Mapped[str] = mapped_column(String(12))                         # Minor | Moderate | Major
    mechanism: Mapped[str] = mapped_column(Text)
    effect: Mapped[str] = mapped_column(Text)
    management: Mapped[str] = mapped_column(Text)
    diet_advice: Mapped[str] = mapped_column(Text)
