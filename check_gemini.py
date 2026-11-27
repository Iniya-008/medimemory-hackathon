"""Checks the Gemini settings in .env and says exactly what is wrong.

Run from the project folder:   .venv\\Scripts\\python check_gemini.py
It never prints your key.
"""
import json
import pathlib
import sys

try:
    import httpx
    from dotenv import dotenv_values
except ImportError:
    sys.exit("Run this with the project's Python:  .venv\\Scripts\\python check_gemini.py")

root = pathlib.Path(__file__).resolve().parent
env = {**dotenv_values(root / ".env"), **dotenv_values(root / "backend" / ".env")}
key = (env.get("LLM_API_KEY") or "").strip()
base = (env.get("LLM_BASE_URL") or "").strip().rstrip("/")
model = (env.get("LLM_MODEL") or "").strip()

print("LLM_BASE_URL :", base or "(empty)")
print("LLM_MODEL    :", model or "(empty)")
print("LLM_API_KEY  :", f"set, {len(key)} characters, starts with '{key[:4]}...'" if key else "(empty)")
print()

if not key:
    sys.exit("PROBLEM: LLM_API_KEY is empty. Paste your Gemini key from aistudio.google.com into .env")
if " " in key or key.startswith(("'", '"')):
    sys.exit("PROBLEM: the key has spaces or quotes around it. Write it as LLM_API_KEY=yourkey")
if "generativelanguage.googleapis.com/v1beta/openai" not in base:
    sys.exit("PROBLEM: LLM_BASE_URL must be https://generativelanguage.googleapis.com/v1beta/openai")


def ask(m):
    r = httpx.post(f"{base}/chat/completions",
                   headers={"Authorization": f"Bearer {key}"},
                   json={"model": m, "response_format": {"type": "json_object"},
                         "messages": [{"role": "user", "content": 'Reply with JSON {"ok": true}'}]},
                   timeout=40)
    msg = ""
    if r.status_code != 200:
        try:
            body = r.json()
            body = body[0] if isinstance(body, list) else body
            msg = (body.get("error") or {}).get("message", "")
        except Exception:
            msg = r.text[:300]
    return r.status_code, msg


for m in [model, "gemini-3.8-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash"]:
    if not m:
        continue
    code, msg = ask(m)
    print(f"{m:28s} -> {code} {'OK' if code == 200 else msg[:200]}")
    if code == 200:
        if m != model:
            print(f"\nFIX: set LLM_MODEL={m} in .env, save, and restart start_all.bat")
        else:
            print("\nGemini works. Restart start_all.bat and try again.")
        sys.exit(0)
    if code in (400, 401, 403) and "model" not in msg.lower():
        print("\nPROBLEM: Google rejected the KEY (not the model).")
        print("FIX: go to aistudio.google.com -> Get API key -> Create API key.")
        print("     It should start with 'AIza'. Paste it as LLM_API_KEY=... and restart.")
        sys.exit(1)
    if code == 429:
        print("   (quota/rate limit on this model, trying the next one)")

print("\nNo model worked. Send a screenshot of this window.")
