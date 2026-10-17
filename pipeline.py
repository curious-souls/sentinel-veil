"""
pipeline.py - runs one item through: triage -> RAM buffer -> AI -> decision -> wipe.
Returns a plain dict so the UI (or the benchmark) can show or score it.
"""
import os
import time

import buffer as buf
import decide as dec
import gemma
import triage as tri

ROOT = os.path.dirname(os.path.abspath(__file__))


class OcrUnavailable(RuntimeError):
    """Tesseract could not be found on this computer."""


def _find_tesseract():
    """Look on PATH, then in the places Windows installers put it. SENTINEL_TESSERACT overrides."""
    import shutil
    candidates = []
    if os.environ.get("SENTINEL_TESSERACT"):
        candidates.append(os.environ["SENTINEL_TESSERACT"])
    on_path = shutil.which("tesseract")
    if on_path:
        candidates.append(on_path)
    if os.name == "nt":
        for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"),
                     os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")):
            if base:
                candidates.append(os.path.join(base, "Tesseract-OCR", "tesseract.exe"))
    for c in candidates:
        if c and os.path.exists(c):
            return c
    return None


def ocr_image(path_or_file) -> str:
    """Local OCR (Tesseract). Nothing is sent anywhere."""
    from PIL import Image
    import pytesseract
    exe = _find_tesseract()
    if exe is None:
        raise OcrUnavailable("Tesseract was not found. Install it (winget install --id UB-Mannheim.TesseractOCR -e), "
                             "restart VS Code, or set SENTINEL_TESSERACT to the path of tesseract.exe.")
    pytesseract.pytesseract.tesseract_cmd = exe
    img = Image.open(path_or_file)
    return pytesseract.image_to_string(img).strip()


def run(item: dict, use_real_ai: bool, ttl: float = 5.0, on_stage=None, wait_for_wipe: bool = True) -> dict:
    """
    item: {text, kind: 'message'|'screen', sender_known, banking_app_open, remote_app_running}
    on_stage(name, data) is called as each stage finishes (the UI uses it to light up).
    """
    emit = on_stage or (lambda *_: None)
    watch = buf.DiskWatch(ROOT)
    res = {"item": item, "stages": [], "timings": {}}

    def stage(name, data):
        res["stages"].append((name, data))
        emit(name, data)

    t_all = time.perf_counter()

    # 1. cheap first check
    t0 = time.perf_counter()
    tr = tri.triage(item["text"], item.get("sender_known", True),
                    item.get("banking_app_open", False), item.get("remote_app_running", False),
                    item.get("use_model", False))
    res["timings"]["triage_ms"] = (time.perf_counter() - t0) * 1000
    res["triage"] = tr
    stage("triage", tr)

    ai = None
    rb = None
    if tr.needs_ai:
        # 2. RAM-only buffer
        rb = buf.RamBuffer(ttl)
        rb.put(item["text"])
        stage("buffer", {"bytes": rb.size, "ttl": ttl})

        # 3. smart AI
        ai = gemma.analyze(item["text"], item.get("sender_known", True), item.get("kind", "message"),
                           tr.score, [c.name for c in tr.clues if c.points > 0], use_real_ai)
        res["timings"]["ai_ms"] = ai["seconds"] * 1000
        stage("ai", ai)
    else:
        stage("buffer", None)
        stage("ai", None)

    # 4. decision
    d = dec.decide(tr.score, tr.sensitive, item.get("kind", "message"), ai)
    res["decision"] = d
    res["ai"] = ai
    stage("decision", d)

    # 5. wipe the buffer once its time is up
    if rb is not None:
        if wait_for_wipe:
            while rb.remaining() > 0:
                emit("countdown", rb.remaining())
                time.sleep(0.2)
        proof = rb.wipe()
        res["wipe"] = proof
        stage("wipe", proof)
    else:
        stage("wipe", None)

    res["timings"]["total_ms"] = (time.perf_counter() - t_all) * 1000
    res["files_changed"] = watch.new_or_changed()
    return res
