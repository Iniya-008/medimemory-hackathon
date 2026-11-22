from datetime import date, datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict

class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
class LoginIn(BaseModel):
    email: EmailStr
    password: str
class ConsultationIn(BaseModel):
    doctor_name: str = ""
    hospital_name: str = ""
    consultation_date: date
    original_text: str = Field(min_length=1)
    extracted_information: str = ""
    confirmation_status: str = "unconfirmed"
class MedicationIn(BaseModel):
    consultation_id: int | None = None
    medicine_name: str
    doctor_prescribed_instruction: str = ""
    frequency: str = "As recorded"
    start_date: date | None = None
    end_date: date | None = None
    confirmation_status: str = "unconfirmed"
class ReminderIn(BaseModel):
    medication_id: int
    reminder_time: str
    reminder_status: str = "active"
class AppointmentIn(BaseModel):
    doctor_name: str = ""
    hospital_name: str = ""
    appointment_date: datetime
    notes: str = ""
    status: str = "upcoming"
class ChatIn(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    language: str = "English"
class ExplainIn(BaseModel):
    consultation_id: int
    instruction: str = Field(min_length=1, max_length=4000)
class ProfileIn(BaseModel):
    name: str
    preferred_language: str = "English"
