# API documentation

Base URL: `http://127.0.0.1:8000`. Interactive OpenAPI: `/docs`.

All routes except `/`, `/api/health`, register and login require `Authorization: Bearer <access_token>`.

| Method | Route | Purpose |
|---|---|---|
| POST | `/api/auth/register` | Create patient account |
| POST | `/api/auth/login` | Login |
| GET | `/api/auth/me` | Current user |
| GET/PUT | `/api/profile` | Profile |
| GET/POST | `/api/consultations` | List/create consultations |
| GET/PUT/DELETE | `/api/consultations/{id}` | Read/update/delete owned consultation |
| POST | `/api/documents/upload` | Upload PDF/image; returns unconfirmed extracted text |
| POST | `/api/assistant/chat` | Grounded question answering |
| POST | `/api/assistant/explain` | Explain confirmed instruction |
| POST | `/api/assistant/transcribe` | ElevenLabs speech-to-text |
| POST | `/api/assistant/speak` | ElevenLabs text-to-speech |
| GET/POST/PUT/DELETE | `/api/medications[/{id}]` | Medication records |
| GET/POST/PUT/DELETE | `/api/reminders[/{id}]` | Reminders |
| GET/POST/PUT/DELETE | `/api/appointments[/{id}]` | Follow-up appointments |
| GET/POST/DELETE | `/api/caregivers[/{id}]` | Prototype caregiver records |
| GET | `/api/dashboard` | Patient dashboard counts and recent data |

The request/response schemas are defined in `backend/app/schemas.py` and endpoint implementations in `backend/app/main.py`.
