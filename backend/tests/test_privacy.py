"""Privacy protections are tested, not just described."""
import io
import json
import shutil
from datetime import timedelta

import pytest
from sqlalchemy import text

from app.api import visits as visits_api
from app.core import ratelimit
from app.core.config import settings
from app.core.llm import LLMUnavailable
from app.database.session import SessionLocal
from app.models import utcnow
from app.models.visits import Visit
from app.privacy.redact import redact
from app.services import visit_ai

TRANSCRIPT = ("Doctor: Test Patient, your phone 98765 43210 and Aadhaar 2345 6789 0123 are on file. "
              "Take Metformin 500 mg after breakfast. Come back after one month.")


@pytest.fixture(autouse=True)
def _reset():
    ratelimit.reset()
    yield


def consent(client, auth):
    client.patch("/api/auth/me", headers=auth, json={"ai_data_consent": True})


def confirmed(client, auth, monkeypatch):
    monkeypatch.setattr(visit_ai, "chat_json", lambda *a, **k: (_ for _ in ()).throw(LLMUnavailable("off")))
    v = client.post("/api/visits/typed", headers=auth, json={"transcript": TRANSCRIPT, "doctor_name": "Dr. Rao"}).json()
    client.post(f"/api/visits/{v['id']}/extract", headers=auth)
    return client.post(f"/api/visits/{v['id']}/confirm", headers=auth).json()


# ---------------------------------------------------------------- encryption at rest
def test_medical_text_is_encrypted_in_the_database(client, auth, monkeypatch):
    v = confirmed(client, auth, monkeypatch)
    with SessionLocal() as db:
        raw_t = db.execute(text("SELECT transcript FROM mm_visits WHERE id=:i"), {"i": v["id"]}).scalar()
        raw_i = db.execute(text("SELECT simple_text, source_sentence FROM mm_visit_instructions WHERE visit_id=:i"), {"i": v["id"]}).all()
        raw_c = db.execute(text("SELECT text FROM mm_doctor_instructions")).scalars().all()
    assert raw_t.startswith("mmenc1:") and "Metformin" not in raw_t
    assert all(a.startswith("mmenc1:") and b.startswith("mmenc1:") for a, b in raw_i)
    assert raw_c and all(c.startswith("mmenc1:") for c in raw_c)
    assert "Metformin" in client.get(f"/api/visits/{v['id']}", headers=auth).json()["transcript"]  # API still decrypts


def test_uploaded_file_is_encrypted_on_disk(client, auth):
    note = b"Take Metformin 500 mg after breakfast and after dinner. Come back after one month."
    v = client.post("/api/visits/document", headers=auth, files={"file": ("note.txt", note, "text/plain")}).json()
    files = [p for p in (settings.storage_dir).rglob("*.txt")]
    newest = max(files, key=lambda p: p.stat().st_mtime)
    assert newest.read_bytes().startswith(b"MMENC1") and b"Metformin" not in newest.read_bytes()
    assert client.get(f"/api/documents/{v['document_id']}/file", headers=auth).content == note


def test_cached_audio_is_encrypted(client, auth, monkeypatch):
    consent(client, auth)
    v = confirmed(client, auth, monkeypatch)
    monkeypatch.setattr(visits_api.el, "synthesize", lambda *a, **k: b"ID3-audio-bytes")
    r = client.get(f"/api/visits/instructions/{v['instructions'][0]['id']}/audio", headers=auth)
    assert r.content == b"ID3-audio-bytes"
    with SessionLocal() as db:
        raw = db.execute(text("SELECT data FROM mm_audio_clips")).scalars().all()
    assert raw and all(bytes(b).startswith(b"MMENC1") for b in raw)


# ---------------------------------------------------------------- privacy shield
def test_redaction_rules():
    r = redact("Lakshmi Raman DOB: 12/05/1958 ph +91 98765 43210, mail l@x.com, Aadhaar 2345 6789 0123, "
               "ABHA 91-1234-5678-9012, lakshmi.r@abdm, PIN: 641112. Take Metformin 500 mg on 25/12/2026.", ["Lakshmi Raman", "Lakshmi"])
    for leaked in ("Lakshmi", "98765", "l@x.com", "2345 6789", "1234-5678", "@abdm", "641112", "1958"):
        assert leaked not in r.text
    assert "Metformin 500 mg" in r.text and "25/12/2026" in r.text  # medical content and visit dates are kept


def test_ai_never_sees_personal_details(client, auth, monkeypatch):
    consent(client, auth)
    seen = []

    def llm(system, user, **k):
        seen.append(user)
        return {"doctor_name": "", "instructions": [{"category": "medicine", "source_sentence": "Take Metformin 500 mg after breakfast.",
                                                     "simple_text": "Take Metformin 500 mg after breakfast."}]}
    monkeypatch.setattr(visit_ai, "chat_json", llm)
    v = client.post("/api/visits/typed", headers=auth, json={"transcript": TRANSCRIPT}).json()
    v = client.post(f"/api/visits/{v['id']}/extract", headers=auth).json()
    sent = "\n".join(seen)
    assert "Test Patient" not in sent and "98765" not in sent and "2345 6789" not in sent
    kinds = {r["kind"] for r in v["privacy"]["removed_before_ai"]}
    assert {"NAME", "PHONE", "AADHAAR"} <= kinds
    assert not v["instructions"][0]["needs_check"]  # still traced against the (redacted) transcript


def test_question_is_redacted_before_matching(client, auth, monkeypatch):
    consent(client, auth)
    confirmed(client, auth, monkeypatch)
    seen = []
    monkeypatch.setattr(visits_api.settings, "llm_api_key", "k")
    monkeypatch.setattr(visit_ai, "chat_json", lambda s, u, **k: seen.append(u) or {"ids": []})
    client.post("/api/visits/ask", headers=auth, json={"question": "I am Test Patient, 9876543210, when is Metformin?"})
    assert seen and "9876543210" not in seen[-1] and "Test Patient" not in seen[-1]


# ---------------------------------------------------------------- OCR
@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract not installed")
def test_photo_is_read_with_ocr_and_confidence(client, auth, monkeypatch):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (1400, 420), "white")
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
    except OSError:
        f = ImageFont.load_default()
    for i, line in enumerate(["Tab Metformin 500 mg after breakfast", "Avoid sweets. Walk 30 minutes daily.", "Review after 1 month"]):
        d.text((60, 50 + i * 110), line, fill="black", font=f)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    monkeypatch.setattr(visit_ai, "chat_json", lambda *a, **k: (_ for _ in ()).throw(LLMUnavailable("off")))
    v = client.post("/api/visits/document", headers=auth, files={"file": ("rx.png", buf.getvalue(), "image/png")}).json()
    assert v["text_method"] == "ocr" and "Metformin" in v["transcript"]
    assert v["ocr"]["confidence"] > 70 and "eng" in v["ocr"]["langs"]


# ---------------------------------------------------------------- rights: summary, export, delete, retention
def test_privacy_summary(client, auth, monkeypatch):
    confirmed(client, auth, monkeypatch)
    s = client.get("/api/privacy/summary", headers=auth).json()
    assert {p["key"] for p in s["protections"]} >= {"encryption", "shield", "audio", "drafts", "consent", "access"}
    assert s["stored"]["visits_confirmed"] == 1 and s["services"][0]["name"] == "ElevenLabs"


def test_export_contains_decrypted_data(client, auth, monkeypatch):
    confirmed(client, auth, monkeypatch)
    r = client.get("/api/privacy/export", headers=auth)
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    data = json.loads(r.content)
    assert "Metformin" in data["visits"][0]["transcript"] and data["account"]["full_name"] == "Test Patient"


def test_delete_account_removes_everything(client, auth, other_auth, monkeypatch):
    confirmed(client, auth, monkeypatch)
    confirmed(client, other_auth, monkeypatch)
    assert client.post("/api/privacy/delete-account", headers=auth, json={"password": "wrong", "confirm": "DELETE"}).status_code == 403
    assert client.post("/api/privacy/delete-account", headers=auth, json={"password": "Secret123", "confirm": "nope"}).status_code == 422
    assert client.post("/api/privacy/delete-account", headers=auth, json={"password": "Secret123", "confirm": "DELETE"}).status_code == 204
    assert client.post("/api/auth/login", json={"email": "pat@example.com", "password": "Secret123"}).status_code == 401
    with SessionLocal() as db:
        owners = set(db.execute(text("SELECT owner_id FROM mm_visits")).scalars().all())
    assert len(owners) == 1  # only the other patient's data remains
    assert client.get("/api/visits", headers=other_auth).json()


def test_unconfirmed_drafts_expire_after_24_hours(client, auth):
    v = client.post("/api/visits/typed", headers=auth, json={"transcript": TRANSCRIPT}).json()
    with SessionLocal() as db:
        db.get(Visit, v["id"]).created_at = utcnow() - timedelta(hours=25)
        db.commit()
    assert client.get("/api/visits", headers=auth).json() == []


def test_any_random_string_works_as_encryption_key(monkeypatch):
    from app.privacy import crypto
    monkeypatch.setenv("DATA_ENCRYPTION_KEY", "render-generated-random-value-8f3k2l1m9")
    crypto.reset_key_cache()
    try:
        enc = crypto.encrypt_text("Metformin 500 mg")
        assert enc.startswith("mmenc1:") and crypto.decrypt_text(enc) == "Metformin 500 mg"
    finally:
        monkeypatch.delenv("DATA_ENCRYPTION_KEY")
        crypto.reset_key_cache()
