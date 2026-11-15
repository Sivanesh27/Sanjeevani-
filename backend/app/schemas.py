from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


Sex = Literal["male", "female", "other"]
Smoker = Literal["never", "former", "current"]
Alcohol = Literal["none", "occasional", "moderate", "heavy"]
Diet = Literal["vegetarian", "non_vegetarian", "vegan", "eggetarian"]
Blood = Literal["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]


class ProfileIn(Strict):
    full_name: Optional[str] = Field(None, max_length=120)
    dob: Optional[date] = None
    sex: Optional[Sex] = None
    blood_group: Optional[Blood] = None
    phone: Optional[str] = Field(None, max_length=30)
    address: Optional[str] = Field(None, max_length=300)
    city: Optional[str] = Field(None, max_length=80)
    state: Optional[str] = Field(None, max_length=80)
    country: Optional[str] = Field(None, max_length=80)
    emergency_contact_name: Optional[str] = Field(None, max_length=120)
    emergency_contact_phone: Optional[str] = Field(None, max_length=30)
    height_cm: Optional[float] = Field(None, ge=40, le=250)
    weight_kg: Optional[float] = Field(None, ge=2, le=400)
    smoker: Optional[Smoker] = None
    alcohol: Optional[Alcohol] = None
    diet_preference: Optional[Diet] = None
    pregnant: Optional[bool] = None
    breastfeeding: Optional[bool] = None
    egfr: Optional[float] = Field(None, ge=1, le=200)
    serum_creatinine: Optional[float] = Field(None, ge=0.1, le=20)
    alt: Optional[float] = Field(None, ge=1, le=5000)
    ast: Optional[float] = Field(None, ge=1, le=5000)
    potassium: Optional[float] = Field(None, ge=1.5, le=9)
    inr: Optional[float] = Field(None, ge=0.5, le=12)
    hba1c: Optional[float] = Field(None, ge=3, le=20)
    systolic_bp: Optional[int] = Field(None, ge=50, le=280)
    diastolic_bp: Optional[int] = Field(None, ge=20, le=180)
    heart_rate: Optional[int] = Field(None, ge=20, le=250)
    notes: Optional[str] = Field(None, max_length=2000)

    @field_validator("dob")
    @classmethod
    def _dob(cls, v):
        if v and (v > date.today() or v.year < 1900):
            raise ValueError("Invalid date of birth")
        return v


class FaceIn(Strict):
    descriptors: list[list[float]]
    photo: Optional[str] = None


class RegisterIn(Strict):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    profile: ProfileIn
    face: Optional[FaceIn] = None
    consent: bool


class LoginIn(Strict):
    email: EmailStr
    password: str = Field(max_length=128)
    face: Optional["FaceProbe"] = None


class FaceProbe(Strict):
    descriptor: list[float]
    nonce: str


LoginIn.model_rebuild()


class FaceLoginIn(Strict):
    email: EmailStr
    descriptor: list[float]
    nonce: str


class OtpIn(Strict):
    otp_token: str
    code: str = Field(min_length=6, max_length=6)


class EmailIn(Strict):
    email: EmailStr


class ResetIn(Strict):
    token: str
    password: str = Field(min_length=10, max_length=128)


class TokenIn(Strict):
    token: str


class ChangePwIn(Strict):
    current_password: str
    new_password: str = Field(min_length=10, max_length=128)


class SecurityIn(Strict):
    face_2fa: bool


class DeleteAccountIn(Strict):
    password: str


class MedIn(Strict):
    name: str = Field(min_length=1, max_length=160)
    dose: Optional[str] = Field(None, max_length=60)
    frequency: Optional[str] = Field(None, max_length=60)
    route: Optional[str] = Field(None, max_length=30)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Literal["active", "stopped"] = "active"


class MedPatch(Strict):
    name: Optional[str] = Field(None, min_length=1, max_length=160)
    dose: Optional[str] = Field(None, max_length=60)
    frequency: Optional[str] = Field(None, max_length=60)
    route: Optional[str] = Field(None, max_length=30)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[Literal["active", "stopped"]] = None


class CondIn(Strict):
    name: str = Field(min_length=1, max_length=160)
    condition_key: Optional[str] = Field(None, max_length=40)
    status: Literal["active", "resolved"] = "active"
    since: Optional[date] = None


class CondPatch(Strict):
    name: Optional[str] = Field(None, min_length=1, max_length=160)
    condition_key: Optional[str] = Field(None, max_length=40)
    status: Optional[Literal["active", "resolved"]] = None
    since: Optional[date] = None


class AllergyIn(Strict):
    allergen: str = Field(min_length=1, max_length=120)
    reaction: Optional[str] = Field(None, max_length=160)
    severity: Optional[Literal["mild", "moderate", "severe"]] = None


class AllergyPatch(Strict):
    allergen: Optional[str] = Field(None, min_length=1, max_length=120)
    reaction: Optional[str] = Field(None, max_length=160)
    severity: Optional[Literal["mild", "moderate", "severe"]] = None


class TextDocIn(Strict):
    text: str = Field(min_length=3, max_length=60000)
    filename: Optional[str] = Field(None, max_length=200)


class ApplyIn(Strict):
    medications: list[MedIn] = []
    conditions: list[CondIn] = []
    allergies: list[AllergyIn] = []
    profile: Optional[ProfileIn] = None


class AdminAccountIn(Strict):
    is_active: Optional[bool] = None
    email_verified: Optional[bool] = None
    face_2fa: Optional[bool] = None


class SetPasswordIn(Strict):
    password: str = Field(min_length=10, max_length=128)
