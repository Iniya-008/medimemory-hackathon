"""Privacy shield: remove personal identifiers before any text leaves our server for an AI service.

What is removed (replaced by a placeholder such as [PHONE]):
  phone numbers, email addresses, Aadhaar-style 12-digit numbers, ABHA numbers (14 digits) and ABHA addresses,
  the patient's own name, dates of birth, and PIN codes written next to the word "PIN".
Doctors' names, medicine names, doses and dates of visits are kept: they are needed to understand the instructions.
The original text stays encrypted on our server; only the redacted copy is sent.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

LABELS = {
    "PHONE": "phone number", "EMAIL": "email address", "AADHAAR": "Aadhaar-style number", "ABHA": "ABHA number or address",
    "NAME": "patient name", "DOB": "date of birth", "PIN": "PIN code",
}

_RULES: list[tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"\b[\w.+-]+@(?!abdm\b|sbx\b)[\w-]+\.[\w.-]+\b", re.I)),
    ("ABHA", re.compile(r"\b[\w.]{3,}@(abdm|sbx)\b", re.I)),
    ("ABHA", re.compile(r"\b\d{2}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b")),
    ("AADHAAR", re.compile(r"\b[2-9]\d{3}[-\s]?\d{4}[-\s]?\d{4}\b")),
    ("PHONE", re.compile(r"(?<![\w.])(?:\+?91[-\s]?|0)?[6-9]\d{4}[-\s]?\d{5}(?![\w.])")),
    ("DOB", re.compile(r"\b(?:d\.?o\.?b\.?|date of birth|born on)\s*[:\-]?\s*\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b", re.I)),
    ("PIN", re.compile(r"\b(?:pin(?:\s?code)?)\s*[:\-]?\s*\d{6}\b", re.I)),
]


@dataclass
class Redaction:
    text: str
    counts: Counter = field(default_factory=Counter)

    def summary(self) -> list[dict]:
        return [{"kind": k, "label": LABELS.get(k, k.lower()), "count": n} for k, n in sorted(self.counts.items())]


def redact(text: str, names: list[str] | None = None) -> Redaction:
    out, counts = text or "", Counter()
    for kind, rx in _RULES:
        out, n = rx.subn(f"[{kind}]", out)
        counts[kind] += n
    for nm in sorted({n.strip() for n in (names or []) if n and len(n.strip()) >= 3}, key=len, reverse=True):
        rx = re.compile(rf"(?<!\w){re.escape(nm)}(?!\w)", re.I)
        out, n = rx.subn("[NAME]", out)
        counts["NAME"] += n
    return Redaction(out, +counts)


def merge(*reports: list[dict]) -> list[dict]:
    c: Counter = Counter()
    for r in reports:
        for item in r or []:
            c[item["kind"]] += item["count"]
    return [{"kind": k, "label": LABELS.get(k, k.lower()), "count": n} for k, n in sorted(c.items()) if n]


def patient_names(user) -> list[str]:
    full = (getattr(user, "full_name", "") or "").strip()
    parts = [p for p in full.split() if len(p) >= 3]
    return [full, *parts] if full else []
