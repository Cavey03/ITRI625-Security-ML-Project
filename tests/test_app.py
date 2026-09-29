"""Desktop app tests: file loading, highlight maths, API client (against a live mock
server), and a GUI smoke test that renders a result without opening a visible window."""
import socket
import threading
import time
import tkinter as tk

import pytest
import uvicorn

from api.mock_app import app as mock_app
from app import highlight
from app.api_client import ApiClient, ApiError
from app.eml_loader import load_email

# ------------------------------------------------------------------ eml / txt loading

PLAIN_EML = b"""From: Northwind Bank <alerts@northwind.example.com>
To: you@example.org
Subject: Unusual sign-in
MIME-Version: 1.0
Content-Type: text/plain; charset="utf-8"

Please verify your account.
"""

HTML_EML = b"""Subject: =?utf-8?B?WW91ciBwYWNrYWdl?=
MIME-Version: 1.0
Content-Type: text/html; charset="utf-8"

<html><body><p>Track <b>here</b></p></body></html>
"""

MULTIPART_EML = b"""Subject: Newsletter
MIME-Version: 1.0
Content-Type: multipart/alternative; boundary="XX"

--XX
Content-Type: text/plain; charset="utf-8"

Plain version
--XX
Content-Type: text/html; charset="utf-8"

<p>HTML version</p>
--XX--
"""

BAD_CHARSET_EML = b"""Subject: Odd
Content-Type: text/plain; charset="x-unknown-charset"

Hello \xe9
"""


@pytest.mark.parametrize("data,subject,body", [
    (PLAIN_EML, "Unusual sign-in", "Please verify your account."),
    (HTML_EML, "Your package", "<html><body><p>Track <b>here</b></p></body></html>"),
    (MULTIPART_EML, "Newsletter", "Plain version"),       # prefers text/plain
])
def test_load_eml(tmp_path, data, subject, body):
    p = tmp_path / "m.eml"
    p.write_bytes(data)
    assert load_email(p) == (subject, body)


def test_load_eml_unknown_charset_does_not_crash(tmp_path):
    p = tmp_path / "m.eml"
    p.write_bytes(BAD_CHARSET_EML)
    subject, body = load_email(p)
    assert subject == "Odd" and body.startswith("Hello")


def test_load_txt(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("Subject: Hi there\n\nLine one\nLine two\n", encoding="utf-8")
    assert load_email(p) == ("Hi there", "Line one\nLine two")
    p.write_text("no subject line\nsecond", encoding="utf-8")
    assert load_email(p) == ("", "no subject line\nsecond")


# ------------------------------------------------------------------ highlight maths

def test_tag_buckets():
    assert highlight.tag_for(0.9) == "phish_3"
    assert highlight.tag_for(0.5) == "phish_2"
    assert highlight.tag_for(-0.2) == "legit_1"
    assert highlight.tag_for(0.1) is None


def test_spans_point_at_the_right_characters():
    text, offsets = highlight.layout("Urgent 😀 now", "Please verify")
    words = [{"field": "subject", "start": 0, "end": 6, "word": "Urgent", "score": 0.9},
             {"field": "subject", "start": 9, "end": 12, "word": "now", "score": 0.5},
             {"field": "body", "start": 7, "end": 13, "word": "verify", "score": 1.0},
             {"field": "body", "start": 0, "end": 6, "word": "Please", "score": 0.05}]
    spans = highlight.spans(words, offsets)
    assert [text[s.start:s.end] for s in spans] == ["Urgent", "now", "verify"]   # "Please" below threshold


# ------------------------------------------------------------------ API client vs live mock

def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def live_url():
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(mock_app, host="127.0.0.1", port=port, log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=5)


def test_client_health_and_explain(live_url):
    c = ApiClient(live_url)
    assert c.health().model_loaded
    r = c.explain("URGENT", "verify your password", threshold=0.5)
    assert r.label == "phishing" and r.words


def test_client_batch(live_url, tmp_path):
    p = tmp_path / "b.csv"
    p.write_text('id,subject,body\na,Hi,"thanks, see attached"\nb,,\n', encoding="utf-8")
    r = ApiClient(live_url).predict_batch(p)
    assert r.n_rows == 2 and r.n_scored == 1 and r.results[1].error


def test_client_surfaces_validation_detail(live_url):
    with pytest.raises(ApiError) as e:
        ApiClient(live_url).explain("", "   ")
    assert e.value.status == 422 and "empty" in str(e.value)


def test_client_server_down():
    with pytest.raises(ApiError) as e:
        ApiClient(f"http://127.0.0.1:{_free_port()}").health()
    assert e.value.status is None and "Cannot reach" in str(e.value)


# ------------------------------------------------------------------ GUI smoke test

@pytest.fixture
def gui(live_url):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display available")
    root.withdraw()
    from app.main import App
    app = App(root, ApiClient(live_url))
    yield app
    root.destroy()


def test_gui_renders_result_and_threshold_is_local(gui, live_url):
    result = ApiClient(live_url).explain("Urgent", "Please verify your account. Thanks", threshold=0.5)
    gui.show_result(result)
    assert gui.verdict.cget("text") == ("PHISHING" if result.probability_phishing >= 0.5 else "LEGITIMATE")
    ranges = gui.explain.tag_ranges("phish_3")
    assert ranges and gui.explain.get(ranges[0], ranges[1]) in {"Urgent", "verify"}

    gui.threshold.set(0.95)      # above the probability: flips locally, no request needed
    gui._on_threshold()
    assert gui.verdict.cget("text") == "LEGITIMATE"
