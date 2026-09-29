"""Dataset pipeline: raw Kaggle CSVs -> cleaned, deduplicated, stratified splits.

Usage:  python -m src.data          (writes data/processed/*.parquet + results/data_*.csv)

Steps, in order:
  1. load the six source corpora (NOT the pre-merged phishing_email.csv, which is the
     same rows after lowercasing and stop-word removal: unusable for DistilBERT)
  2. keep only subject + body + label (+ source for analysis); drop sender,
     receiver, date and the urls flag
  3. clean text (src/preprocess.py)
  4. drop junk: fewer than 3 words, mailbox system messages
  5. deduplicate BEFORE splitting: exact, then near-duplicate (normalised key);
     groups whose copies disagree on the label are dropped entirely
  6. stratified 70/15/15 split on (source, label), fixed seed
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from src.preprocess import clean_email

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
RESULTS_DIR = ROOT / "results"

SOURCES = ["CEAS_08", "Enron", "Ling", "Nazario", "Nigerian_Fraud", "SpamAssasin"]
SEED = 42
SPLIT_FRACTIONS = (0.70, 0.15, 0.15)
MIN_WORDS = 3
# Nazario mbox artefact: "DON'T DELETE THIS MESSAGE -- FOLDER INTERNAL DATA"
JUNK_SUBJECT = re.compile(r"FOLDER INTERNAL DATA", re.I)

_URL = re.compile(r"(?:https?://|www\.)\S+", re.I)
_DIGITS = re.compile(r"\d+")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


# ------------------------------------------------------------------ loading

def load_raw(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    frames = []
    for src in SOURCES:
        df = pd.read_csv(raw_dir / f"{src}.csv", usecols=["subject", "body", "label"])
        frames.append(df.assign(source=src))
    df = pd.concat(frames, ignore_index=True)
    df["subject"] = df["subject"].fillna("").astype(str)
    df["body"] = df["body"].fillna("").astype(str)
    df["label"] = df["label"].astype(int)
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    out = [clean_email(s, b) for s, b in zip(df["subject"], df["body"])]
    return df.assign(subject=[o[0] for o in out], body=[o[1] for o in out], text=[o[2] for o in out])


def drop_junk(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    too_short = df["text"].str.split().str.len() < MIN_WORDS
    system_msg = df["subject"].str.contains(JUNK_SUBJECT)
    report = {"too_short": int(too_short.sum()), "mailbox_system_msg": int((system_msg & ~too_short).sum())}
    return df[~(too_short | system_msg)].reset_index(drop=True), report


# ------------------------------------------------------------------ dedup

def exact_key(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def near_key(text: str) -> str:
    """Normalised hash: case, URLs, numbers, punctuation and spacing ignored.

    Catches the same template sent with different tracking links / amounts, and
    the same email appearing in a pre-tokenised corpus ("2001 ,") and a raw one ("2001,").
    """
    t = _URL.sub(" url ", text.lower())
    t = _DIGITS.sub("0", t)
    t = _NON_ALNUM.sub("", t)
    return hashlib.sha1(t.encode("utf-8")).hexdigest()


def deduplicate(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Two passes (exact, then near). In each pass, a group of identical keys is
    kept as ONE row if all copies share a label, or dropped entirely if the labels
    conflict (we cannot know which label is right)."""
    report = {"before": len(df)}
    for name, keyfn in (("exact", exact_key), ("near", near_key)):
        key = df["text"].map(keyfn)
        n_labels = df.groupby(key)["label"].transform("nunique")
        conflicting = n_labels > 1
        dup_extra = key.duplicated() & ~conflicting
        report[f"{name}_duplicates_removed"] = int(dup_extra.sum())
        report[f"{name}_label_conflicts_removed"] = int(conflicting.sum())
        df = df[~(dup_extra | conflicting)].reset_index(drop=True)
    report["after"] = len(df)
    return df, report


# ------------------------------------------------------------------ splitting

def split(df: pd.DataFrame, seed: int = SEED) -> dict[str, pd.DataFrame]:
    """Stratified on source x label, so every split has the same mix of corpora
    AND classes (needed later for per-source evaluation)."""
    strata = df["source"] + "_" + df["label"].astype(str)
    train_frac, val_frac, test_frac = SPLIT_FRACTIONS
    train, rest = train_test_split(df, train_size=train_frac, stratify=strata, random_state=seed)
    val, test = train_test_split(rest, test_size=test_frac / (val_frac + test_frac),
                                 stratify=strata.loc[rest.index], random_state=seed)
    return {"train": train, "val": val, "test": test}


def add_ids(df: pd.DataFrame) -> pd.DataFrame:
    """Content-based id: stable across re-runs and machines (no dependence on row order)."""
    return df.assign(id=df["text"].map(lambda t: exact_key(t)[:16]))


# ------------------------------------------------------------------ reports

def split_summary(splits: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for name, d in splits.items():
        rows.append({"split": name, "n": len(d), "legitimate": int((d.label == 0).sum()),
                     "phishing": int((d.label == 1).sum()),
                     "phishing_pct": round(100 * d.label.mean(), 2)})
    return pd.DataFrame(rows)


def source_label_table(df: pd.DataFrame) -> pd.DataFrame:
    t = pd.crosstab(df["source"], df["label"]).rename(columns={0: "legitimate", 1: "phishing"})
    t["total"] = t.sum(axis=1)
    t["phishing_pct"] = (100 * t["phishing"] / t["total"]).round(1)
    return t


def source_only_accuracy(df: pd.DataFrame) -> float:
    """Accuracy of a 'model' that only knows which corpus an email came from and
    predicts that corpus's majority label. This is the ceiling of pure corpus leakage."""
    return float(pd.crosstab(df["source"], df["label"]).max(axis=1).sum() / len(df))


def split_fingerprint(d: pd.DataFrame) -> str:
    """Hash of the sorted ids: lets two people confirm they have identical splits."""
    return hashlib.sha1("\n".join(sorted(d["id"])).encode()).hexdigest()[:12]


# ------------------------------------------------------------------ main

COLUMNS = ["id", "subject", "body", "text", "label", "source"]


def build(raw_dir: Path = RAW_DIR, out_dir: Path = PROCESSED_DIR, results_dir: Path = RESULTS_DIR) -> dict:
    raw = load_raw(raw_dir)
    df = clean(raw)
    df, junk = drop_junk(df)
    df, dedup = deduplicate(df)
    df = add_ids(df)
    splits = split(df)
    report = save_outputs(raw, df, splits, junk, dedup, out_dir, results_dir)
    return {"df": df, "splits": splits, "report": report, "raw": raw}


def save_outputs(raw: pd.DataFrame, df: pd.DataFrame, splits: dict[str, pd.DataFrame], junk: dict,
                 dedup: dict, out_dir: Path = PROCESSED_DIR, results_dir: Path = RESULTS_DIR) -> dict:
    assert df["id"].is_unique
    out_dir.mkdir(parents=True, exist_ok=True)
    results_dir.mkdir(parents=True, exist_ok=True)
    for name, d in splits.items():
        d[COLUMNS].reset_index(drop=True).to_parquet(out_dir / f"{name}.parquet", index=False)

    summary = split_summary(splits)
    summary.to_csv(results_dir / "data_split_summary.csv", index=False)
    source_label_table(df).to_csv(results_dir / "data_source_label.csv")
    report = {
        "raw_rows": len(raw), "junk_removed": junk, "dedup": dedup, "final_rows": len(df),
        "source_only_accuracy": round(source_only_accuracy(df), 4),
        "majority_class_accuracy": round(float(max(df.label.mean(), 1 - df.label.mean())), 4),
        "split_fingerprints": {k: split_fingerprint(v) for k, v in splits.items()},
        "seed": SEED,
    }
    (results_dir / "data_report.json").write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    out = build()
    print(json.dumps(out["report"], indent=2))
    print(split_summary(out["splits"]).to_string(index=False))
