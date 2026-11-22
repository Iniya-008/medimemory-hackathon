from datetime import datetime, date, time
from sqlalchemy import String, Text, Boolean, DateTime, Date, Time, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    preferred_language: Mapped[str] = mapped_column(String(40), default="English")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    consultations = relationship("Consultation", back_populates="user", cascade="all, delete-orphan")

class Consultation(Base):
    __tablename__ = "consultations"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    doctor_name: Mapped[str] = mapped_column(String(120), default="")
    hospital_name: Mapped[str] = mapped_column(String(160), default="")
    consultation_date: Mapped[date] = mapped_column(Date, default=date.today)
    original_text: Mapped[str] = mapped_column(Text, default="")
    extracted_information: Mapped[str] = mapped_column(Text, default="")
    confirmation_status: Mapped[str] = mapped_column(String(30), default="unconfirmed")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="consultations")
    medications = relationship("Medication", back_populates="consultation", cascade="all, delete-orphan")

class Medication(Base):
    __tablename__ = "medications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    consultation_id: Mapped[int | None] = mapped_column(ForeignKey("consultations.id"), nullable=True)
    medicine_name: Mapped[str] = mapped_column(String(160))
    doctor_prescribed_instruction: Mapped[str] = mapped_column(Text, default="")
    frequency: Mapped[str] = mapped_column(String(100), default="As recorded")
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    confirmation_status: Mapped[str] = mapped_column(String(30), default="unconfirmed")
    consultation = relationship("Consultation", back_populates="medications")

class Reminder(Base):
    __tablename__ = "reminders"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    medication_id: Mapped[int] = mapped_column(ForeignKey("medications.id"))
    reminder_time: Mapped[str] = mapped_column(String(5))
    reminder_status: Mapped[str] = mapped_column(String(30), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    medication = relationship("Medication")

class Appointment(Base):
    __tablename__ = "appointments"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    doctor_name: Mapped[str] = mapped_column(String(120), default="")
    hospital_name: Mapped[str] = mapped_column(String(160), default="")
    appointment_date: Mapped[datetime] = mapped_column(DateTime)
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="upcoming")

class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    consultation_id: Mapped[int | None] = mapped_column(ForeignKey("consultations.id"), nullable=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    source_reference: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Caregiver(Base):
    __tablename__ = "caregivers"
    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    caregiver_email: Mapped[str] = mapped_column(String(255))
    permissions: Mapped[str] = mapped_column(Text, default="consultations")
    access_status: Mapped[str] = mapped_column(String(30), default="pending")
