import json
from fastapi.testclient import TestClient
from .conftest import register, login_admin, desc


def fresh(app):
    c = TestClient(app, base_url="http://localhost"); return c


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/health/deep").json()["ml"] is True


def test_register_login_and_session(client, app):
    d = register(client, "p1@test.com")
    assert d["user"]["role"] == "patient" and d["user"]["face_enrolled"]
    assert client.get("/api/auth/me").json()["user"]["email"] == "p1@test.com"
    assert client.post("/api/auth/register", json={"email": "p1@test.com", "password": "Str0ng-Passw0rd", "profile": {}, "consent": True}).status_code in (409, 422)
    c2 = fresh(app)
    assert c2.post("/api/auth/login", json={"email": "p1@test.com", "password": "wrong-password"}).status_code == 401
    assert c2.post("/api/auth/login", json={"email": "p1@test.com", "password": "Str0ng-Passw0rd"}).status_code == 200


def test_weak_password_and_missing_consent(client):
    r = client.post("/api/auth/register", json={"email": "w@test.com", "password": "short1", "profile": {}, "consent": True})
    assert r.status_code == 422
    r = client.post("/api/auth/register", json={"email": "w@test.com", "password": "Str0ng-Passw0rd", "profile": {}, "consent": False})
    assert r.status_code == 422


def test_csrf_required_for_writes(client):
    register(client, "csrf@test.com")
    good = client.headers.pop("X-CSRF-Token")
    assert client.put("/api/patient/profile", json={"city": "X"}).status_code == 403
    client.headers["X-CSRF-Token"] = good
    assert client.put("/api/patient/profile", json={"city": "Madurai"}).json()["city"] == "Madurai"


def test_mass_assignment_rejected(client):
    register(client, "ma@test.com")
    assert client.put("/api/patient/profile", json={"city": "X", "user_id": "x"}).status_code == 422
    assert client.post("/api/patient/medications", json={"name": "Warfarin", "user_id": "x"}).status_code == 422


def test_data_isolation_between_patients(client, app):
    register(client, "a@test.com", seed=0.1)
    m = client.post("/api/patient/medications", json={"name": "Warfarin", "dose": "5 mg"}).json()
    assert m["in_kb"] and m["normalized_name"] == "Warfarin"
    b = fresh(app); register(b, "b@test.com", seed=0.3)
    assert b.get("/api/patient/medications").json() == []
    assert b.put(f"/api/patient/medications/{m['id']}", json={"dose": "99 mg"}).status_code == 404
    assert b.delete(f"/api/patient/medications/{m['id']}").status_code == 404
    assert b.get("/api/admin/patients").status_code == 403
    assert b.get("/api/admin/tables").status_code == 403
    assert client.get("/api/patient/medications").json()[0]["dose"] == "5 mg"


def test_analysis_is_personalised(client):
    register(client, "an@test.com")
    for n in ("Warfarin", "Ibuprofen", "Lisinopril"):
        client.post("/api/patient/medications", json={"name": n})
    client.put("/api/patient/profile", json={"serum_creatinine": 1.8, "potassium": 5.4, "inr": 3.4})
    client.post("/api/patient/conditions", json={"name": "Peptic ulcer", "condition_key": "peptic_ulcer_history"})
    a = client.post("/api/patient/analysis/run").json()
    assert a["overall"]["level"] == "Critical"
    top = a["interactions"][0]
    assert top["score"] > top["base_severity"].__len__() and any("ulcer" in f["label"].lower() for f in top["factors"])
    assert a["diet"] and a["monitoring"] and a["questions_for_doctor"]
    assert len(client.get("/api/patient/analysis").json()) == 1
    healthy = fresh(client.app); register(healthy, "young@test.com", dob="1995-01-01", sex="male"); healthy.post("/api/patient/medications", json={"name": "Warfarin"}); healthy.post("/api/patient/medications", json={"name": "Ibuprofen"})
    h = healthy.post("/api/patient/analysis/run").json()
    assert h["interactions"][0]["score"] < top["score"]


def test_analysis_needs_medicine(client):
    register(client, "nomed@test.com")
    assert client.post("/api/patient/analysis/run").status_code == 422


def test_report_ner_upload_and_apply(client):
    register(client, "ner@test.com")
    text = "Allergies: Penicillin (rash)\nPMH: Type 2 diabetes, CKD\nMedications:\nTab Ecosprin 75 mg OD\nWarfarin 5 mg BD\nCreatinine 2.1 mg/dL, K 5.6\nNo history of asthma."
    r = client.post("/api/patient/documents/upload", files={"file": ("report.txt", text.encode(), "text/plain")})
    assert r.status_code == 200, r.text
    d = r.json()
    names = {m["name"] for m in d["suggestions"]["medications"]}
    assert {"Aspirin", "Warfarin"} <= names and d["labs"]["potassium"] == 5.6
    assert all(c["condition_key"] != "asthma_copd" for c in d["suggestions"]["conditions"])
    s = d["suggestions"]
    ap = client.post(f"/api/patient/documents/{d['id']}/apply", json={"medications": [{"name": m["name"], "dose": m.get("dose"), "frequency": m.get("frequency")} for m in s["medications"]],
                                                                     "conditions": [{"name": c["name"], "condition_key": c["condition_key"]} for c in s["conditions"]],
                                                                     "allergies": [{"allergen": a["allergen"], "reaction": a["reaction"]} for a in s["allergies"]],
                                                                     "profile": {"potassium": d["labs"]["potassium"], "serum_creatinine": d["labs"]["serum_creatinine"]}})
    assert ap.json()["added"]["medications"] == 2
    assert client.get("/api/patient/profile").json()["potassium"] == 5.6
    assert client.post("/api/patient/documents/upload", files={"file": ("x.exe", b"MZ", "application/octet-stream")}).status_code == 415
    assert client.post("/api/patient/documents/upload", files={"file": ("x.pdf", b"not a pdf", "application/pdf")}).status_code == 415


def test_face_login_and_2fa(client, app):
    register(client, "face@test.com", seed=0.1)
    c = fresh(app)
    n = c.get("/api/auth/face/challenge").json()["nonce"]
    ok = c.post("/api/auth/face/login", json={"email": "face@test.com", "descriptor": desc(0.1), "nonce": n})
    assert ok.status_code == 200
    bad = fresh(app); n = bad.get("/api/auth/face/challenge").json()["nonce"]
    assert bad.post("/api/auth/face/login", json={"email": "face@test.com", "descriptor": desc(0.9), "nonce": n}).status_code == 401
    assert bad.post("/api/auth/face/login", json={"email": "face@test.com", "descriptor": desc(0.1), "nonce": "forged.nonce.value"}).status_code == 401
    assert client.patch("/api/auth/security", json={"face_2fa": True}).json()["user"]["face_2fa"] is True
    c2 = fresh(app)
    r = c2.post("/api/auth/login", json={"email": "face@test.com", "password": "Str0ng-Passw0rd"})
    assert r.status_code == 401 and r.json()["detail"] == "face_required"
    n = c2.get("/api/auth/face/challenge").json()["nonce"]
    assert c2.post("/api/auth/login", json={"email": "face@test.com", "password": "Str0ng-Passw0rd", "face": {"descriptor": desc(0.1), "nonce": n}}).status_code == 200


def test_lockout(client, app):
    register(client, "lock@test.com")
    c = fresh(app)
    codes = [c.post("/api/auth/login", json={"email": "lock@test.com", "password": "bad-password-x"}).status_code for _ in range(6)]
    assert codes[:5] == [401] * 5 and codes[5] == 429
    assert c.post("/api/auth/login", json={"email": "lock@test.com", "password": "Str0ng-Passw0rd"}).status_code == 429


def test_no_admin_registration_and_admin_flow(client, app):
    p = fresh(app); pdata = register(p, "pat@test.com"); pid = pdata["user"]["id"]
    p.post("/api/patient/medications", json={"name": "Metformin"})
    assert client.post("/api/auth/register", json={"email": "doctor2@test.com", "password": "Str0ng-Passw0rd", "profile": {"role": "admin"}, "consent": True}).status_code == 422
    a = fresh(app); login_admin(a)
    assert a.get("/api/auth/me").json()["user"]["role"] == "admin"
    assert any(x["email"] == "pat@test.com" for x in a.get("/api/admin/patients?q=pat@").json()["items"])
    assert a.get(f"/api/admin/patients/{pid}/medications").json()[0]["name"] == "Metformin"
    assert a.put(f"/api/admin/patients/{pid}/profile", json={"city": "Coimbatore"}).json()["city"] == "Coimbatore"
    assert a.get(f"/api/admin/patients/{pid}/face").json()["photo"].startswith("data:image/jpeg")
    assert a.post(f"/api/admin/patients/{pid}/analysis/run").status_code == 200
    assert p.get("/api/patient/profile").json()["city"] == "Coimbatore"
    log = a.get(f"/api/admin/audit?target={pid}").json()
    assert log["total"] >= 4 and any("profile" in x["action"] for x in log["items"])
    assert a.get("/api/admin/stats").json()["patients"] >= 1
    assert a.get("/api/admin/patients/00000000-0000-0000-0000-000000000000/profile").status_code == 404
    assert a.delete(f"/api/admin/patients/{pid}").status_code == 200 and p.get("/api/auth/me").status_code == 401


def test_admin_explorer_update_swap_delete(client, app):
    a = fresh(app); login_admin(a)
    t = {x["name"]: x for x in a.get("/api/admin/tables").json()}
    assert {"users", "kb_interactions", "audit_logs"} <= set(t) and "password_hash" not in [c["name"] for c in t["users"]["columns"]]
    row = a.post("/api/admin/tables/kb_interactions", json={"drug_a": "TestA", "drug_b": "TestB", "severity": "Major", "mechanism": "m", "effect": "e", "management": "g", "diet_advice": "d"}).json()
    assert a.put(f"/api/admin/tables/kb_interactions/{row['id']}", json={"effect": "edited"}).json()["effect"] == "edited"
    sw = a.post("/api/admin/tables/kb_interactions/swap", json={"mode": "columns", "id": row["id"], "col_a": "drug_a", "col_b": "drug_b"}).json()["rows"][0]
    assert (sw["drug_a"], sw["drug_b"]) == ("TestB", "TestA")
    row2 = a.post("/api/admin/tables/kb_interactions", json={"drug_a": "X1", "drug_b": "X2", "severity": "Minor", "mechanism": "m", "effect": "e2", "management": "g", "diet_advice": "d"}).json()
    s2 = a.post("/api/admin/tables/kb_interactions/swap", json={"mode": "rows", "id_a": row["id"], "id_b": row2["id"], "fields": ["severity"]}).json()["rows"]
    assert (s2[0]["severity"], s2[1]["severity"]) == ("Minor", "Major")
    assert a.delete(f"/api/admin/tables/kb_interactions/{row['id']}").status_code == 200
    assert a.put("/api/admin/tables/users/" + a.get("/api/admin/tables/users").json()["items"][0]["id"], json={"role": "admin"}).status_code == 422
    assert a.put("/api/admin/tables/audit_logs/x", json={"action": "x"}).status_code in (404, 422, 405)
    assert a.delete("/api/admin/tables/audit_logs/1").status_code == 405
    assert a.post("/api/admin/tables/users", json={"email": "x@x.com"}).status_code == 405


def test_kb_edit_changes_analysis(client, app):
    a = fresh(app); login_admin(a)
    a.post("/api/admin/tables/kb_drugs", json={"name": "Zorbitol", "class_name": "NSAID", "kind": "drug", "tags": ["nsaid", "bleeding_risk", "gi_risk"], "synonyms": ["zorb"]})
    p = fresh(app); register(p, "kbtest@test.com")
    assert p.post("/api/patient/medications", json={"name": "zorb"}).json()["normalized_name"] == "Zorbitol"
    p.post("/api/patient/medications", json={"name": "Warfarin"})
    r = p.post("/api/patient/analysis/run").json()
    assert any("Zorbitol" in (i["drug_a"], i["drug_b"]) for i in r["interactions"] + r["possible_interactions"])


def test_password_reset_and_change(client, app, monkeypatch):
    sent = {}
    from app.services import emailer
    monkeypatch.setattr(emailer, "send_reset", lambda to, tok: sent.update(tok=tok))
    register(client, "reset@test.com")
    assert client.post("/api/auth/forgot", json={"email": "reset@test.com"}).status_code == 200
    assert client.post("/api/auth/forgot", json={"email": "nobody@test.com"}).status_code == 200
    assert client.post("/api/auth/reset", json={"token": sent["tok"], "password": "N3w-Passw0rd!!"}).status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    c = fresh(app)
    assert c.post("/api/auth/login", json={"email": "reset@test.com", "password": "N3w-Passw0rd!!"}).status_code == 200
    assert client.post("/api/auth/reset", json={"token": sent["tok"], "password": "N3w-Passw0rd!!"}).status_code == 400


def test_delete_account_erases_everything(client, app):
    d = register(client, "bye@test.com"); client.post("/api/patient/medications", json={"name": "Warfarin"})
    assert client.request("DELETE", "/api/auth/me", json={"password": "wrong"}).status_code == 401
    assert client.request("DELETE", "/api/auth/me", json={"password": "Str0ng-Passw0rd"}).status_code == 200
    from app.db import SessionLocal
    from app.models import User, Medication, FaceCredential
    from sqlalchemy import select, func
    with SessionLocal() as s:
        assert s.scalar(select(func.count()).select_from(User).where(User.email == "bye@test.com")) == 0
        assert s.scalar(select(func.count()).select_from(Medication).where(Medication.user_id == __import__("uuid").UUID(d["user"]["id"]))) == 0


def test_origin_check(client):
    r = client.post("/api/auth/login", json={"email": "a@b.com", "password": "x"}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403


def test_sensitive_fields_encrypted_at_rest(client):
    register(client, "enc@test.com", phone="+91 99999 11111")
    from app.db import engine
    from sqlalchemy import text
    with engine.connect() as c:
        if engine.dialect.name == "postgresql":   # RLS hides rows from an identity-less connection - act as admin
            c.execute(text("select set_config('app.role','admin',false)"))
        raw = c.execute(text("select phone from patient_profiles where phone is not null limit 1")).scalar()
        photo = c.execute(text("select photo from face_credentials limit 1")).scalar()
    assert "99999" not in raw and raw.startswith("gAAAA") and photo.startswith("gAAAA")
