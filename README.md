# MediMemory — Never Miss What Your Doctor Told You

A voice-first post-consultation memory companion. This hackathon prototype stores patient-owned consultation notes, retrieves only confirmed instructions for grounded Q&A, and integrates ElevenLabs STT/TTS through the backend when credentials are configured.

> **Safety:** This is a prototype, not a medical device or medical-advice service. Demo records are fictional. Never use it to diagnose, prescribe, or change treatment. Verify every instruction with the original prescription/clinician.

## Features
- React + Vite responsive app: dashboard, consultation memory, explain, voice assistant, reminders, follow-ups, caregiver prototype, profile.
- FastAPI backend, SQLAlchemy/SQLite, bcrypt password hashing, JWT authentication, ownership checks.
- Demo account seeded automatically: `demo@medimemory.test` / `Demo123!`
- Consultation CRUD and PDF/image upload (text extraction where supported; OCR is optional and not silently assumed).
- Confirm-before-use workflow for uploaded/extracted content.
- Context-grounded assistant: SQLite-backed lexical retrieval from confirmed consultation records; optional OpenAI-compatible LLM via server-side environment variables; safe extractive fallback if no LLM configured.
- ElevenLabs speech-to-text and text-to-speech REST integration (real API calls when configured).
- Medication/reminder and appointment CRUD; browser in-app due reminder checks while app is open.
- Caregiver invitation/access prototype records permissions but does not implement external caregiver login.
- API docs at `/docs`.

## Run locally (Windows PowerShell)
### 1. Backend
```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload
```
Backend: http://127.0.0.1:8000

### 2. Frontend (new terminal)
```powershell
cd frontend
npm install
copy .env.example .env
npm run dev
```
Frontend: http://localhost:5173

The frontend proxies `/api` to `http://127.0.0.1:8000`. If changing the backend host, update `frontend/vite.config.js`.

## Environment configuration
Edit `backend/.env`:
- `SECRET_KEY`: replace with a long random secret before any shared deployment.
- `ELEVENLABS_API_KEY`: obtain from the ElevenLabs dashboard. Keep it only on the backend.
- `ELEVENLABS_VOICE_ID`: choose a voice available to your account.
- `OPENAI_API_KEY` and `OPENAI_MODEL`: optional; used for contextual explanation/Q&A. If omitted, the app uses a conservative evidence-only fallback. LLM output is always constrained to provided confirmed source text.
- `CORS_ORIGINS`: comma-separated frontend origins.

No ElevenLabs key means voice buttons return a clear configuration error; the app does not fake STT/TTS or substitute browser speech synthesis.

## Demo
Use **Continue with demo account** on the login screen or credentials above. The fictional patient is Ananya Sharma. The sample consultation is clearly marked DEMO and not medically validated.

## API overview
- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`
- `GET/POST /api/consultations`, `GET/PUT/DELETE /api/consultations/{id}`
- `POST /api/documents/upload` (multipart `file`)
- `POST /api/assistant/chat`, `/api/assistant/explain`, `/api/assistant/transcribe`, `/api/assistant/speak`
- `GET/POST /api/medications`, `PUT/DELETE /api/medications/{id}`
- `GET/POST /api/reminders`, `PUT/DELETE /api/reminders/{id}`
- `GET/POST /api/appointments`, `PUT/DELETE /api/appointments/{id}`
- `GET/POST /api/caregivers`, `DELETE /api/caregivers/{id}`
- `GET/PUT /api/profile`, `GET /api/dashboard`

## Security and prototype limitations
- Password hashes use bcrypt; API uses signed bearer JWTs; patient ownership is derived from the token, not a client-supplied user ID.
- Uploaded files are size/type limited and stored under `backend/uploads`; avoid deploying with real PHI without a formal security, privacy, legal and compliance review.
- SQLite is suitable for a local demo, not concurrent production use. Use HTTPS, managed secrets, PostgreSQL, audit logging, retention controls, encryption-at-rest, backups and a formal threat model before real patient use.
- Reminder notifications are in-app while the app is open; background delivery is not guaranteed.
- Caregiver module is a patient-side prototype only; it does not grant an external account access.
- OCR accuracy is not guaranteed. Extracted text is unverified until patient confirmation.
- LLM requests send only selected confirmed source excerpts and the current question to the configured provider. Review provider privacy/data terms before use.
- ElevenLabs and LLM integrations require valid credentials and network access.

## Tests
```powershell
cd backend
pip install -r requirements.txt
pytest -q
```

## Hackathon demo script (3 minutes)
1. Login using demo account and point out the fictional/demo banner.
2. Dashboard: show consultation count, next follow-up and reminders loaded from SQLite.
3. Open Consultation Memory; display original doctor-provided text and its confirmation state.
4. Add a consultation or upload a sample document; explain that extraction remains pending review until explicitly confirmed.
5. Ask the assistant: “What did my doctor say about the follow-up?” Show the source consultation reference and evidence-based answer.
6. Click Explain on a confirmed instruction.
7. If ElevenLabs credentials are configured, record a question and play the real ElevenLabs-generated answer; otherwise show the honest setup status.
8. Show reminders and follow-up tracker. Close by reinforcing that MediMemory remembers and explains existing clinician instructions; it never diagnoses or prescribes.

## Architecture
See `docs/architecture.md` and `docs/api_documentation.md`.

## Official ElevenLabs references
- [Speech-to-text API](https://elevenlabs.io/docs/api-reference/speech-to-text/convert) — multipart upload to `/v1/speech-to-text`; this project uses `scribe_v2`.
- [Text-to-speech API](https://elevenlabs.io/docs/api-reference/text-to-speech) — direct synthesis via `/v1/text-to-speech/{voice_id}`.
- [Speech-to-text overview and healthcare notes](https://elevenlabs.io/docs/overview/capabilities/speech-to-text) — check supported languages and contractual requirements before handling health data.
