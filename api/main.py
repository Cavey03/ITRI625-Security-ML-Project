"""Real phishing-classifier API: serves the fine-tuned DistilBERT model.

Implements the contract in api/schemas.py (same as api/mock_app.py).

Run:   uvicorn api.main:app --port 8000
Docs:  http://127.0.0.1:8000/docs
Env:   PHISH_MODEL_DIR (default models/distilbert_best), PHISH_DEVICE (cuda / cpu)

The model is loaded ONCE at startup (lifespan), not per request. If loading fails,
/health reports status "error" and every prediction endpoint returns 503.
"""
from __future__ import annotations

import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from api.common import prediction, read_batch_csv, row_problem
from api.model import DEFAULT_MODEL_DIR, PhishingClassifier
from api.schemas import BatchOut, BatchRow, EmailIn, ExplainIn, ExplainOut, HealthOut, Prediction, WordScore
from src.preprocess import clean_email

log = logging.getLogger("uvicorn.error")
MODEL_DIR = os.environ.get("PHISH_MODEL_DIR", str(DEFAULT_MODEL_DIR))
STATE: dict = {"model": None, "status": "loading", "error": None}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    STATE.update(model=None, status="loading", error=None)   # never serve a stale model
    t0 = time.time()
    try:
        STATE["model"] = PhishingClassifier(MODEL_DIR, device=os.environ.get("PHISH_DEVICE"))
        STATE["status"] = "ok"
        log.info("model %s loaded on %s in %.1fs", STATE["model"].version, STATE["model"].device, time.time() - t0)
    except Exception as exc:   # keep the server up so /health can report the problem
        STATE["status"], STATE["error"] = "error", f"{type(exc).__name__}: {exc}"
        log.error("could not load model from %s: %s", MODEL_DIR, STATE["error"])
    yield
    STATE["model"] = None


app = FastAPI(title="Phishing email classifier", version="1.0", lifespan=lifespan)


def _model() -> PhishingClassifier:
    if STATE["model"] is None:
        raise HTTPException(503, f"model not loaded ({STATE['status']}): {STATE['error'] or 'starting up'}")
    return STATE["model"]


@app.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    m = STATE["model"]
    return HealthOut(status=STATE["status"], model_loaded=m is not None,
                     model_version=m.version if m else None, device=str(m.device) if m else None)


@app.post("/predict", response_model=Prediction)
def predict(email: EmailIn) -> Prediction:
    m = _model()
    return Prediction(**prediction(m.predict(email.subject, email.body), email.threshold, m.version))


@app.post("/explain", response_model=ExplainOut)
def explain(req: ExplainIn) -> ExplainOut:
    m = _model()
    e = m.explain(req.subject, req.body)
    return ExplainOut(**prediction(e.probability, req.threshold, m.version), method=req.method,
                      subject=e.subject, body=e.body, truncated=e.truncated,
                      words=[WordScore(**w) for w in e.words])


@app.post("/predict_batch", response_model=BatchOut)
async def predict_batch(file: UploadFile = File(...), threshold: float = Query(0.5, ge=0.0, le=1.0)) -> BatchOut:
    m = _model()
    rows = await read_batch_csv(file)
    results: list[BatchRow | None] = [None] * len(rows)
    to_score = []
    for i, r in enumerate(rows):
        subject, body = r.get("subject") or "", r.get("body") or ""
        if problem := row_problem(subject, body):
            results[i] = BatchRow(row=i, id=r.get("id"), label=None, label_id=None,
                                  probability_phishing=None, error=problem)
        else:
            to_score.append((i, clean_email(subject, body)[2]))
    probs = m.predict_texts([t for _, t in to_score])
    for (i, _), p in zip(to_score, probs):
        pr = prediction(p, threshold, m.version)
        results[i] = BatchRow(row=i, id=rows[i].get("id"), label=pr["label"], label_id=pr["label_id"],
                              probability_phishing=pr["probability_phishing"])
    return BatchOut(n_rows=len(rows), n_scored=len(to_score), threshold=threshold,
                    model_version=m.version, results=results)
