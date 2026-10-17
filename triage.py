"""
triage.py - the cheap first check.

Looks at the content AND the situation, adds up points, and says whether the
smart AI (Gemma) is needed. No AI, no network, runs in microseconds.
"""
import os
import re
from dataclasses import dataclass

# Score at or above this wakes the AI. Below it, the item is allowed straight through.
AI_THRESHOLD = 25

# (name, points, regex, plain-language reason)
CONTENT_RULES = [
    ("Asks for a code / PIN / password", 30,
     r"\b(otp|pin|cvv|password|passcode|aadhaar|aadhar|one[- ]time)\b|\b\d\s?digits?\b",
     "Real organisations never ask you to hand over codes or PINs."),
    ("Money or payment involved", 20,
     r"\b(pay|payment|transfer|send|refund|fee|charges?|collect request|upi|rupees|inr|lottery|lakh|deposit|gift cards?|paise|paisa|paise)\b|rs\.?\s?\d|₹",
     "Scams usually end with you sending money."),
    ("Urgency or threat", 15,
     r"\b(immediately|urgent|within \d+|expires?|expired|blocked|suspend\w*|last (warning|chance)|"
     r"arrest|legal action|deactivat\w*|turant|abhi|aaj raat|kat jayega|band ho|disconnected)\b",
     "Pressure to act fast stops you from thinking."),
    ("Contains a link", 15,
     r"https?://\S+|www\.\S+",
     "Links are the main way phishing pages reach you."),
    ("Shortened or odd link", 10,
     r"bit\.ly|tinyurl|cutt\.ly|rb\.gy|\.(xyz|top|click|link|online|site|icu)\b",
     "Short or unusual domains hide where the link really goes."),
    ("Pretends to be an authority", 10,
     r"\b(bank|rbi|sbi|hdfc|icici|axis|kyc|police|cbi|customs|income tax|court|parcel|courier|"
     r"bijli|electricity|aadhaar|trai|sim|paytm|amazon)\b",
     "Scammers borrow the name of banks, police and delivery firms."),
    ("Asks you to install a remote-access app", 25,
     r"\b(anydesk|teamviewer|quicksupport|screen ?share)\b|\.apk\b",
     "Remote-access apps let a stranger control your phone."),
]

# A genuine bank OTP warns you NOT to share it. Only trusted for known / verified senders.
PROTECTIVE = re.compile(r"(do not|don't|never|na karein)\s+share", re.I)

SENSITIVE_RULES = {"Asks for a code / PIN / password", "Money or payment involved"}


@dataclass
class Clue:
    name: str
    points: int
    why: str


@dataclass
class TriageResult:
    score: int
    clues: list
    needs_ai: bool
    sensitive: bool  # content touches money or credentials


# ---- optional trained model (made by train_triage.py) ----
# SECURITY: the model file is a pickle. Only load a model you trained yourself.
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "triage_model.joblib")
_cache = {"loaded": False, "obj": None}


def _model():
    if not _cache["loaded"]:
        _cache["loaded"] = True
        try:
            if os.path.exists(MODEL_PATH):
                import joblib
                _cache["obj"] = joblib.load(MODEL_PATH)
        except Exception:
            _cache["obj"] = None
    return _cache["obj"]


def model_available() -> bool:
    return _model() is not None


def learned_probability(text: str):
    m = _model()
    return None if m is None else float(m["model"].predict_proba([text])[0][1])


def triage(text: str, sender_known: bool = True, banking_app_open: bool = False,
           remote_app_running: bool = False, use_model: bool = False) -> TriageResult:
    clues = []
    low = text.lower()

    for name, pts, pattern, why in CONTENT_RULES:
        if re.search(pattern, low):
            clues.append(Clue(name, pts, why))

    sensitive = any(c.name in SENSITIVE_RULES for c in clues)

    # Situation clues (the content alone is not enough).
    if not sender_known:
        clues.append(Clue("Unknown sender", 15, "You have no history with this sender."))
    if remote_app_running:
        clues.append(Clue("Remote-access app is running", 20, "Someone may be controlling the device."))
    if banking_app_open and sensitive:
        clues.append(Clue("Banking app is open", 10, "Money is one tap away right now."))

    # Optional extra clue from the small trained model.
    if use_model:
        p = learned_probability(text)
        if p is not None and p >= _model()["threshold"]:
            clues.append(Clue("Trained model: reads like a scam", round(30 * p),
                              f"The small trained model gives this a {p:.0%} scam score."))

    # Reassuring clue, trusted only from a known / verified sender.
    if sender_known and PROTECTIVE.search(text):
        clues.append(Clue("Warns you not to share the code", -30,
                          "Genuine alerts from a verified sender warn you about this."))

    score = max(0, min(100, sum(c.points for c in clues)))
    return TriageResult(score=score, clues=clues, needs_ai=score >= AI_THRESHOLD, sensitive=sensitive)
