"""Mock API: implements the contract in api/schemas.py with FAKE scores.

Lets the desktop app be built and tested before the real model exists.
Scores come from a keyword heuristic, NOT a model. Never use them as results.

Run:  uvicorn api.mock_app:app --port 8000
Docs: http://127.0.0.1:8000/docs
"""
from __future__ import annotations

import math
import re

from fastapi import FastAPI, File, Query, UploadFile

from api.common import prediction, read_batch_csv, row_problem
from api.schemas import BatchOut, BatchRow, EmailIn, ExplainIn, ExplainOut, HealthOut, Prediction, WordScore

MODEL_VERSION = "mock-0"

app = FastAPI(title="Phishing classifier (MOCK)", version="1.0")

# word -> weight; positive = phishing-leaning
_KEYWORDS = {
    "verify": 1.0, "urgent": 0.9, "suspended": 0.9, "password": 0.8, "account": 0.5,
    "click": 0.7, "login": 0.7, "bank": 0.6, "winner": 0.9, "prize": 0.8,
    "immediately": 0.7, "confirm": 0.6, "http": 0.5, "https": 0.3,
    "meeting": -0.7, "thanks": -0.6, "attached": -0.5, "regards": -0.5,
    "schedule": -0.6, "project": -0.5, "lunch": -0.6, "team": -0.4,
}
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_WORD = re.compile(r"\S+")


def _clean(text: str) -> str:
    return _WS.sub(" ", _TAG.sub(" ", text)).strip()


def _word_weight(word: str) -> float:
    w = word.lower().strip(".,:;!?()[]\"'")
    for key, weight in _KEYWORDS.items():
        if w.startswith(key):
            return weight
    return 0.0


def _score(subject: str, body: str) -> tuple[str, str, list[tuple[str, int, int, str, float]], float]:
    subject, body = _clean(subject), _clean(body)
    words = [(field, m.start(), m.end(), m.group(), _word_weight(m.group()))
             for field, text in (("subject", subject), ("body", body))
             for m in _WORD.finditer(text)]
    logit = -1.0 + sum(w[4] for w in words)
    return subject, body, words, 1 / (1 + math.exp(-logit))


def _prediction(prob: float, threshold: float) -> dict:
    return prediction(prob, threshold, MODEL_VERSION)


@app.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok", model_loaded=True, model_version=MODEL_VERSION, device="mock")


@app.post("/predict", response_model=Prediction)
def predict(email: EmailIn) -> Prediction:
    *_, prob = _score(email.subject, email.body)
    return Prediction(**_prediction(prob, email.threshold))


@app.post("/explain", response_model=ExplainOut)
def explain(req: ExplainIn) -> ExplainOut:
    subject, body, words, prob = _score(req.subject, req.body)
    peak = max((abs(w[4]) for w in words), default=0.0) or 1.0
    return ExplainOut(
        **_prediction(prob, req.threshold), method=req.method, subject=subject, body=body,
        truncated=False,
        words=[WordScore(field=f, start=s, end=e, word=t, score=round(v / peak, 4))
               for f, s, e, t, v in words],
    )


@app.post("/predict_batch", response_model=BatchOut)
async def predict_batch(file: UploadFile = File(...),
                        threshold: float = Query(0.5, ge=0.0, le=1.0)) -> BatchOut:
    rows = await read_batch_csv(file)

    results = []
    for i, r in enumerate(rows):
        subject, body = r.get("subject") or "", r.get("body") or ""
        if problem := row_problem(subject, body):
            results.append(BatchRow(row=i, id=r.get("id"), label=None, label_id=None,
                                    probability_phishing=None, error=problem))
            continue
        *_, prob = _score(subject, body)
        p = _prediction(prob, threshold)
        results.append(BatchRow(row=i, id=r.get("id"), label=p["label"], label_id=p["label_id"],
                                probability_phishing=p["probability_phishing"]))
    return BatchOut(n_rows=len(rows), n_scored=sum(r.error is None for r in results),
                    threshold=threshold, model_version=MODEL_VERSION, results=results)
