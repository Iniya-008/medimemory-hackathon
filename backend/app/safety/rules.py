"""Safety rules for the after-visit assistant. Enforced in code, before any record lookup or LLM call.

Order of checks for every question:
1. EMERGENCY  -> fixed "call 108" message. Records are NOT consulted.
2. REFUSAL    -> diagnosis, new medicines, dose changes. Fixed message pointing to the doctor/pharmacist.
3. otherwise  -> the caller may answer, but only from the patient's CONFIRMED instructions.

The Tamil keywords and messages below were written by the development team and are
NOT yet verified by a native-speaker reviewer (see TAMIL_TEXT_VERIFIED).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

TAMIL_TEXT_VERIFIED = False

# ------------------------------------------------------------------ fixed messages
MESSAGES = {
    "emergency": {
        "en": "This could be an emergency. Please call 108 or go to the nearest hospital now. "
              "I can't help with emergencies.",
        "ta": "இது அவசர நிலையாக இருக்கலாம். உடனே 108-ஐ அழைக்கவும் அல்லது அருகிலுள்ள மருத்துவமனைக்குச் செல்லவும்.",
    },
    "dose_change": {
        "en": "I can't advise changing, skipping or stopping a medicine or its dose. Please ask your doctor or pharmacist.",
        "ta": "மருந்தின் அளவை மாற்றுவது, தவிர்ப்பது அல்லது நிறுத்துவது பற்றி என்னால் ஆலோசனை சொல்ல முடியாது. உங்கள் மருத்துவர் அல்லது மருந்தாளரிடம் கேளுங்கள்.",
    },
    "new_medicine": {
        "en": "I can't suggest new medicines. Please ask your doctor or pharmacist.",
        "ta": "புதிய மருந்துகளை என்னால் பரிந்துரைக்க முடியாது. உங்கள் மருத்துவர் அல்லது மருந்தாளரிடம் கேளுங்கள்.",
    },
    "diagnosis": {
        "en": "I can't diagnose or judge your health. I can only repeat what your doctor told you. Please ask your doctor.",
        "ta": "என்னால் நோயைக் கண்டறியவோ உங்கள் உடல்நிலையை மதிப்பிடவோ முடியாது. மருத்துவர் சொன்னதை மட்டுமே திரும்பச் சொல்ல முடியும். உங்கள் மருத்துவரிடம் கேளுங்கள்.",
    },
    "not_found": {
        "en": "That isn't in your saved instructions. Please ask your doctor.",
        "ta": "அது நீங்கள் சேமித்த அறிவுரைகளில் இல்லை. உங்கள் மருத்துவரிடம் கேளுங்கள்.",
    },
}


def message(kind: str, lang: str = "en") -> str:
    m = MESSAGES[kind]
    return m.get(lang) or m["en"]


# ------------------------------------------------------------------ patterns
_MED = r"(dose|dosage|tablets?|pills?|medicines?|medication|meds|insulin|units?|mg|capsules?|injection)"

EMERGENCY = [
    r"\bchest (pain|tightness|pressure)\b", r"\bpain in (my |the )?chest\b", r"\bheart attack\b",
    r"\b(can'?t|cannot|unable to|hard to|difficult(y)? (in )?|trouble) breath", r"\bbreathless", r"\bshort(ness)? of breath\b",
    r"\bfaint(ed|ing)?\b", r"\bpassed out\b", r"\bunconscious\b", r"\bcollaps(e|ed|ing)\b",
    r"\b(severe|heavy|a lot of|lots of) bleeding\b", r"\bbleeding (heavily|a lot|won'?t stop|that won'?t stop)\b",
    r"\b(vomit(ing|ed)?|cough(ing|ed)?) (up )?blood\b",
    r"\bstroke\b", r"\bface (is )?droop", r"\bslurred speech\b", r"\bcan'?t (move|lift|feel) (my )?(arm|leg|face|side)\b",
    r"\b(seizure|fits|convulsion)", r"\boverdose\b", r"\btook too many\b",
    r"\bsuicid", r"\bkill myself\b", r"\bend my life\b",
    # Tamil (unverified): chest pain, breathlessness, fainting/unconscious, bleeding, stroke/paralysis, fits
    r"நெஞ்சு ?வலி", r"நெஞ்சுவலி", r"மார்பு ?வலி", r"மூச்சு ?(த்)?திணறல்", r"மூச்சு விட முடிய",
    r"மயக்கம்", r"மயங்கி", r"ரத்தப்போக்கு", r"இரத்தப்போக்கு", r"பக்கவாதம்", r"வலிப்பு",
]

DOSE_CHANGE = [
    r"\b(double|increase|decrease|reduce|halve|raise|lower|change|adjust|cut)\b.{0,30}\b(dose|dosage|insulin|units?|mg)\b",
    r"\b(double|increase|decrease|reduce|halve|change|adjust|cut)\s+(the |my |this |that )?(tablets?|pills?|medicines?|medication|meds|capsules?)\b",
    r"\b(more|less|extra|another|fewer)\s+(of )?(the |my |this )?(dose|dosage|tablets?|pills?|medicines?|medication|meds|insulin|capsules?)\b",
    r"\b(dose|dosage)\b.{0,30}\b(double|increase|decrease|reduce|halve|higher|lower|change)\b",
    r"\b(stop|skip|quit|discontinue)\b.{0,25}\b(taking|tablets?|pills?|medicines?|medication|meds|insulin|it|them)\b",
    r"\btake (two|2|three|3|an extra|another|one more|double)\b",
    r"\bmissed\b.{0,40}\b(dose|tablets?|pills?|medicines?|insulin|it)\b.{0,40}\b(now|should|can|what do)\b",
    # Tamil (unverified): stop, increase, dose
    r"நிறுத்த", r"அதிகம(ா|ாக)?.{0,15}(மாத்திரை|மருந்து)", r"டோஸ்",
]

NEW_MEDICINE = [
    r"\bwhat (should|can|do) i take\b", r"\b(which|what) (medicine|tablet|pill|drug|syrup)s?\b.{0,20}\b(for|should|can|to)\b",
    r"\b(recommend|suggest|prescribe)\b.{0,20}\b(medicine|tablet|pill|drug|something)\b",
    r"\b(painkiller|antibiotic)s?\b.{0,20}\b(for|should|can)\b", r"\bcan i (take|have) (a |an |some )?(paracetamol|crocin|dolo|antibiotic|painkiller|ibuprofen)\b",
    r"\bfor (my|a|the) (headache|fever|cold|cough|pain)\b.{0,20}\b(take|medicine|tablet)\b",
    # Tamil (unverified): "what tablet", "what medicine"
    r"என்ன மாத்திரை", r"என்ன மருந்து",
]

DIAGNOSIS = [
    r"\bdo i have\b", r"\bdiagnos", r"\bwhat (disease|illness|condition|problem) (do i|have i|is)\b",
    r"\bis (it|this|my) (cancer|serious|dangerous|diabetes|infection)\b",
    r"\bis my (bp|blood pressure|sugar|blood sugar|report|result|level|hba1c|cholesterol)\b.{0,20}\b(normal|high|low|bad|ok(ay)?|dangerous|fine|good)\b",
    r"\bam i (sick|ok(ay)?|fine|diabetic|healthy|going to)\b", r"\bwhy (do|am) i (feel|have|get)\b",
    # Tamil (unverified): "what disease", "is it serious"
    r"என்ன நோய்", r"ஆபத்தா",
]

_COMPILED = {
    "emergency": [re.compile(p, re.I) for p in EMERGENCY],
    "dose_change": [re.compile(p, re.I) for p in DOSE_CHANGE],
    "new_medicine": [re.compile(p, re.I) for p in NEW_MEDICINE],
    "diagnosis": [re.compile(p, re.I) for p in DIAGNOSIS],
}


@dataclass
class Verdict:
    kind: str            # emergency | dose_change | new_medicine | diagnosis | ok
    pattern: str | None = None

    @property
    def blocked(self) -> bool:
        return self.kind != "ok"


def classify(question: str) -> Verdict:
    q = " ".join((question or "").split())
    for kind in ("emergency", "dose_change", "new_medicine", "diagnosis"):
        for rx in _COMPILED[kind]:
            if rx.search(q):
                return Verdict(kind, rx.pattern)
    return Verdict("ok")


# ------------------------------------------------------------------ small talk
# "thank you", "bye", "hello"... are not questions about the records, so they get a friendly fixed
# reply instead of "That isn't in your saved instructions". Only when the WHOLE message is small talk:
# "thanks, when do I take Metformin?" still goes to the normal search.
SMALL_TALK_MESSAGES = {
    "greeting": {
        "en": "Hello! Ask me anything about what your doctor told you.",
        "ta": "வணக்கம்! உங்கள் மருத்துவர் சொன்னதைப் பற்றி எதுவும் கேளுங்கள்.",
        "hi": "नमस्ते! अपने डॉक्टर की बताई किसी भी बात के बारे में पूछिए।",
    },
    "thanks": {
        "en": "You're welcome! Ask me again whenever you need.",
        "ta": "மகிழ்ச்சி! தேவைப்படும்போது மீண்டும் கேளுங்கள்.",
        "hi": "आपका स्वागत है! जब भी ज़रूरत हो, फिर से पूछिए।",
    },
    "goodbye": {
        "en": "Goodbye! Take care, and follow your doctor's advice.",
        "ta": "சரி, போய் வாருங்கள்! உடம்பைப் பார்த்துக் கொள்ளுங்கள்.",
        "hi": "अलविदा! अपना ध्यान रखिए।",
    },
    "ack": {
        "en": "Okay. Ask me whenever you need.",
        "ta": "சரி. தேவைப்படும்போது கேளுங்கள்.",
        "hi": "ठीक है। जब भी ज़रूरत हो, पूछिए।",
    },
    "help": {
        "en": "I repeat only what your doctor told you, in your language. For example, ask: when should I take Metformin?",
        "ta": "உங்கள் மருத்துவர் சொன்னதை மட்டும் உங்கள் மொழியில் திரும்பச் சொல்வேன். உதாரணமாக: மெட்ஃபார்மின் எப்போது சாப்பிட வேண்டும் என்று கேளுங்கள்.",
        "hi": "मैं सिर्फ़ वही दोहराता हूँ जो आपके डॉक्टर ने बताया, आपकी भाषा में। जैसे पूछिए: मेटफॉर्मिन कब लेनी है?",
    },
}
MESSAGES.update(SMALL_TALK_MESSAGES)
SMALL_TALK = tuple(SMALL_TALK_MESSAGES)

_TALK = {
    "goodbye": ["bye bye", "bye", "goodbye", "good bye", "good night", "see you", "see you later", "take care",
                "that's all", "thats all", "that is all", "nothing else", "nothing more", "i am done", "i'm done",
                "alvida", "chalo bye", "tata", "poittu varen", "poitu varen", "povom",
                "போயிட்டு வரேன்", "போய்ட்டு வரேன்", "போய் வருகிறேன்", "போய் வரேன்", "பை பை", "பை", "அவ்வளவு தான்", "அவ்வளவுதான்",
                "அலவிதா", "अलविदा", "बाय", "शुभ रात्रि", "बस इतना ही", "ठीक है बाय"],
    "thanks": ["thank you very much", "thank you so much", "thank you", "thanks a lot", "thanks", "thank u", "thx", "ty",
               "nandri", "nanri", "romba nandri", "dhanyavad", "dhanyawad", "shukriya",
               "ரொம்ப நன்றி", "மிக்க நன்றி", "நன்றி", "धन्यवाद", "शुक्रिया", "बहुत धन्यवाद",
               "ధన్యవాదాలు", "ಧನ್ಯವಾದ", "നന്ദി", "ধন্যবাদ", "ਧੰਨਵਾਦ", "આભાર"],
    "help": ["what can you do", "who are you", "how do i use this", "how to use this", "help me", "help",
             "நீ யார்", "நீங்கள் யார்", "நீங்க யாரு", "என்ன செய்ய முடியும்", "உதவி",
             "आप कौन हैं", "तुम कौन हो", "आप क्या कर सकते हैं", "मदद"],
    "greeting": ["good morning", "good afternoon", "good evening", "hello", "hey", "hii", "hi", "how are you",
                 "vanakkam", "namaste", "namaskar", "kaise ho", "eppadi irukeenga",
                 "வணக்கம்", "எப்படி இருக்கீங்க", "எப்படி இருக்கிறீர்கள்", "நமஸ்தே", "नमस्ते", "नमस्कार", "कैसे हो", "आप कैसे हैं",
                 "నమస్కారం", "ನಮಸ್ಕಾರ", "നമസ്കാരം", "নমস্কার", "ਸਤ ਸ੍ਰੀ ਅਕਾਲ", "નમસ્તે"],
    "ack": ["okay", "ok", "okk", "fine", "got it", "understood", "alright", "all right", "hmm", "sure", "yes", "no",
            "sari", "seri", "purinjathu", "theek hai", "thik hai", "achha", "acha",
            "சரி", "சரிங்க", "புரிந்தது", "புரிஞ்சது", "ஆமாம்", "இல்லை", "ठीक है", "अच्छा", "हाँ", "नहीं"],
}
_FILLERS = ["sir", "madam", "mam", "doctor", "amma", "appa", "ji", "da", "please", "very", "much", "so", "and", "then",
            "now", "for", "the", "help", "your", "you", "ங்க", "ம்மா", "சார்", "जी", "और"]
_PRIORITY = ("goodbye", "thanks", "help", "greeting", "ack")


def _strip(text: str, phrase: str) -> tuple[str, bool]:
    if phrase.isascii():
        new, n = re.subn(rf"(?<![a-z']){re.escape(phrase)}(?![a-z'])", " ", text)
    else:
        n = text.count(phrase)
        new = text.replace(phrase, " ")
    return new, n > 0


def small_talk(text: str) -> str | None:
    """Return "greeting" / "thanks" / "goodbye" / "ack" / "help" when the whole message is small talk, else None."""
    t = re.sub(r"[\s.,!?।॥،;:\"“”()\-]+", " ", (text or "").lower()).strip()
    if not t or len(t.split()) > 8:
        return None
    found = set()
    for kind in _PRIORITY:
        for p in sorted(_TALK[kind], key=len, reverse=True):
            t, hit = _strip(t, p)
            if hit:
                found.add(kind)
    if not found:
        return None
    for f in _FILLERS:
        t, _ = _strip(t, f)
    if t.strip():
        return None  # something else was said too: treat it as a real question
    return next(k for k in _PRIORITY if k in found)
