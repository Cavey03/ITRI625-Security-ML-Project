"""Real-API tests beyond the shared contract: training/serving parity, explanation
details, and behaviour when the model can't be loaded."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import api.main as api_main
from api.schemas import MAX_CHARS

ROOT = Path(__file__).resolve().parents[1]
HAS_MODEL = (Path(api_main.MODEL_DIR) / "config.json").exists()
needs_model = pytest.mark.skipif(not HAS_MODEL, reason="no trained checkpoint in models/")


@pytest.fixture(scope="module")
def client():
    with TestClient(api_main.app) as c:
        yield c


@needs_model
def test_serving_matches_notebook_predictions(client, tmp_path):
    """The API must reproduce the notebook's test-set probabilities: same cleaning,
    same truncation, same weights. A mismatch here means training/serving skew."""
    preds = ROOT / "results" / "distilbert_test_predictions.csv"
    test = ROOT / "data" / "processed" / "test.parquet"
    if not (preds.exists() and test.exists()):
        pytest.skip("needs results/distilbert_test_predictions.csv and the processed test split")
    sample = (pd.read_parquet(test).merge(pd.read_csv(preds, dtype={"id": str}), on=["id", "label"])
              .sample(300, random_state=0))
    csv_path = tmp_path / "sample.csv"
    sample[["id", "subject", "body"]].to_csv(csv_path, index=False)
    with csv_path.open("rb") as f:
        out = client.post("/predict_batch", files={"file": ("s.csv", f, "text/csv")}).json()
    # Emails over the contract's MAX_CHARS are rejected per row (4 of 11,136 test emails);
    # the notebook scored them by truncation, so compare only the rows the API accepted.
    too_long = ((sample.body.str.len() > MAX_CHARS) | (sample.subject.str.len() > MAX_CHARS)).to_numpy()
    rejected = np.array([r["probability_phishing"] is None for r in out["results"]])
    assert (rejected == too_long).all()
    api_p = np.array([r["probability_phishing"] for r in out["results"]])[~rejected].astype(float)
    nb_p = sample.prob_phishing.to_numpy()[~rejected]
    # The notebook evaluated in bf16 mixed precision, the API runs in float32: allow small drift.
    assert np.abs(api_p - nb_p).max() < 0.05
    assert ((api_p >= 0.5) == (nb_p >= 0.5)).mean() >= 0.99


@needs_model
def test_explain_highlights_cleaned_text_and_flags_truncation(client):
    short = client.post("/explain", json={"subject": "Verify now",
                                          "body": "Contact <b>bob@corp.example.com</b> in 2019"}).json()
    assert short["body"] == "Contact [email] in [year]"        # HTML stripped, address + year masked
    assert not short["truncated"]
    for w in short["words"]:
        text = short["subject"] if w["field"] == "subject" else short["body"]
        assert text[w["start"]:w["end"]] == w["word"]

    long = client.post("/explain", json={"subject": "", "body": "word " * 600}).json()
    assert long["truncated"]
    assert 0 < len(long["words"]) < 600                          # words past the cut-off are not scored


@needs_model
def test_explain_without_subject_uses_body_offsets(client):
    r = client.post("/explain", json={"subject": "", "body": "please verify your account"}).json()
    assert {w["field"] for w in r["words"]} == {"body"}
    assert [w["word"] for w in r["words"]] == ["please", "verify", "your", "account"]


def test_missing_model_returns_503(monkeypatch):
    monkeypatch.setattr(api_main, "MODEL_DIR", str(ROOT / "models" / "does_not_exist"))
    with TestClient(api_main.app) as c:
        h = c.get("/health").json()
        assert h["status"] == "error" and not h["model_loaded"]
        r = c.post("/predict", json={"subject": "hi", "body": "there"})
        assert r.status_code == 503 and "not loaded" in r.json()["detail"]
