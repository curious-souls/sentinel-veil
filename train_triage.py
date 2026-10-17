"""
train_triage.py - trains the SMALL first-check model (not Gemma).

It learns from labelled messages (scam / safe) and saves data/triage_model.joblib.
When that file exists and you switch it on, triage.py adds one extra clue:
"the trained model thinks this reads like a scam". That helps catch scams with
few obvious keywords.

Examples
  # your own examples only
  python train_triage.py

  # Kaggle SMS Spam style file (columns v1 = label, v2 = text), plus your examples
  python train_triage.py --data spam.csv --text-col v2 --label-col v1 --scam-values spam --encoding latin-1

  # any other Kaggle file: tell it the column names and which label values mean "scam"
  python train_triage.py --data phishing.csv --text-col text --label-col type --scam-values phishing,smishing

THE RULE THAT KEEPS THE NUMBERS HONEST
  * The model trains on 80% of (Kaggle + data/extra_train.csv).
  * 20% is held out and only used to measure it.
  * data/tests.csv is your final exam. It is NEVER used for training.
"""
import argparse
import csv
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(ROOT, "data", "triage_model.joblib")


def read_csv(path, text_col, label_col, scam_values, encoding=None):
    """Return [(text, 1 if scam else 0)]. Tries utf-8, then latin-1 (Kaggle SMS file needs it)."""
    last_err = None
    for enc in ([encoding] if encoding else ["utf-8", "latin-1"]):
        try:
            with open(path, encoding=enc, newline="") as f:
                reader = csv.DictReader(f)
                if text_col not in (reader.fieldnames or []) or label_col not in (reader.fieldnames or []):
                    sys.exit(f"Columns not found in {path}. It has: {reader.fieldnames}. "
                             f"Use --text-col and --label-col.")
                rows = []
                for r in reader:
                    text = (r.get(text_col) or "").strip()
                    label = (r.get(label_col) or "").strip().lower()
                    if text and label:
                        rows.append((text, 1 if label in scam_values else 0))
                return rows
        except UnicodeDecodeError as e:
            last_err = e
    sys.exit(f"Could not read {path}: {last_err}. Try --encoding latin-1")


def main():
    ap = argparse.ArgumentParser(description="Train the small first-check model.")
    ap.add_argument("--data", help="optional Kaggle CSV")
    ap.add_argument("--text-col", default="text")
    ap.add_argument("--label-col", default="label")
    ap.add_argument("--scam-values", default="scam,spam,phishing,smishing,fraud",
                    help="comma-separated label values that mean 'scam'")
    ap.add_argument("--encoding", default=None)
    ap.add_argument("--extra", default=os.path.join(ROOT, "data", "extra_train.csv"),
                    help="your own examples (columns text,label with scam/safe)")
    ap.add_argument("--extra-weight", type=int, default=5,
                    help="repeat your own rows this many times so they count more than a big generic file")
    ap.add_argument("--max-rows", type=int, default=20000, help="cap on Kaggle rows (keeps training quick)")
    args = ap.parse_args()

    try:
        import joblib
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import classification_report, confusion_matrix
        from sklearn.model_selection import train_test_split
        from sklearn.pipeline import FeatureUnion, Pipeline
    except ImportError:
        sys.exit("scikit-learn is missing. Run:  pip install scikit-learn joblib")

    scam_values = {v.strip().lower() for v in args.scam_values.split(",")}
    pool = []      # (text, label, is_own_example)
    sources = []

    if args.data:
        k = read_csv(args.data, args.text_col, args.label_col, scam_values, args.encoding)
        if len(k) > args.max_rows:
            import random
            random.Random(42).shuffle(k)
            k = k[:args.max_rows]
        pool += [(t, l, False) for t, l in k]
        sources.append(f"{os.path.basename(args.data)} ({len(k)} rows)")

    if os.path.exists(args.extra):
        e = read_csv(args.extra, "text", "label", {"scam"})
        pool += [(t, l, True) for t, l in e]
        sources.append(f"{os.path.basename(args.extra)} ({len(e)} rows, counted x{args.extra_weight} in training)")

    # drop exact duplicate messages so the same text can never sit on both sides of the split
    seen, unique = set(), []
    for t, l, own in pool:
        if t not in seen:
            seen.add(t)
            unique.append((t, l, own))
    pool = unique

    if len(pool) < 20:
        sys.exit("Not enough training rows. Add --data or fill data/extra_train.csv.")

    y_all = [l for _, l, _ in pool]
    print("Training data:", ", ".join(sources))
    print(f"  unique rows {len(pool)}  scam {sum(y_all)}  safe {len(y_all) - sum(y_all)}")
    if sum(y_all) == 0 or sum(y_all) == len(y_all):
        sys.exit("Training data needs both scam and safe examples. Check --scam-values.")

    # SPLIT FIRST. Only afterwards are your own examples repeated, and only in the training half.
    idx = list(range(len(pool)))
    tr_idx, ho_idx = train_test_split(idx, test_size=0.2, random_state=42, stratify=y_all)
    x_tr, y_tr = [], []
    for i in tr_idx:
        t, l, own = pool[i]
        for _ in range(args.extra_weight if own else 1):
            x_tr.append(t)
            y_tr.append(l)
    x_ho = [pool[i][0] for i in ho_idx]
    y_ho = [pool[i][1] for i in ho_idx]

    pipe = Pipeline([
        ("features", FeatureUnion([
            ("word", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)),
            ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=2, sublinear_tf=True)),
        ])),
        ("clf", LogisticRegression(max_iter=2000, class_weight="balanced")),
    ])
    pipe.fit(x_tr, y_tr)

    print("\n== Held-out check (20% the model never trained on) ==")
    pred = pipe.predict(x_ho)
    print(classification_report(y_ho, pred, target_names=["safe", "scam"], digits=2, zero_division=0))
    tn, fp, fn, tp = confusion_matrix(y_ho, pred, labels=[0, 1]).ravel()
    print(f"scams caught {tp}/{tp + fn}   safe wrongly flagged {fp}/{fp + tn}")
    if args.extra and os.path.exists(args.extra) and not args.data:
        print("(Small held-out set from only your own examples: treat this as a smoke test, not a result.)")

    # Final exam: the hand-written test set, never trained on.
    tests = os.path.join(ROOT, "data", "tests.csv")
    if os.path.exists(tests):
        rows = read_csv(tests, "text", "label", {"scam"})
        ex_x = [t for t, _ in rows]
        ex_y = [l for _, l in rows]
        probs = pipe.predict_proba(ex_x)[:, 1]
        ex_pred = [1 if p >= 0.5 else 0 for p in probs]
        tp = sum(1 for a, b in zip(ex_y, ex_pred) if a == 1 and b == 1)
        fn = sum(1 for a, b in zip(ex_y, ex_pred) if a == 1 and b == 0)
        fp = sum(1 for a, b in zip(ex_y, ex_pred) if a == 0 and b == 1)
        tn = sum(1 for a, b in zip(ex_y, ex_pred) if a == 0 and b == 0)
        print("\n== Final exam: data/tests.csv (never used for training) ==")
        print(f"scams caught {tp}/{tp + fn}   safe wrongly flagged {fp}/{fp + tn}   accuracy {(tp + tn) / len(ex_y):.0%}")
        print("(This is the model on its own. The real system also uses the rules and Gemma.)")

    # The saved model is the same one that was measured above (trained on the training part only).
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump({"model": pipe, "threshold": 0.5, "sources": sources, "rows": len(pool)}, MODEL_PATH)
    print(f"\nSaved {MODEL_PATH}")
    print("Switch it on in the app sidebar, or run:  python benchmark.py --learned")


if __name__ == "__main__":
    main()
