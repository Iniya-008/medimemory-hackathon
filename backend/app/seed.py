"""Seed a clearly-fictional demo patient (Lakshmi Raman, 68, Tamil) and her son as a demo caregiver.

Usage:  python -m app.seed            (skips if the demo user exists)
        python -m app.seed --reset    (deletes and recreates the demo accounts)
All dates are relative to today so the demo always looks current.
"""
from __future__ import annotations

import secrets
import sys
from datetime import date, datetime, time, timedelta

from sqlalchemy import select

from app.core.config import BACKEND_DIR
from app.core.security import hash_password
from app.database.session import SessionLocal
from app.models import (Appointment, CaregiverInvitation, CaregiverPermission, Consultation, DoctorInstruction,
                        DocumentExtraction, MedicalDocument, Medication, MedicationSchedule, PatientProfile, Reminder, User, utcnow)
from app.rag.indexer import reindex_user
from app.services import storage
from app.services.audit import audit
from app.services.extraction import process_document
from app.services.reminders import ensure_reminders
from app.utils import sample_docs

DEMO_EMAIL = "demo@medimemory.app"
DEMO_PASSWORD = "Demo@1234"
CAREGIVER_EMAIL = "caregiver.demo@medimemory.app"
CAREGIVER_PASSWORD = "Care@1234"


def _doc(db, owner: User, title: str, doc_type: str, content: bytes, mime: str, ext: str, ddate: date, consultation_id=None):
    stored = storage.save_file(owner.id, content, ext)
    res = process_document(content, mime, use_llm=False)
    doc = MedicalDocument(owner_id=owner.id, title=title, doc_type=doc_type, original_filename=f"{title}{ext}",
                          stored_filename=stored, mime_type=mime, size_bytes=len(content), document_date=ddate,
                          status="confirmed", consultation_id=consultation_id,
                          notes="Fictional demo document.")
    structured = dict(res.structured)
    doc.extraction = DocumentExtraction(raw_text=res.raw_text, method=res.method, confidence=res.confidence,
                                        structured=structured, warnings=res.warnings,
                                        confirmed_data={**structured, "title": title, "doc_type": doc_type},
                                        confirmed_at=utcnow())
    db.add(doc)
    db.flush()
    return doc


def seed(reset: bool = False) -> None:
    from app import models  # noqa: F401  (register every table)
    from app.database.session import Base, engine
    Base.metadata.create_all(engine)  # safe: only creates tables that are missing
    db = SessionLocal()
    try:
        existing = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        if existing and not reset:
            print(f"Demo data already present ({DEMO_EMAIL}). Use --reset to recreate.")
            return
        for email in (DEMO_EMAIL, CAREGIVER_EMAIL):
            u = db.scalar(select(User).where(User.email == email))
            if u:
                db.delete(u)
        db.commit()

        today = date.today()
        patient = User(email=DEMO_EMAIL, full_name="Lakshmi Raman", password_hash=hash_password(DEMO_PASSWORD), is_demo=True)
        patient.profile = PatientProfile(
            date_of_birth=date(today.year - 68, 6, 2), gender="Female", phone="+91 90000 00000",
            address="Fictional address, Coimbatore", blood_group="O+", emergency_contact_name="Karthik Raman (fictional)",
            emergency_contact_phone="+91 90000 00001", emergency_contact_relation="Son", preferred_language="ta",
            ai_data_consent=True, voice_autoplay=True, reminders_enabled=True)
        caregiver = User(email=CAREGIVER_EMAIL, full_name="Karthik Raman", password_hash=hash_password(CAREGIVER_PASSWORD), is_demo=True)
        caregiver.profile = PatientProfile(ai_data_consent=False)
        db.add_all([patient, caregiver])
        db.flush()

        # ---------------- consultation 1: diabetologist, ~6 weeks ago (blood sugar)
        c1_date = today - timedelta(days=42)
        c1 = Consultation(owner_id=patient.id, doctor_name="Dr. Arjun Menon", specialty="Diabetologist",
                          clinic="City Care Hospital", consultation_date=c1_date,
                          symptoms="More thirsty than usual and tired in the afternoons.",
                          doctor_notes="Reviewed the Greenleaf Diagnostics report: fasting glucose and HbA1c above the lab reference range. Started Metformin.",
                          recommended_tests="HbA1c before the next visit",
                          follow_up_date=today + timedelta(days=20), status="confirmed")
        c1.instructions = [DoctorInstruction(text=t) for t in [
            "Take Metformin 500 mg after breakfast and after dinner.",
            "Avoid sweets and sugary drinks.",
            "Walk for 30 minutes every evening.",
        ]]

        # ---------------- consultation 2: general physician, ~10 days ago (blood pressure)
        c2_date = today - timedelta(days=10)
        c2_follow = today + timedelta(days=20)
        c2 = Consultation(owner_id=patient.id, doctor_name="Dr. Kavitha Rao", specialty="General Physician",
                          clinic="Sunrise Family Clinic", consultation_date=c2_date,
                          symptoms="Occasional headaches in the evening.",
                          doctor_notes="Clinic blood pressure higher than last time. Started Amlodipine. Continue Metformin as prescribed by Dr. Menon.",
                          recommended_tests="HbA1c blood test before the next visit",
                          follow_up_date=c2_follow, status="confirmed")
        c2.instructions = [DoctorInstruction(text=t) for t in [
            "Take Amlodipine 5 mg once in the morning.",
            "Continue Metformin 500 mg after breakfast and after dinner.",
            "Reduce salt and avoid packaged snacks.",
            "Do the HbA1c blood test before the next visit.",
            "Come back after one month with the HbA1c report.",
        ]]
        db.add_all([c1, c2])
        db.flush()

        # ---------------- medications (labels and instructions never repeat each other)
        metformin = Medication(owner_id=patient.id, consultation_id=c1.id, name="Metformin", dosage="500 mg",
                               frequency="Twice daily", start_date=c1_date, end_date=c1_date + timedelta(days=90),
                               instructions="With food", prescribed_by="Dr. Arjun Menon")
        metformin.schedules = [MedicationSchedule(time_of_day="08:30", label="After breakfast"),
                               MedicationSchedule(time_of_day="20:30", label="After dinner")]
        amlo = Medication(owner_id=patient.id, consultation_id=c2.id, name="Amlodipine", dosage="5 mg",
                          frequency="Once daily", start_date=c2_date, instructions="For blood pressure",
                          prescribed_by="Dr. Kavitha Rao")
        amlo.schedules = [MedicationSchedule(time_of_day="08:00", label="Morning")]
        db.add_all([metformin, amlo])
        db.flush()

        # ---------------- documents (generated, clearly fictional files through the real pipeline)
        lab_date = c1_date - timedelta(days=4)
        _doc(db, patient, "Blood test report - Greenleaf Diagnostics", "lab_report",
             sample_docs.lab_report_pdf(lab_date), "application/pdf", ".pdf", lab_date, c1.id)
        rx = _doc(db, patient, "Prescription - Dr. Arjun Menon", "prescription",
                  sample_docs.prescription_pdf(c1_date, c2_follow), "application/pdf", ".pdf", c1_date, c1.id)
        c1.source_document_id = rx.id
        note = sample_docs.consultation_note_txt(c2_date, c2_follow).encode()
        nd = _doc(db, patient, "Consultation note - Dr. Kavitha Rao", "consultation_note", note, "text/plain", ".txt", c2_date, c2.id)
        c2.source_document_id = nd.id

        # ---------------- the latest visit as a confirmed after-visit memory (shown on the chat home page)
        from app.models.visits import Visit, VisitInstruction
        visit_text = (
            "[SAMPLE - pre-written for demonstration, not a real consultation]\n"
            "Dr. Kavitha Rao: Lakshmi amma, your BP is a little high this time. "
            "Take Amlodipine 5 mg once in the morning. "
            "Continue Metformin 500 mg after breakfast and after dinner. "
            "Reduce salt and avoid packaged snacks. "
            "Walk for 30 minutes every evening. "
            "Do the HbA1c blood test before the next visit. "
            "Come back after one month with the HbA1c report."
        )
        items = [
            ("medicine", "Take Amlodipine 5 mg once in the morning.", "Take Amlodipine 5 mg once in the morning."),
            ("medicine", "Continue Metformin 500 mg after breakfast and after dinner.", "Take Metformin 500 mg after breakfast and after dinner."),
            ("diet", "Reduce salt and avoid packaged snacks.", "Reduce salt and avoid packaged snacks."),
            ("lifestyle", "Walk for 30 minutes every evening.", "Walk for 30 minutes every evening."),
            ("test", "Do the HbA1c blood test before the next visit.", "Do the HbA1c blood test before the next visit."),
            ("follow_up", "Come back after one month with the HbA1c report.", "Come back after one month with the HbA1c report."),
        ]
        v = Visit(owner_id=patient.id, doctor_name="Dr. Kavitha Rao", visit_date=c2_date, status="confirmed", source="sample",
                  transcript=visit_text, text_method="typed", extraction_method="rules", confirmed_at=utcnow(),
                  consultation_id=c2.id)
        v.instructions = [VisitInstruction(owner_id=patient.id, position=i, category=c, source_sentence=src, simple_text=txt)
                          for i, (c, src, txt) in enumerate(items)]
        db.add(v)
        db.flush()

        # ---------------- appointments (short titles; dates always relative to today)
        def at(d: date, h: int, m: int = 0) -> datetime:
            return datetime.combine(d, time(h, m))
        db.add_all([
            Appointment(owner_id=patient.id, title="Sugar review", doctor_name="Dr. Arjun Menon", specialty="Diabetologist",
                        hospital="City Care Hospital", scheduled_at=at(c1_date, 11), status="completed", consultation_id=c1.id),
            Appointment(owner_id=patient.id, title="BP check", doctor_name="Dr. Kavitha Rao", specialty="General Physician",
                        hospital="Sunrise Family Clinic", scheduled_at=at(c2_date, 17, 30), status="completed", consultation_id=c2.id),
            Appointment(owner_id=patient.id, title="HbA1c blood test", hospital="Greenleaf Diagnostics",
                        location="Fictional address, Coimbatore", scheduled_at=at(today + timedelta(days=12), 8),
                        notes="Fasting: no food for 10 to 12 hours before. Water is fine.", reminder_minutes_before=720),
            Appointment(owner_id=patient.id, title="Follow-up visit", doctor_name="Dr. Kavitha Rao",
                        specialty="General Physician", hospital="Sunrise Family Clinic", scheduled_at=at(c2_follow, 10, 30),
                        is_follow_up=True, consultation_id=c2.id, notes="Bring the HbA1c report."),
        ])
        db.flush()

        # ---------------- reminder history for the last 7 days (fictional dose log)
        for i in range(7, 0, -1):
            ensure_reminders(db, patient.id, today - timedelta(days=i))
        db.flush()
        pattern = ["taken", "taken", "taken", "missed", "taken", "taken", "taken", "taken", "pending", "taken"]
        past = db.scalars(select(Reminder).where(Reminder.owner_id == patient.id, Reminder.kind == "medication",
                                                 Reminder.due_at < datetime.combine(today, time.min)).order_by(Reminder.due_at)).all()
        for i, r in enumerate(past):
            r.status = pattern[i % len(pattern)]
            r.acted_at = r.due_at + timedelta(minutes=12) if r.status != "pending" else None
        ensure_reminders(db, patient.id, today)

        # ---------------- caregiver: her son Karthik has accepted view-only access to medicines + appointments
        inv = CaregiverInvitation(patient_id=patient.id, caregiver_email=CAREGIVER_EMAIL, caregiver_name="Karthik Raman",
                                  relationship_label="Son", token=secrets.token_urlsafe(24),
                                  permissions=["appointments", "medications"], consent_given=True, status="accepted",
                                  expires_at=utcnow() + timedelta(days=7), accepted_at=utcnow(), caregiver_user_id=caregiver.id)
        db.add(inv)
        db.flush()
        for scope in inv.permissions:
            db.add(CaregiverPermission(patient_id=patient.id, caregiver_id=caregiver.id, scope=scope, invitation_id=inv.id))

        # ---------------- index + example conversations (generated by the real pipeline)
        for kind, rows in (("document.upload", db.scalars(select(MedicalDocument).where(MedicalDocument.owner_id == patient.id)).all()),
                           ("consultation.create", [c1, c2])):
            for r in rows:
                audit(db, patient.id, kind, kind.split(".")[0], r.id, detail="seeded demo data")
        reindex_user(db, patient.id)
        db.commit()
        files = sample_docs.write_demo_files(BACKEND_DIR / "sample_documents", today)
        print("Seeded fictional demo data.")
        print(f"  Patient login:   {DEMO_EMAIL} / {DEMO_PASSWORD}")
        print(f"  Caregiver login: {CAREGIVER_EMAIL} / {CAREGIVER_PASSWORD}")
        print("  Demo upload files:", ", ".join(f.name for f in files))
    finally:
        db.close()


if __name__ == "__main__":
    seed(reset="--reset" in sys.argv)
