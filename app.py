"""
Sentinel Veil prototype - run with:  streamlit run app.py

Left half  = the "kernel layer" (simulated), shown as a live terminal log.
Right half = the device screen, i.e. what the user actually sees.

The phone / OS hookup is simulated by the scenario picker; everything after that
(triage, RAM buffer, Gemma, decision, wipe) is real code.
"""
import base64
import html
import time

import streamlit as st

import decide as dec
import gemma
import pipeline
import triage as tri
from scenarios import CALLS, SCENARIOS

st.set_page_config(page_title="Sentinel Veil", page_icon="🛡️", layout="wide")

COLORS = {dec.ALLOW: "#1a7f37", dec.DELAY: "#9a6700", dec.CHALLENGE: "#bc4c00", dec.REJECT: "#cf222e"}

ss = st.session_state
ss.setdefault("stats", {"runs": 0, "ai_calls": 0, "skipped": 0})
ss.setdefault("last", None)
ss.setdefault("gemma_ok", None)

# ------------------------------------------------------------------ styles
st.markdown("""
<style>
.term-wrap{display:flex;flex-direction:column-reverse;overflow-y:auto;height:640px;background:#0d1117;
  border:1px solid #30363d;border-radius:8px;}
.term{margin:0;padding:14px 16px;color:#c9d1d9 !important;font:13px/1.55 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  white-space:pre-wrap;word-break:break-word;}
.term .tl{color:#c9d1d9;margin:0 0 3px;padding:0;white-space:pre-wrap}
.term .tag{color:#58a6ff;font-weight:600}
.term .ok{color:#3fb950} .term .warn{color:#d29922} .term .bad{color:#f85149} .term .dim{color:#8b949e}
.term-bar{background:#161b22;border:1px solid #30363d;border-bottom:0;border-radius:8px 8px 0 0;
  padding:6px 12px;color:#8b949e;font:12px ui-monospace,Menlo,Consolas,monospace}
.phone{max-width:380px;margin:0 auto;border:10px solid #1f2328;border-radius:34px;background:#f4f5f7;
  color:#111;min-height:620px;padding:0 0 18px;overflow:hidden;font-family:system-ui,sans-serif}
.phone .top{background:#e6e8ec;padding:10px 16px;font-weight:600;font-size:14px;display:flex;justify-content:space-between}
.phone .body{padding:16px}
.phone .sender{font-size:12px;color:#555;margin-bottom:4px}
.phone .bubble{background:#fff;border:1px solid #d8dbe0;border-radius:14px;padding:12px 14px;font-size:14px;line-height:1.4;
  word-break:break-word}
.phone .blur{filter:blur(5px);user-select:none}
.phone .dim{opacity:.55}
.phone img{width:100%;border-radius:8px;border:1px solid #d8dbe0;margin-bottom:8px}
.phone .note{margin-top:14px;border-radius:12px;padding:12px 14px;font-size:13px;line-height:1.4;border-left:6px solid}
.phone .note b{display:block;font-size:15px;margin-bottom:2px}
.phone .idle{color:#777;text-align:center;margin-top:120px;font-size:14px}
.phone .cline{background:#fff;border:1px solid #d8dbe0;border-radius:12px;padding:8px 12px;margin:6px 0;font-size:13px;line-height:1.35}
.phone .meter{height:10px;background:#d8dbe0;border-radius:6px;margin-top:12px;overflow:hidden}
.phone .meter div{height:10px}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("Input")
    mode = st.radio("Source", ["Demo scenario", "Type / upload my own"], label_visibility="collapsed")

    item = None
    if mode == "Demo scenario":
        name = st.selectbox("Scenario", list(SCENARIOS) + list(CALLS))
        if name in CALLS:
            item = {"call": CALLS[name], "name": name}
            st.caption(f"Simulated live call · caller: {CALLS[name]['caller']}")
        else:
            sc = SCENARIOS[name]
            item = {k: sc.get(k) for k in ("kind", "text", "sender_known", "banking_app_open", "remote_app_running")}
            item.update(sender_label=sc["sender"], image=sc.get("image"), name=name, expect=sc["expect"],
                        ocr_fallback=sc.get("ocr_fallback"))
            st.caption(f"Sender: {sc['sender']}")
    else:
        text = st.text_area("Message text", height=120, placeholder="Paste a message...")
        up = st.file_uploader("...or a screenshot", type=["png", "jpg", "jpeg"])
        kind = "screen" if up else "message"
        known = st.toggle("Sender is known / verified", value=False)
        bank = st.toggle("Banking app is open", value=False)
        remote = st.toggle("Remote-access app is running", value=False)
        item = dict(kind=kind, text=text, sender_known=known, banking_app_open=bank, remote_app_running=remote,
                    sender_label="Known contact" if known else "Unknown sender", image=up, name="Custom", expect="-")

    st.header("Settings")
    ttl = st.slider("RAM buffer wipe timer (seconds)", 1, 10, 5)
    want_real = st.toggle("Use local Gemma if available", value=True)
    if st.button("Re-check Gemma"):
        ss.gemma_ok = None
    if ss.gemma_ok is None:
        ss.gemma_ok = gemma.is_available()
    use_real = want_real and ss.gemma_ok
    if tri.model_available():
        use_model = st.toggle("Use trained first-check model", value=False)
    else:
        use_model = False
        st.caption("No trained first-check model yet (run train_triage.py).")

    run = st.button("▶ Run through Sentinel Veil", type="primary", width="stretch")

    st.divider()
    st.subheader("This session")
    stats_ph = st.empty()


def draw_stats():
    s = ss.stats
    with stats_ph.container():
        st.metric("Items checked", s["runs"])
        st.metric("Skipped the AI", s["skipped"])
        st.metric("AI calls", s["ai_calls"])


draw_stats()

# ------------------------------------------------------------------ header
st.title("🛡️ Sentinel Veil")
st.caption("Multimodal AI OS-layer firewall & scam detector · prototype simulator")

if use_real:
    st.success(f"AI mode: **real local Gemma** ({gemma.MODEL}). Nothing leaves this machine.")
else:
    st.warning("AI mode: **STAND-IN**. Gemma is not reachable, so the AI step reuses the first-check score "
               "and is not a real AI. Start Ollama and pull a Gemma model for the real thing (see README).")

col_term, col_screen = st.columns(2, gap="large")
with col_term:
    st.subheader("⚙️ Kernel layer (simulated)")
    ph_term = st.empty()
with col_screen:
    st.subheader("📱 Device screen")
    ph_screen = st.empty()
    ph_challenge = st.container()

proof = st.container()


# ------------------------------------------------------------------ terminal
def tline(tag, msg, cls=""):
    """One log line. Text is escaped so scam content can never inject HTML."""
    m = html.escape(msg)
    m = f'<span class="{cls}">{m}</span>' if cls else m
    return f'<span class="tag">{tag:<9}</span> {m}'


def draw_terminal(lines, tail=None):
    body = "".join(f'<div class="tl">{l}</div>' for l in lines + ([tail] if tail else []))
    ph_term.markdown(
        '<div class="term-bar">sentinel@veil:~$ sv-kernel --watch --adrc</div>'
        f'<div class="term-wrap"><div class="term">{body}</div></div>', unsafe_allow_html=True)


def lines_for(name, data, it):
    """Turn a pipeline stage into terminal lines."""
    L = []
    if name == "triage":
        for c in data.clues:
            sign = f"+{c.points}" if c.points > 0 else str(c.points)
            L.append(tline("triage", f"{sign:>4}  {c.name}", "ok" if c.points < 0 else "warn" if c.points >= 20 else ""))
        verdict = (f"WAKE AI (>= {tri.AI_THRESHOLD})", "warn") if data.needs_ai else (f"BYPASS, AI stays asleep (< {tri.AI_THRESHOLD})", "ok")
        L.append(tline("triage", f"score={data.score}/100  -> {verdict[0]}", verdict[1]))
    elif name == "buffer":
        if data is None:
            L.append(tline("ramguard", "not used (nothing risky enough to hold)", "dim"))
        else:
            L.append(tline("ramguard", f"hold {data['bytes']} bytes in memory only, wipe timer {data['ttl']}s"))
    elif name == "ai":
        if data is None:
            L.append(tline("npu", "asleep, zero compute used", "dim"))
        else:
            L.append(tline("npu", f"wake model: {data['source']}", "warn" if not data["real"] else ""))
            lvl = {"low": "ok", "medium": "warn", "high": "bad"}[data["level"]]
            L.append(tline("npu", f"verdict={data['level'].upper()} risk={data['risk']}/100 in {data['seconds'] * 1000:.0f} ms", lvl))
            L.append(tline("npu", f"reason: {data['reason']}", "dim"))
    elif name == "decision":
        L.append(tline("adrc", f"decision={data.action}  risk={data.risk}/100",
                       {"ALLOW": "ok", "DELAY": "warn", "CHALLENGE": "warn", "REJECT": "bad"}[data.action]))
        L.append(tline("adrc", f"rule: {data.rule}", "dim"))
    elif name == "wipe":
        if data is None:
            L.append(tline("ramguard", "nothing to wipe", "dim"))
        else:
            L.append(tline("ramguard", f"{data['bytes_overwritten']} bytes overwritten with 0x00, buffer size now {data['size_after']}", "ok"))
    return L


# ------------------------------------------------------------------ device screen
def screen_html(it, state, d=None):
    img = f'<img src="data:image/png;base64,{it["image_b64"]}">' if it.get("image_b64") else ""
    text = html.escape(it["text"]).replace("\n", "<br>")
    head = '<div class="top"><span>Messages</span><span>Sentinel Veil ●</span></div>'
    sender = f'<div class="sender">{html.escape(it["sender_label"])}</div>'

    if state == "idle":
        return f'<div class="phone">{head}<div class="body"><div class="idle">Waiting for incoming content…</div></div></div>'

    bubble_cls, note = "bubble", ""
    if state == "checking":
        bubble_cls = "bubble dim"
        note = ('<div class="note" style="border-color:#9a6700;background:#fff4d6"><b>⏳ DELAY · checking…</b>'
                'Held for a moment while Sentinel Veil looks at this.</div>')
    elif d is not None:
        c = COLORS[d.action]
        if d.action == dec.ALLOW:
            note = (f'<div class="note" style="border-color:{c};background:#e3f5e8"><b>✓ ALLOW · delivered</b>'
                    f'{"Checked and safe." if it.get("ai_used") else "No risky signs, passed straight through."}</div>')
        elif d.action == dec.DELAY:
            bubble_cls = "bubble blur"
            note = (f'<div class="note" style="border-color:{c};background:#fff4d6"><b>⏳ DELAY · held for safety</b>'
                    f'{html.escape(d.reason)}</div>')
        elif d.action == dec.CHALLENGE:
            bubble_cls = "bubble blur"
            note = (f'<div class="note" style="border-color:{c};background:#ffe9db"><b>🔐 CHALLENGE · action frozen</b>'
                    f'{html.escape(d.reason)}<br><br>Confirm it is really you to continue.</div>')
        else:
            return (f'<div class="phone">{head}<div class="body">{sender}'
                    f'<div class="note" style="border-color:{c};background:#fde4e6;margin-top:6px"><b>🚫 REJECT · message blocked</b>'
                    f'Action blocked due to high phishing risk.<br><br>{html.escape(d.reason)}</div></div></div>')
    return f'<div class="phone">{head}<div class="body">{sender}{img}<div class="{bubble_cls}">{text}</div>{note}</div></div>'


def answer(code, message):
    ss.challenge = (code, message)


def show_challenge(d):
    ph_challenge.empty()
    if d is None or d.action != dec.CHALLENGE:
        return
    with ph_challenge.container(border=True):
        st.markdown("🔐 **Confirm it's you** (stand-in for a biometric / hardware-token prompt)")
        a, b = st.columns(2)
        # on_click runs before the page reruns, so the terminal can log the answer straight away
        a.button("I started this", key="ch_yes", on_click=answer,
                 args=("user approved", "Allowed by user. Logged as a user-approved exception."))
        b.button("Cancel, stay safe", key="ch_no", on_click=answer,
                 args=("user cancelled", "Cancelled. The action never happened."))
        if ss.get("challenge"):
            st.info(ss.challenge[1])


def show_proof(res):
    with proof:
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("New files written to disk", res["files_changed"])
        c2.metric("AI used?", "No" if res["ai"] is None else "Yes")
        c3.metric("First check time", f"{res['timings']['triage_ms']:.2f} ms")
        c4.metric("AI time", "—" if res["ai"] is None else f"{res['timings']['ai_ms']:.0f} ms")
        st.caption("Disk check = files created or changed in this project folder during the run. "
                   "Memory wipe is best-effort in Python; the real product would use locked memory (see README).")
        with st.expander("Rule table: how the decision is made"):
            st.table({"If…": [r for r, _ in dec.RULE_TABLE], "Then": [a for _, a in dec.RULE_TABLE]})


def prepare(it):
    """OCR and image encoding, done once per run. Returns (item, ocr_ms)."""
    it = dict(it)
    ocr_ms = None
    img = it.get("image")
    if img is not None:
        t0 = time.perf_counter()
        try:
            it["text"] = pipeline.ocr_image(img)
            ocr_ms = (time.perf_counter() - t0) * 1000
        except pipeline.OcrUnavailable:
            if not it.get("ocr_fallback"):
                raise  # an uploaded image has no pre-saved text, so show the real error
            it["text"] = it["ocr_fallback"]
            it["ocr_note"] = "Tesseract not found: using the pre-saved text of this demo image (NOT real OCR). See README."
        raw = open(img, "rb").read() if isinstance(img, str) else img.getvalue()
        it["image_b64"] = base64.b64encode(raw).decode()
        it["image"] = None  # keep the stored item light; the pixels live in image_b64
    return it, ocr_ms


# ------------------------------------------------------------------ simulated live call
RANK = {dec.ALLOW: 0, dec.DELAY: 1, dec.CHALLENGE: 2, dec.REJECT: 3}


def call_screen_html(call, shown, d=None, gate=None):
    head = '<div class="top"><span>📞 Call in progress</span><span>Sentinel Veil ●</span></div>'
    who = f'<div class="sender">{html.escape(call["caller"])} · simulated live call</div>'
    lines = "".join(f'<div class="cline">{html.escape(l)}</div>' for l in shown) or '<div class="sender">Connecting…</div>'
    risk = d.risk if d else 0
    color = COLORS[d.action] if d else COLORS[dec.ALLOW]
    meter = (f'<div class="meter"><div style="width:{risk}%;background:{color}"></div></div>'
             f'<div class="sender">Call risk {risk}/100</div>')
    note = ""
    if gate is not None:
        c = COLORS[gate.action]
        if gate.action == dec.ALLOW:
            note = (f'<div class="note" style="border-color:{c};background:#e3f5e8"><b>✓ ALLOW · payment app opened</b>'
                    f'{html.escape(gate.reason)}</div>')
        else:
            note = (f'<div class="note" style="border-color:{c};background:#ffe9db"><b>🔐 CHALLENGE · payment app frozen</b>'
                    f'{html.escape(gate.reason)}<br><br>Confirm it is really you to continue.</div>')
    elif d is not None:
        c = COLORS[d.action]
        if d.action == dec.ALLOW:
            note = f'<div class="note" style="border-color:{c};background:#e3f5e8"><b>✓ No warning</b>Nothing suspicious so far.</div>'
        elif d.action == dec.DELAY:
            note = (f'<div class="note" style="border-color:{c};background:#fff4d6"><b>⚠ CAUTION</b>'
                    f'{html.escape(d.reason)}</div>')
        else:
            note = (f'<div class="note" style="border-color:{c};background:#ffe9db"><b>⚠ WARNING · likely scam call</b>'
                    f'{html.escape(d.reason)}<br><br>Do not share codes or PINs. Payments are guarded.</div>')
    return f'<div class="phone">{head}<div class="body">{who}{lines}{meter}{note}</div></div>'


def show_proof_call(s):
    with proof:
        st.divider()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Call windows analysed", s["windows"])
        c2.metric("Woke the AI", f"{s['ai_wakes']} of {s['windows']}")
        c3.metric("New files written to disk", s["files"])
        c4.metric("Payment app gate", s["gate"].action)
        st.caption("The call audio is SIMULATED as a streaming transcript. In a real product this would come from "
                   "OS-level access via a phone maker. Sentinel Veil never looks at the PIN screen; it acts before.")
        with st.expander("Rule table: how the decision is made"):
            st.table({"If…": [r for r, _ in dec.RULE_TABLE], "Then": [a for _, a in dec.RULE_TABLE]})


def run_call(name, call):
    ss.pop("challenge", None)
    log = [tline("hook", f"call from '{call['caller']}' (SIMULATED stream, not real audio)")]
    draw_terminal(log)
    shown, worst = [], None
    windows = ai_wakes = files = 0
    ph_screen.markdown(call_screen_html(call, shown), unsafe_allow_html=True)
    time.sleep(0.8)

    for line in call["lines"]:
        shown.append(line)
        log.append(tline("asr", f'"{line}"', "dim"))
        ph_screen.markdown(call_screen_html(call, shown, worst), unsafe_allow_html=True)
        draw_terminal(log)
        time.sleep(0.9)
        if len(shown) < 2:
            continue  # wait for a little context before analysing

        window = " ".join(shown[-3:])
        item_w = dict(kind="call", text=window, sender_known=call["sender_known"],
                      banking_app_open=False, remote_app_running=False, use_model=use_model)
        log.append(tline("window", f"analysing the last {min(3, len(shown))} lines", "dim"))

        def live(stage, data):
            if stage == "countdown":
                return
            log.extend(lines_for(stage, data, item_w))
            draw_terminal(log)

        res = pipeline.run(item_w, use_real, ttl=0.5, on_stage=live)
        windows += 1
        ai_wakes += 1 if res["ai"] else 0
        files += res["files_changed"]
        d = res["decision"]
        if worst is None or RANK[d.action] >= RANK[worst.action]:  # a flagged call stays flagged
            worst = d
        ph_screen.markdown(call_screen_html(call, shown, worst), unsafe_allow_html=True)
        time.sleep(0.4)

    # the user now opens a payment app during the call (SIMULATED event)
    time.sleep(0.8)
    log.append(tline("event", "user opens a payment app (PhonePe / Google Pay) during the call [simulated]", "warn"))
    gate = dec.gate_payment_app(worst)
    log.append(tline("adrc", f"decision={gate.action}  risk={gate.risk}/100",
                     {"ALLOW": "ok", "DELAY": "warn", "CHALLENGE": "warn", "REJECT": "bad"}[gate.action]))
    log.append(tline("adrc", f"rule: {gate.rule}", "dim"))
    log.append(tline("disk", f"new or changed files in project folder: {files}", "ok" if files == 0 else "bad"))
    log.append(tline("kernel", "call analysis done, back to sleep", "dim"))
    draw_terminal(log)
    ph_screen.markdown(call_screen_html(call, shown, worst, gate), unsafe_allow_html=True)
    show_challenge(gate)

    stats = {"windows": windows, "ai_wakes": ai_wakes, "files": files, "gate": gate}
    ss.last = {"mode": "call", "call": call, "shown": list(shown), "worst": worst, "gate": gate, "log": log, "stats": stats}
    ss.stats["runs"] += windows
    ss.stats["ai_calls"] += ai_wakes
    ss.stats["skipped"] += windows - ai_wakes
    draw_stats()
    show_proof_call(stats)


# ------------------------------------------------------------------ run / replay
if run and "call" in item:
    run_call(item["name"], item["call"])

elif run:
    ss.pop("challenge", None)
    try:
        it, ocr_ms = prepare(item)
    except Exception as e:
        st.error(f"OCR failed ({type(e).__name__}): {e}")
        st.stop()
    if not (it["text"] or "").strip():
        st.warning("Nothing to check. Type a message or pick a scenario.")
        st.stop()

    it["use_model"] = use_model
    log = [tline("hook", f"rx {it['kind']} from '{it['sender_label']}' ({len(it['text'])} chars)")]
    if ocr_ms is not None:
        log.append(tline("ocr", f"text read from screen pixels in {ocr_ms:.0f} ms (local)"))
    if it.get("ocr_note"):
        log.append(tline("ocr", it["ocr_note"], "warn"))
    draw_terminal(log)
    ph_screen.markdown(screen_html(it, "checking"), unsafe_allow_html=True)
    time.sleep(0.5)

    def live(name, data):
        if name == "countdown":
            draw_terminal(log, tail=tline("ramguard", f"wiping in {data:.1f}s ...", "dim"))
            return
        if name == "ai":
            it["ai_used"] = data is not None  # the screen wording for ALLOW depends on this
        log.extend(lines_for(name, data, it))
        draw_terminal(log)
        if name == "decision":
            ph_screen.markdown(screen_html(it, "final", data), unsafe_allow_html=True)
            show_challenge(data)
        time.sleep(0.35)  # small pause so the log visibly streams in order

    res = pipeline.run(it, use_real, ttl=ttl, on_stage=live)
    log.append(tline("disk", f"new or changed files in project folder: {res['files_changed']}",
                     "ok" if res["files_changed"] == 0 else "bad"))
    log.append(tline("kernel", f"done in {res['timings']['total_ms']:.0f} ms (includes wipe wait), back to sleep", "dim"))
    draw_terminal(log)

    it["ai_used"] = res["ai"] is not None
    ss.last = {"res": res, "item": it, "log": log}
    ss.stats["runs"] += 1
    ss.stats["ai_calls"] += 1 if res["ai"] else 0
    ss.stats["skipped"] += 0 if res["ai"] else 1
    draw_stats()
    show_proof(res)

elif ss.last and ss.last.get("mode") == "call":
    L = ss.last
    log = list(L["log"])
    if ss.get("challenge"):
        log.append(tline("adrc", f"user response: {ss.challenge[0]}", "ok" if ss.challenge[0] == "user cancelled" else "warn"))
    draw_terminal(log)
    ph_screen.markdown(call_screen_html(L["call"], L["shown"], L["worst"], L["gate"]), unsafe_allow_html=True)
    show_challenge(L["gate"])
    show_proof_call(L["stats"])

elif ss.last:
    # a button on the page was pressed: redraw the last result without re-running it
    res, it, log = ss.last["res"], ss.last["item"], list(ss.last["log"])
    if ss.get("challenge"):
        log.append(tline("adrc", f"user response: {ss.challenge[0]}", "ok" if ss.challenge[0] == "user cancelled" else "warn"))
    draw_terminal(log)
    ph_screen.markdown(screen_html(it, "final", res["decision"]), unsafe_allow_html=True)
    show_challenge(res["decision"])
    show_proof(res)
else:
    draw_terminal([tline("kernel", "idle. waiting for a stream to inspect...", "dim")])
    ph_screen.markdown(screen_html({"text": "", "sender_label": ""}, "idle"), unsafe_allow_html=True)
