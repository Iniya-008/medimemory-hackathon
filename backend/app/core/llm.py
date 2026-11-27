"""Minimal JSON chat client for any OpenAI-compatible endpoint (OpenAI, Gemini, Groq...)."""
from __future__ import annotations

import json
import re

import httpx

from app.core.config import settings


class LLMUnavailable(Exception):
    pass


def _parse(raw: str) -> dict:
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            raise
        return json.loads(m.group(0))


def chat_json(system: str, user: str | list, timeout: float = 45) -> dict:
    if not settings.llm_enabled:
        raise LLMUnavailable("No LLM is configured on the server (set LLM_API_KEY, LLM_BASE_URL, LLM_MODEL).")
    try:
        resp = httpx.post(
            f"{settings.llm_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json={"model": settings.llm_model, "temperature": 0.1,
                  "response_format": {"type": "json_object"},
                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
            timeout=timeout,
        )
        resp.raise_for_status()
        return _parse(resp.json()["choices"][0]["message"]["content"])
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        hint = {400: "check LLM_API_KEY / LLM_MODEL", 401: "bad LLM_API_KEY", 403: "bad LLM_API_KEY",
                404: "wrong LLM_MODEL name", 429: "quota hit, try another LLM_MODEL"}.get(code, "")
        print(f"[LLM] HTTP {code} from {settings.llm_base_url} model={settings.llm_model}: "
              f"{exc.response.text[:300]}", flush=True)
        raise LLMUnavailable(f"LLM call failed: HTTP {code} {hint}".strip()) from exc
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise LLMUnavailable(f"LLM call failed: {type(exc).__name__}") from exc
