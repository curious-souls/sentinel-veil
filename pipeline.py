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


def ocr_image(path_or_file) -> str:
    """Local OCR (Tesseract). Nothing is sent anywhere."""
    from PIL import Image
    import pytesseract
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
                    item.get("banking_app_open", False), item.get("remote_app_running", False))
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
