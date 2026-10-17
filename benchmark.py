"""
benchmark.py - measures the cascade honestly.

  python benchmark.py            # uses Gemma if Ollama is running, else triage-only numbers
  python benchmark.py --no-ai    # force triage-only

What it reports
  - how many items skipped the AI (the battery-saving claim)
  - how many scams the first check lets through WITHOUT the AI ever seeing them (the weak point)
  - with real Gemma: cascade vs "run Gemma on everything" (accuracy and time)

The test set in data/tests.csv is hand-written. Add Kaggle rows (and keep some rows
out of any training) before quoting numbers on a slide.
"""
import csv
import os
import sys
import time

import decide as dec
import gemma
import triage as tri

ROOT = os.path.dirname(os.path.abspath(__file__))


def load():
    with open(os.path.join(ROOT, "data", "tests.csv"), encoding="utf-8") as f:
        return list(csv.DictReader(f))


def flagged(action):  # anything other than ALLOW counts as "we reacted"
    return action != dec.ALLOW


def evaluate(rows, mode, use_real):
    """mode: 'cascade' or 'always'."""
    tp = fn = fp = tn = ai_calls = 0
    ai_time = 0.0
    misses = []
    for r in rows:
        known, bank, remote = r["sender_known"] == "1", r["banking_app_open"] == "1", r["remote_app_running"] == "1"
        t = tri.triage(r["text"], known, bank, remote)
        ai = None
        if mode == "always" or t.needs_ai:
            ai = gemma.analyze(r["text"], known, "message", t.score,
                               [c.name for c in t.clues if c.points > 0], use_real)
            ai_calls += 1
            ai_time += ai["seconds"]
        d = dec.decide(t.score, t.sensitive, "message", ai)
        bad = r["label"] == "scam"
        hit = flagged(d.action)
        if bad and hit: tp += 1
        elif bad: fn += 1; misses.append((r["text"], t.score, d.action))
        elif hit: fp += 1
        else: tn += 1
    n = len(rows)
    return {"n": n, "scams_caught": tp, "scams_missed": fn, "safe_wrongly_flagged": fp, "safe_ok": tn,
            "accuracy": (tp + tn) / n, "ai_calls": ai_calls, "ai_share": ai_calls / n,
            "ai_seconds": ai_time, "misses": misses}


def main():
    rows = load()
    use_real = ("--no-ai" not in sys.argv) and gemma.is_available()
    scams = [r for r in rows if r["label"] == "scam"]
    safe = [r for r in rows if r["label"] == "safe"]
    print(f"Test set: {len(rows)} items ({len(scams)} scams, {len(safe)} safe)")

    # Triage-only facts (no AI needed)
    reach = lambda group: sum(tri.triage(r["text"], r["sender_known"] == "1", r["banking_app_open"] == "1",
                                         r["remote_app_running"] == "1").needs_ai for r in group)
    s_reach, f_reach = reach(scams), reach(safe)
    print("\n-- First check (triage) alone --")
    print(f"Skipped the AI:                {len(rows) - s_reach - f_reach}/{len(rows)} ({(len(rows) - s_reach - f_reach) / len(rows):.0%})")
    print(f"Scams sent on to the AI:       {s_reach}/{len(scams)} ({s_reach / len(scams):.0%})   <- the part triage gets right")
    print(f"Scams that NEVER reach the AI: {len(scams) - s_reach}/{len(scams)}   <- the known weak point")
    print(f"Safe items sent to the AI:     {f_reach}/{len(safe)}   (extra work, not harm)")

    if not use_real:
        print("\nGemma is not running (or --no-ai), so cascade-vs-always-AI is NOT reported.")
        print("Start Ollama, pull a Gemma model, and run again for the full comparison.")
        c = evaluate(rows, "cascade", False)
        print("\nWorst misses (stand-in mode):")
        for text, score, action in c["misses"][:8]:
            print(f"  score={score:3} {action:6} {text[:90]}")
        return

    print(f"\n-- Real Gemma ({gemma.MODEL}) --")
    results = {}
    for mode in ("always", "cascade"):
        t0 = time.perf_counter()
        results[mode] = evaluate(rows, mode, True)
        results[mode]["wall"] = time.perf_counter() - t0
    for mode, r in results.items():
        label = "Gemma on everything" if mode == "always" else "Cascade (ours)"
        print(f"{label:20} accuracy={r['accuracy']:.0%}  scams caught={r['scams_caught']}/{len(scams)}  "
              f"safe wrongly flagged={r['safe_wrongly_flagged']}/{len(safe)}  "
              f"AI calls={r['ai_calls']} ({r['ai_share']:.0%})  time={r['wall']:.1f}s")
    a, c = results["always"], results["cascade"]
    if a["wall"] > 0:
        print(f"\nCascade used {1 - c['ai_calls'] / a['ai_calls']:.0%} fewer AI calls and was {a['wall'] / max(c['wall'], 1e-9):.1f}x faster.")

    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    with open(os.path.join(ROOT, "results", "benchmark.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["mode", "accuracy", "scams_caught", "scams_missed", "safe_wrongly_flagged", "ai_calls", "seconds"])
        for mode, r in results.items():
            w.writerow([mode, f"{r['accuracy']:.3f}", r["scams_caught"], r["scams_missed"],
                        r["safe_wrongly_flagged"], r["ai_calls"], f"{r['wall']:.1f}"])
    print("Saved results/benchmark.csv")


if __name__ == "__main__":
    main()
