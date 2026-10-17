# Sentinel Veil prototype (text + image)

A laptop demo of a "smart firewall for scams". The screen is split in two: the **left half is the
simulated kernel layer** (a live terminal log of every step) and the **right half is the device screen**
(what the user actually sees). It simulates the protection layer on a phone. The phone/OS hookup is simulated by the scenario picker; everything
after that is real code.

```
incoming item -> triage (cheap clues + score) -> [score high enough?]
                                                   |no  -> ALLOW, AI never wakes
                                                   |yes -> RAM buffer -> Gemma -> decision -> wipe
```

Decisions: **ALLOW**, **DELAY**, **CHALLENGE**, **REJECT** (rule table is shown in the app).

## Setup

```bash
pip install -r requirements.txt
sudo apt install tesseract-ocr          # for the screenshot scenario (OCR)
python make_assets.py                   # makes the fake phishing screenshot

# real AI (recommended): local Gemma through Ollama
ollama pull gemma3:4b                   # or the Gemma 4 tag you want; check `ollama list`
export SENTINEL_MODEL=gemma3:4b         # set this to whichever tag you pulled

streamlit run app.py
python benchmark.py                     # cascade vs "Gemma on everything"
```

Without Ollama the app still runs in **STAND-IN mode**. The AI step then just reuses
the first-check score, and the app says so in a yellow banner. Do not present
stand-in results as Gemma results.

## Files

| File | Job |
|---|---|
| `triage.py` | cheap first check: clue rules + situation clues -> score 0-100 |
| `decide.py` | score + AI answer -> Allow / Delay / Challenge / Reject (rule table) |
| `buffer.py` | RAM-only buffer, zero-overwrite wipe, disk-write check |
| `gemma.py` | calls local Gemma via Ollama; stand-in when unavailable |
| `pipeline.py` | runs one item through all the steps |
| `scenarios.py` | the 7 demo scenarios |
| `app.py` | Streamlit screen |
| `benchmark.py` + `data/tests.csv` | 59 hand-written examples (English + Hinglish) |

## Known limits (say these out loud in the pitch)

- **Triage can miss scams.** If a scam has few clues, the AI never sees it. The benchmark prints how many.
- **The test set is hand-written by the same people who wrote the rules**, so the numbers are optimistic.
  Add Kaggle data (keep a held-out part) and more Indian scam examples before quoting figures.
- **RAM wipe is best-effort in Python.** Other copies of text can exist (interpreter, swap). A real product
  needs locked memory, swap disabled and encrypted memory.
- **The disk check only watches this project folder.**
- A scammer can copy the "do not share" wording of a real OTP. The first check only trusts that wording
  from a known/verified sender.
- Real OS-level hooks, on-phone chips, hardware-token challenge and live audio are **future work**.
  Audio (call) scenarios are planned as the next addition.
