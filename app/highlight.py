"""Turn /explain word scores into highlight spans. No Tk here, so it can be unit-tested.

Colours: red = pushes towards phishing, blue = pushes towards legitimate.
(Red/blue rather than red/green so colour-blind users can tell them apart.)
"""
from __future__ import annotations

from dataclasses import dataclass

# |score| thresholds -> intensity level. Below the lowest threshold: not highlighted.
LEVELS = ((0.7, 3), (0.4, 2), (0.15, 1))

# (background, foreground) per tag. Level 3 backgrounds are dark enough to need white text.
TAG_STYLES = {
    "phish_1": ("#fbd9d9", "#0b0b0b"), "phish_2": ("#f4a3a3", "#0b0b0b"), "phish_3": ("#d93b3b", "#ffffff"),
    "legit_1": ("#d9e7f8", "#0b0b0b"), "legit_2": ("#a3c6ef", "#0b0b0b"), "legit_3": ("#2a6fc4", "#ffffff"),
}

SUBJECT_PREFIX = "Subject: "


@dataclass(frozen=True)
class Span:
    tag: str
    start: int   # character offset in the displayed text
    end: int
    word: str
    score: float


def tag_for(score: float) -> str | None:
    magnitude = abs(score)
    for threshold, level in LEVELS:
        if magnitude >= threshold:
            return f"{'phish' if score > 0 else 'legit'}_{level}"
    return None


def layout(subject: str, body: str) -> tuple[str, dict[str, int]]:
    """Text shown in the explanation box, and where each field starts in it."""
    text = f"{SUBJECT_PREFIX}{subject}\n\n{body}"
    return text, {"subject": len(SUBJECT_PREFIX), "body": len(SUBJECT_PREFIX) + len(subject) + 2}


def spans(words: list[dict], offsets: dict[str, int]) -> list[Span]:
    out = []
    for w in words:
        tag = tag_for(w["score"])
        if tag is None:
            continue
        base = offsets[w["field"]]
        out.append(Span(tag, base + w["start"], base + w["end"], w["word"], w["score"]))
    return out


def top_words(words: list[dict], n: int = 5) -> tuple[list[dict], list[dict]]:
    """Strongest phishing-leaning and legitimate-leaning words, for the summary line."""
    ranked = sorted(words, key=lambda w: w["score"])
    phish = [w for w in reversed(ranked) if w["score"] > 0][:n]
    legit = [w for w in ranked if w["score"] < 0][:n]
    return phish, legit
