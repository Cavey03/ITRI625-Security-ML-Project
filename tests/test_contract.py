"""Contract tests. Any app that claims to implement api/schemas.py must pass these.

Milestone 8 adds the real API to APPS, so the mock and the real service are held
to exactly the same contract.
"""
import pytest
from fastapi.testclient import TestClient

from api.mock_app import app as mock_app
from api.schemas import BatchOut, ExplainOut, HealthOut, Prediction

APPS = {"mock": mock_app}

PHISH = {"subject": "URGENT: account suspended",
         "body": "Verify your password immediately at http://secure-bank.example.com"}
LEGIT = {"subject": "Project meeting", "body": "Thanks, the schedule is attached. Regards, Sam"}


@pytest.fixture(params=list(APPS), scope="module")
def client(request):
    with TestClient(APPS[request.param]) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    h = HealthOut.model_validate(r.json())
    assert h.model_loaded and h.status == "ok"


def test_predict_shape_and_label_consistency(client):
    for email in (PHISH, LEGIT):
        p = Prediction.model_validate(client.post("/predict", json=email).json())
        assert p.label_id == int(p.probability_phishing >= p.threshold)
        assert p.label == ("legitimate", "phishing")[p.label_id]


def test_threshold_changes_label_not_probability(client):
    lo = client.post("/predict", json={**LEGIT, "threshold": 0.0}).json()
    hi = client.post("/predict", json={**LEGIT, "threshold": 1.0}).json()
    assert lo["probability_phishing"] == hi["probability_phishing"]
    assert lo["label"] == "phishing"


@pytest.mark.parametrize("bad", [
    {"subject": "", "body": "   "},                 # both blank
    {"subject": "hi"},                              # body missing
    {"subject": "hi", "body": "x", "threshold": 2},  # threshold out of range
])
def test_predict_rejects_bad_input(client, bad):
    r = client.post("/predict", json=bad)
    assert r.status_code == 422
    assert "detail" in r.json()


def test_explain_offsets_point_at_words(client):
    e = ExplainOut.model_validate(client.post("/explain", json=PHISH).json())
    assert e.words, "expected at least one scored word"
    for w in e.words:
        text = e.subject if w.field == "subject" else e.body
        assert text[w.start:w.end] == w.word
    assert max(abs(w.score) for w in e.words) == pytest.approx(1.0)


def test_predict_batch(client):
    csv_bytes = ("id,subject,body\n"
                 f"a,{PHISH['subject']},{PHISH['body']}\n"
                 "b,,\n"
                 f"c,{LEGIT['subject']},\"{LEGIT['body']}\"\n").encode()
    r = client.post("/predict_batch?threshold=0.5",
                    files={"file": ("emails.csv", csv_bytes, "text/csv")})
    assert r.status_code == 200
    b = BatchOut.model_validate(r.json())
    assert (b.n_rows, b.n_scored) == (3, 2)
    assert [x.id for x in b.results] == ["a", "b", "c"]
    assert b.results[1].error and b.results[1].probability_phishing is None


def test_predict_batch_requires_body_column(client):
    r = client.post("/predict_batch", files={"file": ("x.csv", b"subject\nhello\n", "text/csv")})
    assert r.status_code == 400
