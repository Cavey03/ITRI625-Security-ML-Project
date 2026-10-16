"""End-to-end check of the desktop app against the REAL API.

Starts `uvicorn api.main:app` as a separate process, drives the Tkinter app through
every feature (check, highlighting, threshold slider, truncation note, .eml loading,
batch CSV + export + double-click, API going down and coming back) and prints one
PASS/FAIL line per check. Needs the trained model in models/distilbert_best and a display.

Usage (from the repo root):  python scripts/check_app_e2e.py [output_dir]
Screenshots and the API log go to output_dir (default: a new temp folder).
Error dialogs are recorded instead of shown, so the run never blocks on a popup.
"""
import csv, ctypes, subprocess, sys, tempfile, time, tkinter as tk
from pathlib import Path
from tkinter import ttk

import requests
from PIL import ImageGrab

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SP = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="app_e2e_"))
SP.mkdir(parents=True, exist_ok=True)
PORT = 8791
URL = f"http://127.0.0.1:{PORT}"
PY = sys.executable
if sys.platform == "win32":
    ctypes.windll.shcore.SetProcessDpiAwareness(2)   # screenshots at real pixel size

import app.main as appmain
from app.api_client import ApiClient

results = []
def check(name, ok, detail=""):
    results.append(ok); print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}", flush=True)

errors_shown = []
appmain.messagebox.showerror = lambda title, msg, **k: errors_shown.append(msg)
appmain.messagebox.showinfo = lambda title, msg, **k: errors_shown.append(msg)

def start_api():
    log = open(SP / "api_log.txt", "a")
    p = subprocess.Popen([PY, "-m", "uvicorn", "api.main:app", "--port", str(PORT)], cwd=ROOT, stdout=log, stderr=log)
    for _ in range(120):
        try:
            if requests.get(URL + "/health", timeout=1).json()["model_loaded"]:
                return p
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("API did not start")

def explain_calls():
    return (SP / "api_log.txt").read_text(errors="ignore").count('"POST /explain')

(SP / "api_log.txt").write_text("")
api = start_api()

root = tk.Tk(); root.geometry("1180x720+40+40"); root.attributes("-topmost", True)
if sys.platform == "win32":
    ttk.Style(root).theme_use("vista")
app = appmain.App(root, ApiClient(URL))

def pump(seconds):
    end = time.time() + seconds
    while time.time() < end:
        root.update(); time.sleep(0.02)

def wait_for(cond, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        root.update(); time.sleep(0.02)
        if cond(): return True
    return False

def grab(name):
    root.update(); x, y = root.winfo_rootx(), root.winfo_rooty()
    ImageGrab.grab(bbox=(x, y, x + root.winfo_width(), y + root.winfo_height())).save(SP / f"{name}.png")

def run_check(subject, body):
    app.last_result = None
    app._set_input(subject, body); app.check()
    return wait_for(lambda: app.last_result is not None and str(app.check_btn.cget("state")) == "normal")

# 1. startup health
check("status line shows real model", wait_for(lambda: "distilbert" in app.status.cget("text"), 15), app.status.cget("text"))

# 2. phishing email
ok = run_check("Your account has been suspended",
               "Dear customer,\n\nWe detected unusual sign-in activity on your account. Please verify your password "
               "immediately at http://secure-login.example.com or your account will be closed within 24 hours.\n\n"
               "Security Team")
r = app.last_result
check("phishing email flagged", ok and app.verdict.cget("text") == "PHISHING", f"p={r.probability_phishing:.4f}")
check("explanation highlights words", bool(app.explain.tag_ranges("phish_3")))
check("body newlines preserved in explanation", "\n" in r.body)
pump(0.5); grab("app_real_phishing")

# 3. threshold slider is local
n_before = explain_calls()
app.threshold.set(0.95); app._on_threshold(); pump(0.3)
check("slider keeps PHISHING at 0.95 (p=%.4f)" % r.probability_phishing, app.verdict.cget("text") == "PHISHING")
app.threshold.set(0.999 if r.probability_phishing < 0.999 else 0.9999); app._on_threshold(); pump(0.3)
flipped = app.verdict.cget("text") == ("LEGITIMATE" if r.probability_phishing < app.threshold.get() else "PHISHING")
check("slider re-labels without a request", flipped and explain_calls() == n_before, f"explain calls {n_before}->{explain_calls()}")
app.threshold.set(0.5); app._on_threshold()

# 4. legitimate email
ok = run_check("Project review moved to Thursday",
               "Hi team,\n\nThe project review is moved to Thursday 10am in room 2. I attached the updated slides.\n\nThanks,\nSam")
check("legitimate email passes", ok and app.verdict.cget("text") == "LEGITIMATE", f"p={app.last_result.probability_phishing:.4f}")
pump(0.5); grab("app_real_legit")

# 5. long email -> truncation note
ok = run_check("Quarterly newsletter", "Here is our news for this quarter. " * 120)
check("long email shows truncation note", ok and "first part" in app.note.cget("text"))

# 6. .eml loading via the loader used by the Load button
eml = SP / "sample.eml"
eml.write_text("Subject: Invoice overdue\nContent-Type: text/html; charset=utf-8\n\n"
               "<html><body><p>Your invoice is overdue. <b>Pay now</b> at http://pay-invoices.example.net</p></body></html>\n")
appmain.filedialog.askopenfilename = lambda **k: str(eml)
app.load_file()
check(".eml loads into the form", app.subject.get() == "Invoice overdue" and "<b>Pay now</b>" in app.body.get("1.0", "end"))
ok = run_check(app.subject.get(), app.body.get("1.0", "end-1c"))
check("HTML stripped before highlighting", ok and "<b>" not in app.last_result.body, repr(app.last_result.body[:60]))

# 7. batch CSV
batch = SP / "batch.csv"
rows = [("1", "URGENT: account suspended", "Verify your password immediately at http://secure-bank.example.com"),
        ("2", "Lunch on Friday?", "Are we still on for lunch on Friday? Let me know. Thanks"),
        ("3", "You have won a prize", "Congratulations! Click here to claim your free gift card now"),
        ("4", "", ""),
        ("5", "Minutes from today", "Attached are the minutes from today's meeting. Action items are on page 2."),
        ("6", "Mailbox full", "Your mailbox is almost full. Log in here to upgrade your storage: http://mail-upgrade.example.org"),
        ("7", "Long one", "x" * 120_000)]
with batch.open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f); w.writerow(["id", "subject", "body"]); w.writerows(rows)
appmain.filedialog.askopenfilename = lambda **k: str(batch)
app.tabs.select(app.batch_tab); app.open_batch()
ok = wait_for(lambda: len(app.tree.get_children()) == len(rows))
errs = [app.batch_rows[i]["error"] for i in (3, 6)]
check("batch scores rows and reports bad rows", ok and all(errs), app.batch_summary.cget("text"))
pump(0.5); grab("app_real_batch")
appmain.filedialog.asksaveasfilename = lambda **k: str(SP / "batch_results.csv")
app.export_batch()
check("batch export written", (SP / "batch_results.csv").exists() and len((SP / "batch_results.csv").read_text().splitlines()) == len(rows) + 1)

# 8. double-click a batch row -> single tab check
app.tree.selection_set("5"); app._open_batch_row(None)
ok = wait_for(lambda: app.last_result is not None and app.subject.get() == "Mailbox full")
check("double-click opens row in single tab", ok)
wait_for(lambda: str(app.check_btn.cget("state")) == "normal")

# 9. API down -> graceful error, then recovery
api.terminate(); api.wait()
errors_shown.clear()
app._set_input("Test", "is the API there?"); app.check()
ok = wait_for(lambda: bool(errors_shown) and str(app.check_btn.cget("state")) == "normal", 30)
check("API down: error shown, app still usable", ok and "Cannot reach" in errors_shown[0])
check("API down: status line turns red", "Cannot reach" in app.status.cget("text") or "unreachable" in app.status.cget("text").lower(),
      app.status.cget("text"))
pump(0.3); grab("app_real_down")
api = start_api()
app.check_health(manual=True)
check("API back: status recovers", wait_for(lambda: "distilbert" in app.status.cget("text"), 20))
ok = run_check("Test", "is the API there?")
check("API back: checks work again", ok)

root.destroy(); api.terminate()
print(f"\n{sum(results)}/{len(results)} checks passed. Screenshots and API log in {SP}")
sys.exit(0 if all(results) else 1)
