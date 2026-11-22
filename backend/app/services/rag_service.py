import os, re
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import Consultation

STOP = {"what","when","where","which","about","from","with","that","this","your","have","does","did","doctor","tell","please","could","would","should","the","and","for","are","was","were","can","you","my"}
def retrieve(db: Session, user_id: int, question: str):
    records = db.scalars(select(Consultation).where(
        Consultation.user_id == user_id,
        Consultation.confirmation_status == "confirmed"
    ).order_by(Consultation.consultation_date.desc())).all()
    terms = {t.lower() for t in re.findall(r"[a-zA-Z0-9]+", question) if len(t) > 2 and t.lower() not in STOP}
    scored = []
    for c in records:
        text = f"{c.original_text}\n{c.extracted_information}"
        tokens = set(t.lower() for t in re.findall(r"[a-zA-Z0-9]+", text))
        score = len(terms & tokens)
        if score or not terms:
            scored.append((score, c))
    scored.sort(key=lambda x: (x[0], x[1].consultation_date), reverse=True)
    return [(s,c) for s,c in scored[:3] if s > 0] or ([(0,scored[0][1])] if scored and not terms else [])

async def answer_question(question: str, sources: list, language: str = "English"):
    if not sources:
        return "I cannot verify that information from your saved consultation. Please contact your doctor or pharmacist for clarification.", []
    excerpts = []
    for _, c in sources:
        excerpts.append(f"Consultation #{c.id} ({c.consultation_date}): {c.original_text[:3500]}\nAdditional confirmed details: {c.extracted_information[:1500]}")
    context = "\n\n".join(excerpts)
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if api_key:
        base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        system = ("You are MediMemory, a post-consultation memory assistant. Answer only from the supplied confirmed records. "
                  "Do not diagnose, prescribe, change doses, infer missing schedules, or give new medical advice. "
                  "If the records do not answer the question, say exactly that you cannot verify it and advise contacting the doctor/pharmacist. "
                  "Keep important details unchanged. State the consultation source ID. Reply in " + language + ".")
        async with httpx.AsyncClient(timeout=45) as client:
            r = await client.post(f"{base}/chat/completions", headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "temperature": 0.1, "messages":[
                    {"role":"system","content":system},
                    {"role":"user","content":f"CONFIRMED RECORDS:\n{context}\n\nQUESTION: {question}"}
                ]})
        if r.status_code >= 400:
            return "I could not reach the configured explanation service. Please try again or review the original consultation.", sources
        return r.json()["choices"][0]["message"]["content"], sources
    # Honest evidence-only fallback: quote matching source text, not a pretend AI answer.
    q = question.lower()
    chunks = []
    for _, c in sources:
        text = c.original_text.strip()
        if text:
            chunks.append(f"From consultation #{c.id} ({c.consultation_date}): “{text[:900]}”")
    return ("I found this in your confirmed consultation record. " + "\n".join(chunks) +
            "\n\nThis is a source excerpt, not a medical interpretation. If it does not answer your question, please contact your doctor or pharmacist."), sources
