"""Privacy centre: what we store, how it is protected, and the patient's rights (export, withdraw consent, delete).

Aligned with the consent and data-principal rights in India's Digital Personal Data Protection Act, 2023.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.deps import client_ip, get_current_user
from app.core.security import verify_password
from app.database.session import get_db
from app.models import (
    Appointment, AuditLog, Consultation, MedicalDocument, Medication, User,
)
from app.models.visits import Visit, VisitInstruction
from app.privacy import crypto
from app.privacy.redact import merge
from app.services.audit import audit

router = APIRouter(prefix="/api/privacy", tags=["privacy"])


def _llm_host() -> str | None:
    if not settings.llm_enabled:
        return None
    host = settings.llm_base_url.split("//")[-1].split("/")[0]
    return {"generativelanguage.googleapis.com": "Google Gemini API", "api.openai.com": "OpenAI API"}.get(host, host)


@router.get("/summary")
def summary(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    visits = db.scalars(select(Visit).where(Visit.owner_id == user.id)).all()
    removed = merge(*[json.loads(v.privacy_report or "{}").get("removed_before_ai", []) for v in visits])
    count = lambda model: db.scalar(select(func.count()).select_from(model).where(model.owner_id == user.id)) or 0  # noqa: E731
    recent = db.scalars(select(AuditLog).where(AuditLog.user_id == user.id).order_by(AuditLog.created_at.desc()).limit(12)).all()
    return {
        "consent": {"ai_and_voice": bool(user.profile and user.profile.ai_data_consent)},
        "protections": [
            {"key": "encryption", "on": True, "title": "Encrypted at rest",
             "detail": "Transcripts, instructions, translations, uploaded files and cached audio are encrypted (AES with HMAC, Fernet)."},
            {"key": "shield", "on": True, "title": "Personal details removed before AI",
             "detail": "Names, phone numbers, Aadhaar/ABHA numbers, emails, dates of birth and PIN codes are replaced before text is sent to the AI."},
            {"key": "audio", "on": True, "title": "Recordings are not stored",
             "detail": "Visit audio is turned into text and discarded. Only the text you confirm is kept."},
            {"key": "drafts", "on": True, "title": "Unconfirmed drafts deleted after 24 hours",
             "detail": "Nothing becomes part of your record until you confirm it."},
            {"key": "consent", "on": bool(user.profile and user.profile.ai_data_consent), "title": "AI and voice only with your consent",
             "detail": "You can withdraw consent at any time; the app then stops sending anything to AI or voice services."},
            {"key": "access", "on": True, "title": "Only you (and family you invite) can see it",
             "detail": "Every request is checked against your login. Family access is read-only and can be revoked."},
        ],
        "removed_before_ai": removed,
        "photos_sent_to_ai": sum(1 for v in visits if json.loads(v.privacy_report or "{}").get("photo_sent_to_ai")),
        "services": [
            {"name": "ElevenLabs", "purpose": "Speech-to-text and spoken answers", "receives": "Audio you record; instruction text to speak"},
            *([{"name": _llm_host(), "purpose": "Finding instructions, translation, understanding questions",
                "receives": "Text with personal details removed"}] if _llm_host() else []),
        ],
        "stored": {
            "visits_confirmed": sum(1 for v in visits if v.status == "confirmed"),
            "visit_drafts": sum(1 for v in visits if v.status == "draft"),
            "instructions": db.scalar(select(func.count()).select_from(VisitInstruction).where(VisitInstruction.owner_id == user.id)) or 0,
            "documents": count(MedicalDocument), "consultations": count(Consultation),
            "medications": count(Medication), "appointments": count(Appointment),
        },
        "encryption_key": crypto.key_source(),
        "recent_activity": [{"action": a.action, "at": a.created_at.isoformat(), "detail": a.detail} for a in recent],
    }


@router.get("/export")
def export(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Everything we hold about the patient, decrypted, as one JSON file (right to access)."""
    visits = db.scalars(select(Visit).options(selectinload(Visit.instructions).selectinload(VisitInstruction.translations))
                        .where(Visit.owner_id == user.id)).all()
    rows = lambda model: db.scalars(select(model).where(model.owner_id == user.id)).all()  # noqa: E731
    plain = lambda o, cols: {c: (getattr(o, c).isoformat() if hasattr(getattr(o, c), "isoformat") else getattr(o, c)) for c in cols}  # noqa: E731
    data = {
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "account": {"email": user.email, "full_name": user.full_name},
        "visits": [{
            **plain(v, ["id", "doctor_name", "visit_date", "status", "source", "text_method", "transcript", "confirmed_at"]),
            "instructions": [{**plain(i, ["category", "source_sentence", "simple_text"]),
                              "translations": {t.lang: {"text": t.text, "verified": t.verified} for t in i.translations}}
                             for i in v.instructions],
        } for v in visits],
        "documents": [plain(d, ["id", "title", "original_filename", "mime_type", "status", "created_at"]) for d in rows(MedicalDocument)],
        "medications": [plain(m, ["id", "name", "dosage", "frequency", "instructions"]) for m in rows(Medication)],
        "appointments": [plain(a, ["id", "title", "doctor_name", "scheduled_at"]) for a in rows(Appointment)],
        "activity_log": [plain(a, ["action", "resource_type", "resource_id", "created_at"])
                         for a in db.scalars(select(AuditLog).where(AuditLog.user_id == user.id).order_by(AuditLog.created_at)).all()],
    }
    audit(db, user.id, "privacy.export", ip=client_ip(request))
    db.commit()
    return Response(json.dumps(data, ensure_ascii=False, indent=2, default=str), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="medimemory-my-data.json"', "Cache-Control": "no-store"})


class DeleteIn(BaseModel):
    password: str = Field(min_length=1, max_length=200)
    confirm: str = Field(pattern="^DELETE$")


@router.post("/delete-account", status_code=204)
def delete_account(body: DeleteIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Right to erasure: removes the account, every record and every stored file. Cannot be undone."""
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(403, "Password is incorrect.")
    uid = user.id
    audit(db, uid, "privacy.delete_account", detail="account and all data deleted at the user's request", ip=client_ip(request))
    db.commit()
    shutil.rmtree(settings.storage_dir / str(int(uid)), ignore_errors=True)
    db.expunge_all()
    db.execute(delete(User).where(User.id == uid))  # database cascades remove all owned rows; audit rows keep no user id
    db.commit()
