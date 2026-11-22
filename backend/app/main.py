import os, io, base64
from datetime import date, datetime
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from dotenv import load_dotenv
from .database import Base, engine, get_db, SessionLocal
from .models import User, Consultation, Medication, Reminder, Appointment, Conversation, Caregiver
from .schemas import *
from .auth import current_user, hash_password, verify_password, create_token
from .services.document_service import extract_text, ALLOWED
from .services.rag_service import retrieve, answer_question
from .services.elevenlabs_service import transcribe, speak

load_dotenv()
Base.metadata.create_all(bind=engine)
app = FastAPI(title="MediMemory API", version="1.0.0", description="Post-consultation memory companion. Not for diagnosis or prescribing.")
origins = [x.strip() for x in os.getenv("CORS_ORIGINS","http://localhost:5173").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def seed_demo():
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email=="demo@medimemory.test"))
        if not user:
            user = User(name="Ananya Sharma", email="demo@medimemory.test", password_hash=hash_password("Demo123!"), preferred_language="English")
            db.add(user); db.commit(); db.refresh(user)
            c = Consultation(user_id=user.id, doctor_name="Dr. Meera Iyer", hospital_name="Demo City Clinic",
                consultation_date=date(2026,11,15),
                original_text="DEMO ONLY — Fictional doctor-provided note: Take the prescribed medicine after breakfast. Return for a follow-up appointment on 30 November 2026. If you have questions about the medicine or experience unexpected symptoms, contact the clinic.",
                extracted_information="Follow-up date recorded in this fictional demo: 30 November 2026.",
                confirmation_status="confirmed", is_demo=True)
            db.add(c); db.commit(); db.refresh(c)
            med = Medication(user_id=user.id, consultation_id=c.id, medicine_name="Demo medicine (fictional)",
                doctor_prescribed_instruction="After breakfast — fictional demo wording only. Not a real prescription.",
                frequency="Once daily (demo only)", confirmation_status="confirmed")
            db.add(med)
            db.add(Appointment(user_id=user.id, doctor_name="Dr. Meera Iyer", hospital_name="Demo City Clinic",
                appointment_date=datetime(2026,11,30,10,30), notes="Fictional demo follow-up.", status="upcoming"))
            db.commit()
    finally: db.close()
seed_demo()

@app.get("/")
def root(): return {"name":"MediMemory API","docs":"/docs","status":"running"}
@app.get("/api/health")
def health(): return {"status":"ok","elevenlabs_configured":bool(os.getenv("ELEVENLABS_API_KEY")),"llm_configured":bool(os.getenv("OPENAI_API_KEY"))}

@app.post("/api/auth/register")
def register(payload: RegisterIn, db: Session=Depends(get_db)):
    email=payload.email.lower()
    if db.scalar(select(User).where(User.email==email)): raise HTTPException(409,"Email already registered")
    user=User(name=payload.name.strip(),email=email,password_hash=hash_password(payload.password))
    db.add(user); db.commit(); db.refresh(user)
    return {"access_token":create_token(user.id),"token_type":"bearer","user":{"id":user.id,"name":user.name,"email":user.email}}
@app.post("/api/auth/login")
def login(payload: LoginIn, db: Session=Depends(get_db)):
    user=db.scalar(select(User).where(User.email==payload.email.lower()))
    if not user or not verify_password(payload.password,user.password_hash): raise HTTPException(401,"Incorrect email or password")
    return {"access_token":create_token(user.id),"token_type":"bearer","user":{"id":user.id,"name":user.name,"email":user.email}}
@app.get("/api/auth/me")
def me(user: User=Depends(current_user)): return {"id":user.id,"name":user.name,"email":user.email,"preferred_language":user.preferred_language}

@app.get("/api/profile")
def profile(user: User=Depends(current_user)): return {"id":user.id,"name":user.name,"email":user.email,"preferred_language":user.preferred_language}
@app.put("/api/profile")
def update_profile(payload: ProfileIn, db: Session=Depends(get_db), user: User=Depends(current_user)):
    user.name=payload.name; user.preferred_language=payload.preferred_language; db.commit()
    return profile(user)

def consultation_dict(c):
    return {"id":c.id,"doctor_name":c.doctor_name,"hospital_name":c.hospital_name,"consultation_date":c.consultation_date.isoformat(),
            "original_text":c.original_text,"extracted_information":c.extracted_information,"confirmation_status":c.confirmation_status,"is_demo":c.is_demo}
@app.get("/api/consultations")
def list_consultations(db: Session=Depends(get_db), user: User=Depends(current_user)):
    return [consultation_dict(c) for c in db.scalars(select(Consultation).where(Consultation.user_id==user.id).order_by(Consultation.consultation_date.desc())).all()]
@app.post("/api/consultations")
def create_consultation(p: ConsultationIn, db: Session=Depends(get_db), user: User=Depends(current_user)):
    c=Consultation(user_id=user.id,**p.model_dump()); db.add(c); db.commit(); db.refresh(c); return consultation_dict(c)
@app.get("/api/consultations/{cid}")
def get_consultation(cid:int, db:Session=Depends(get_db), user:User=Depends(current_user)):
    c=db.scalar(select(Consultation).where(Consultation.id==cid,Consultation.user_id==user.id))
    if not c: raise HTTPException(404,"Consultation not found")
    return consultation_dict(c)
@app.put("/api/consultations/{cid}")
def update_consultation(cid:int,p:ConsultationIn,db:Session=Depends(get_db),user:User=Depends(current_user)):
    c=db.scalar(select(Consultation).where(Consultation.id==cid,Consultation.user_id==user.id))
    if not c: raise HTTPException(404,"Consultation not found")
    for k,v in p.model_dump().items(): setattr(c,k,v)
    db.commit(); db.refresh(c); return consultation_dict(c)
@app.delete("/api/consultations/{cid}")
def delete_consultation(cid:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    c=db.scalar(select(Consultation).where(Consultation.id==cid,Consultation.user_id==user.id))
    if not c: raise HTTPException(404,"Consultation not found")
    db.delete(c); db.commit(); return {"ok":True}

@app.post("/api/documents/upload")
async def upload_document(file: UploadFile=File(...), user:User=Depends(current_user)):
    data=await file.read()
    max_bytes=int(os.getenv("MAX_UPLOAD_MB","10"))*1024*1024
    if len(data)>max_bytes: raise HTTPException(413,"File exceeds upload size limit")
    if file.content_type not in ALLOWED: raise HTTPException(415,"Only PDF, PNG, JPEG and WEBP files are supported")
    try: extracted=extract_text(data,file.content_type)
    except Exception: raise HTTPException(400,"Could not read this document. Try another supported file.")
    upload_dir=Path(__file__).resolve().parents[1]/"uploads"; upload_dir.mkdir(exist_ok=True)
    safe_name=f"user{user.id}_{int(datetime.utcnow().timestamp())}_{Path(file.filename or 'upload').name[:80]}"
    (upload_dir/safe_name).write_bytes(data)
    return {"filename":file.filename,"extracted_text":extracted,"needs_review":True,
            "message":"Review this text against the original document. Nothing has been saved as confirmed." if extracted else "Image received. OCR is not configured; enter the instruction manually after reviewing the image."}

@app.post("/api/assistant/chat")
async def chat(p:ChatIn,db:Session=Depends(get_db),user:User=Depends(current_user)):
    hits=retrieve(db,user.id,p.question)
    answer,sources=await answer_question(p.question,hits,p.language)
    ref=", ".join([f"Consultation #{c.id} ({c.consultation_date})" for _,c in sources]) or "No confirmed source found"
    db.add(Conversation(user_id=user.id,consultation_id=sources[0][1].id if sources else None,question=p.question,answer=answer,source_reference=ref)); db.commit()
    return {"answer":answer,"sources":[{"id":c.id,"date":c.consultation_date.isoformat(),"doctor":c.doctor_name,"excerpt":c.original_text[:700]} for _,c in sources],"grounded":bool(sources),"mode":"configured-llm" if os.getenv("OPENAI_API_KEY") else "evidence-excerpt"}
@app.post("/api/assistant/explain")
async def explain(p:ExplainIn,db:Session=Depends(get_db),user:User=Depends(current_user)):
    c=db.scalar(select(Consultation).where(Consultation.id==p.consultation_id,Consultation.user_id==user.id,Consultation.confirmation_status=="confirmed"))
    if not c: raise HTTPException(404,"Confirmed consultation not found")
    answer,sources=await answer_question("Explain this instruction in simple language without adding medical advice: "+p.instruction,[(1,c)],user.preferred_language)
    return {"original":p.instruction,"explanation":answer,"source":{"id":c.id,"date":c.consultation_date.isoformat()}}
@app.post("/api/assistant/transcribe")
async def transcribe_audio(file:UploadFile=File(...),user:User=Depends(current_user)):
    data=await file.read()
    if len(data)>15*1024*1024: raise HTTPException(413,"Audio too large")
    result=await transcribe(data,file.filename or "recording.webm",file.content_type or "audio/webm")
    return result
@app.post("/api/assistant/speak")
async def speak_text(payload:dict,user:User=Depends(current_user)):
    text=payload.get("text","")
    if not isinstance(text,str) or not text.strip() or len(text)>4500: raise HTTPException(422,"Provide text up to 4500 characters")
    audio=await speak(text)
    return StreamingResponse(io.BytesIO(audio),media_type="audio/mpeg",headers={"Content-Disposition":"inline; filename=medimemory.mp3"})

@app.get("/api/medications")
def meds(db:Session=Depends(get_db),user:User=Depends(current_user)):
    return [{"id":m.id,"consultation_id":m.consultation_id,"medicine_name":m.medicine_name,"doctor_prescribed_instruction":m.doctor_prescribed_instruction,"frequency":m.frequency,"start_date":m.start_date.isoformat() if m.start_date else None,"end_date":m.end_date.isoformat() if m.end_date else None,"confirmation_status":m.confirmation_status} for m in db.scalars(select(Medication).where(Medication.user_id==user.id)).all()]
@app.post("/api/medications")
def add_med(p:MedicationIn,db:Session=Depends(get_db),user:User=Depends(current_user)):
    if p.consultation_id:
        c=db.scalar(select(Consultation).where(Consultation.id==p.consultation_id,Consultation.user_id==user.id))
        if not c: raise HTTPException(404,"Consultation not found")
    m=Medication(user_id=user.id,**p.model_dump()); db.add(m); db.commit(); db.refresh(m); return {"id":m.id,"medicine_name":m.medicine_name}
@app.put("/api/medications/{mid}")
def update_med(mid:int,p:MedicationIn,db:Session=Depends(get_db),user:User=Depends(current_user)):
    m=db.scalar(select(Medication).where(Medication.id==mid,Medication.user_id==user.id))
    if not m: raise HTTPException(404,"Medication not found")
    for k,v in p.model_dump().items(): setattr(m,k,v)
    db.commit(); return {"ok":True}
@app.delete("/api/medications/{mid}")
def delete_med(mid:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    m=db.scalar(select(Medication).where(Medication.id==mid,Medication.user_id==user.id))
    if not m: raise HTTPException(404,"Medication not found")
    db.delete(m); db.commit(); return {"ok":True}
@app.get("/api/reminders")
def reminders(db:Session=Depends(get_db),user:User=Depends(current_user)):
    rows=db.scalars(select(Reminder).where(Reminder.user_id==user.id)).all()
    return [{"id":r.id,"medication_id":r.medication_id,"medicine_name":r.medication.medicine_name,"reminder_time":r.reminder_time,"reminder_status":r.reminder_status} for r in rows]
@app.post("/api/reminders")
def add_reminder(p:ReminderIn,db:Session=Depends(get_db),user:User=Depends(current_user)):
    m=db.scalar(select(Medication).where(Medication.id==p.medication_id,Medication.user_id==user.id,Medication.confirmation_status=="confirmed"))
    if not m: raise HTTPException(400,"A reminder can only be created from a confirmed medication record")
    r=Reminder(user_id=user.id,**p.model_dump()); db.add(r); db.commit(); db.refresh(r); return {"id":r.id}
@app.put("/api/reminders/{rid}")
def update_reminder(rid:int,p:dict,db:Session=Depends(get_db),user:User=Depends(current_user)):
    r=db.scalar(select(Reminder).where(Reminder.id==rid,Reminder.user_id==user.id))
    if not r: raise HTTPException(404,"Reminder not found")
    if p.get("reminder_status") in ("active","completed","missed","inactive"): r.reminder_status=p["reminder_status"]
    db.commit(); return {"ok":True}
@app.delete("/api/reminders/{rid}")
def delete_reminder(rid:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    r=db.scalar(select(Reminder).where(Reminder.id==rid,Reminder.user_id==user.id))
    if not r: raise HTTPException(404,"Reminder not found")
    db.delete(r); db.commit(); return {"ok":True}

@app.get("/api/appointments")
def appointments(db:Session=Depends(get_db),user:User=Depends(current_user)):
    return [{"id":a.id,"doctor_name":a.doctor_name,"hospital_name":a.hospital_name,"appointment_date":a.appointment_date.isoformat(),"notes":a.notes,"status":a.status} for a in db.scalars(select(Appointment).where(Appointment.user_id==user.id).order_by(Appointment.appointment_date)).all()]
@app.post("/api/appointments")
def add_appointment(p:AppointmentIn,db:Session=Depends(get_db),user:User=Depends(current_user)):
    a=Appointment(user_id=user.id,**p.model_dump()); db.add(a); db.commit(); db.refresh(a); return {"id":a.id}
@app.put("/api/appointments/{aid}")
def update_appointment(aid:int,p:AppointmentIn,db:Session=Depends(get_db),user:User=Depends(current_user)):
    a=db.scalar(select(Appointment).where(Appointment.id==aid,Appointment.user_id==user.id))
    if not a: raise HTTPException(404,"Appointment not found")
    for k,v in p.model_dump().items(): setattr(a,k,v)
    db.commit(); return {"ok":True}
@app.delete("/api/appointments/{aid}")
def delete_appointment(aid:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    a=db.scalar(select(Appointment).where(Appointment.id==aid,Appointment.user_id==user.id))
    if not a: raise HTTPException(404,"Appointment not found")
    db.delete(a); db.commit(); return {"ok":True}

@app.get("/api/caregivers")
def caregivers(db:Session=Depends(get_db),user:User=Depends(current_user)):
    return [{"id":c.id,"caregiver_email":c.caregiver_email,"permissions":c.permissions,"access_status":c.access_status} for c in db.scalars(select(Caregiver).where(Caregiver.patient_id==user.id)).all()]
@app.post("/api/caregivers")
def add_caregiver(p:dict,db:Session=Depends(get_db),user:User=Depends(current_user)):
    email=p.get("caregiver_email","").strip().lower()
    if "@" not in email: raise HTTPException(422,"Valid caregiver email required")
    c=Caregiver(patient_id=user.id,caregiver_email=email,permissions=",".join(p.get("permissions",["consultations"])),access_status="pending")
    db.add(c); db.commit(); db.refresh(c); return {"id":c.id,"access_status":"pending"}
@app.delete("/api/caregivers/{cid}")
def revoke_caregiver(cid:int,db:Session=Depends(get_db),user:User=Depends(current_user)):
    c=db.scalar(select(Caregiver).where(Caregiver.id==cid,Caregiver.patient_id==user.id))
    if not c: raise HTTPException(404,"Caregiver not found")
    db.delete(c); db.commit(); return {"ok":True}

@app.get("/api/dashboard")
def dashboard(db:Session=Depends(get_db),user:User=Depends(current_user)):
    consultations=db.scalars(select(Consultation).where(Consultation.user_id==user.id)).all()
    meds=db.scalars(select(Medication).where(Medication.user_id==user.id,Medication.confirmation_status=="confirmed")).all()
    rem=db.scalars(select(Reminder).where(Reminder.user_id==user.id,Reminder.reminder_status=="active")).all()
    apps=db.scalars(select(Appointment).where(Appointment.user_id==user.id,Appointment.status=="upcoming").order_by(Appointment.appointment_date)).all()
    return {"consultation_count":len(consultations),"medication_count":len(meds),"active_reminders":len(rem),
            "upcoming_appointments":[{"id":a.id,"doctor_name":a.doctor_name,"hospital_name":a.hospital_name,"appointment_date":a.appointment_date.isoformat()} for a in apps[:3]],
            "recent_consultations":[consultation_dict(c) for c in sorted(consultations,key=lambda x:x.consultation_date,reverse=True)[:3]]}
