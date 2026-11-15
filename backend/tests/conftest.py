import os, sys
os.environ.setdefault("ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ["ADMIN_EMAIL"] = "doctor@test.com"; os.environ["ADMIN_PASSWORD"] = "Doctor-Passw0rd!"
os.environ["FIELD_ENCRYPTION_KEYS"] = "Vg4m5l6Yq0nO0b0wX0o1m2n3o4p5q6r7s8t9u0v1w2A="
os.environ["SECRET_KEY"] = "test-secret"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text


@pytest.fixture(scope="session")
def app():
    from app.db import Base, engine
    Base.metadata.drop_all(engine)
    from app.main import app as a
    with TestClient(a):  # runs lifespan once to create schema + seed
        pass
    return a


@pytest.fixture()
def client(app):
    from app.security import limiter
    limiter.reset()
    with TestClient(app, base_url="http://localhost") as c:
        yield c


def desc(seed=0.1):
    return [round(seed + i * 0.001, 4) for i in range(128)]


PROFILE = {"full_name": "Asha Raman", "dob": "1950-04-12", "sex": "female", "phone": "+91 90000 00000", "city": "Chennai", "country": "India",
           "height_cm": 160, "weight_kg": 68, "smoker": "never", "alcohol": "none", "blood_group": "B+"}


def register(c, email, seed=0.1, **extra):
    r = c.post("/api/auth/register", json={"email": email, "password": "Str0ng-Passw0rd", "profile": {**PROFILE, **extra}, "consent": True,
                                          "face": {"descriptors": [desc(seed)], "photo": "data:image/jpeg;base64,/9j/AAAA"}})
    assert r.status_code == 200, r.text
    c.headers["X-CSRF-Token"] = r.json()["csrf"]
    return r.json()


def login_admin(c):
    r = c.post("/api/auth/login", json={"email": "doctor@test.com", "password": "Doctor-Passw0rd!"})
    assert r.status_code == 200, r.text
    c.headers["X-CSRF-Token"] = r.json()["csrf"]
    return r.json()
