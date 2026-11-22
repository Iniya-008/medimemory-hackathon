import os, tempfile
from fastapi.testclient import TestClient
# Use a separate database before importing the app.
tmp = tempfile.mktemp(suffix=".db")
os.environ["DATABASE_URL"] = "sqlite:///" + tmp
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough"
from app.main import app
client = TestClient(app)

def token():
    r=client.post("/api/auth/login",json={"email":"demo@medimemory.test","password":"Demo123!"})
    assert r.status_code==200
    return r.json()["access_token"]

def test_health(): assert client.get("/api/health").json()["status"]=="ok"
def test_login_and_dashboard():
    t=token(); h={"Authorization":f"Bearer {t}"}
    r=client.get("/api/dashboard",headers=h)
    assert r.status_code==200 and r.json()["consultation_count"]>=1
def test_consultation_ownership():
    t=token(); h={"Authorization":f"Bearer {t}"}
    rows=client.get("/api/consultations",headers=h).json()
    assert rows and rows[0]["confirmation_status"]=="confirmed"
    assert client.get("/api/consultations/99999",headers=h).status_code==404
def test_auth_required(): assert client.get("/api/consultations").status_code==401
def test_chat_has_source():
    t=token(); h={"Authorization":f"Bearer {t}"}
    r=client.post("/api/assistant/chat",headers=h,json={"question":"When is my follow-up?","language":"English"})
    assert r.status_code==200 and r.json()["sources"]
def test_reminder_rejects_unconfirmed_medication():
    t=token(); h={"Authorization":f"Bearer {t}"}
    r=client.post("/api/medications",headers=h,json={"medicine_name":"Unverified sample","confirmation_status":"unconfirmed"})
    assert r.status_code==200
    med_id=r.json()["id"]
    r=client.post("/api/reminders",headers=h,json={"medication_id":med_id,"reminder_time":"09:00"})
    assert r.status_code==400
