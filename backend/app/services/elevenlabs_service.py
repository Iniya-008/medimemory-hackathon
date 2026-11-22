import os
import httpx
from fastapi import HTTPException

BASE = "https://api.elevenlabs.io/v1"

def _key():
    key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not key:
        raise HTTPException(503, "ElevenLabs is not configured. Add ELEVENLABS_API_KEY to backend/.env.")
    return key

async def transcribe(audio: bytes, filename: str, content_type: str):
    key = _key()
    data = {"model_id": "scribe_v2"}
    files = {"file": (filename, audio, content_type or "audio/webm")}
    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(f"{BASE}/speech-to-text", headers={"xi-api-key": key}, data=data, files=files)
    if response.status_code >= 400:
        raise HTTPException(502, f"ElevenLabs transcription failed ({response.status_code}). Check API access and audio format.")
    payload = response.json()
    return {"text": payload.get("text", ""), "language_code": payload.get("language_code")}

async def speak(text: str, voice_id: str | None = None):
    key = _key()
    voice = voice_id or os.getenv("ELEVENLABS_VOICE_ID", "").strip()
    if not voice:
        raise HTTPException(503, "Set ELEVENLABS_VOICE_ID in backend/.env.")
    model = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(
            f"{BASE}/text-to-speech/{voice}",
            headers={"xi-api-key": key, "Accept": "audio/mpeg", "Content-Type": "application/json"},
            json={"text": text[:4500], "model_id": model,
                  "voice_settings": {"stability": 0.45, "similarity_boost": 0.75}}
        )
    if response.status_code >= 400:
        raise HTTPException(502, f"ElevenLabs speech generation failed ({response.status_code}).")
    return response.content
