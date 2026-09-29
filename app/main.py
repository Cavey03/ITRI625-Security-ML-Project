"""Phishing Email Checker: Tkinter desktop client for the phishing API.

Run the API first (mock for now):   uvicorn api.mock_app:app --port 8000
Then:                               python -m app.main [--api-url http://127.0.0.1:8000]

Threading: every API call runs in a worker thread. Tk widgets may only be touched
from the main thread, so workers put (callback, result) on a queue and the main
loop drains it every 50 ms.
"""
from __future__ import annotations

import argparse
import csv
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font, messagebox, ttk

from api.schemas import MAX_CHARS
from app import highlight
from app.api_client import ApiClient, ApiError
from app.eml_loader import load_email

PHISH_RED = "#c62828"
LEGIT_BLUE = "#1f5fae"
OK_GREEN = "#1a7f37"
MUTED = "#5f5e5a"
HEALTH_EVERY_MS = 15_000


class App(ttk.Frame):
    def __init__(self, root: tk.Tk, client: ApiClient):
        super().__init__(root, padding=10)
        self.root, self.client = root, client
        self.jobs: queue.Queue = queue.Queue()
        self.threshold = tk.DoubleVar(value=0.5)
        self.last_result = None           # ExplainOut of the last check
        self.batch_rows: list[dict] = []  # merged CSV rows + predictions
        self.batch_path: Path | None = None

        self._fonts()
        self.grid(sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._build_header()
        tabs = ttk.Notebook(self)
        tabs.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        self.tabs = tabs
        self.single_tab = ttk.Frame(tabs, padding=8)
        self.batch_tab = ttk.Frame(tabs, padding=8)
        tabs.add(self.single_tab, text="  Single email  ")
        tabs.add(self.batch_tab, text="  Batch CSV  ")
        self._build_single_tab()
        self._build_batch_tab()

        root.bind("<Control-Return>", lambda _e: self.check())
        root.after(50, self._drain_jobs)
        self.check_health()

    # ------------------------------------------------------------ layout

    def _fonts(self):
        base = font.nametofont("TkDefaultFont")
        self.f_bold = base.copy(); self.f_bold.configure(weight="bold")
        self.f_verdict = base.copy(); self.f_verdict.configure(size=22, weight="bold")
        self.f_small = base.copy(); self.f_small.configure(size=max(base.cget("size") - 1, 8))
        self.f_text = font.nametofont("TkTextFont").copy(); self.f_text.configure(size=10)

    def _build_header(self):
        bar = ttk.Frame(self)
        bar.grid(row=0, column=0, sticky="ew")
        bar.columnconfigure(3, weight=1)

        ttk.Label(bar, text="API").grid(row=0, column=0, padx=(0, 4))
        self.url_var = tk.StringVar(value=self.client.base_url)
        url = ttk.Entry(bar, textvariable=self.url_var, width=28)
        url.grid(row=0, column=1)
        url.bind("<Return>", lambda _e: self.check_health(manual=True))
        ttk.Button(bar, text="Reconnect", command=lambda: self.check_health(manual=True)).grid(row=0, column=2, padx=4)
        self.status = tk.Label(bar, text="● checking…", fg=MUTED, anchor="w")
        self.status.grid(row=0, column=3, sticky="w", padx=8)

        ttk.Label(bar, text="Decision threshold").grid(row=0, column=4, padx=(8, 4))
        ttk.Scale(bar, from_=0.05, to=0.95, variable=self.threshold, length=180,
                  command=self._on_threshold).grid(row=0, column=5)
        self.thr_label = ttk.Label(bar, text="0.50", width=5, font=self.f_bold)
        self.thr_label.grid(row=0, column=6, padx=(4, 0))

    def _build_single_tab(self):
        tab = self.single_tab
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)
        panes = ttk.PanedWindow(tab, orient="horizontal")
        panes.grid(row=0, column=0, sticky="nsew")

        # --- left: input
        left = ttk.Frame(panes, padding=(0, 0, 8, 0))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(3, weight=1)
        ttk.Label(left, text="Subject", font=self.f_bold).grid(row=0, column=0, sticky="w")
        self.subject = ttk.Entry(left)
        self.subject.grid(row=1, column=0, sticky="ew", pady=(2, 8))
        ttk.Label(left, text="Body", font=self.f_bold).grid(row=2, column=0, sticky="nw")
        self.body = self._scrolled_text(left, row=3)
        buttons = ttk.Frame(left)
        buttons.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(buttons, text="Load .txt / .eml…", command=self.load_file).pack(side="left")
        ttk.Button(buttons, text="Clear", command=self.clear).pack(side="left", padx=6)
        self.check_btn = ttk.Button(buttons, text="Check email  (Ctrl+Enter)", command=self.check)
        self.check_btn.pack(side="right")
        panes.add(left, weight=1)

        # --- right: result
        right = ttk.Frame(panes, padding=(8, 0, 0, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(5, weight=1)
        self.verdict = tk.Label(right, text="—", font=self.f_verdict, fg=MUTED, anchor="w")
        self.verdict.grid(row=0, column=0, sticky="w")
        self.prob_label = ttk.Label(right, text="Paste an email or load a file, then press Check.")
        self.prob_label.grid(row=1, column=0, sticky="w")
        # Drawn bar instead of ttk.Progressbar: the Windows theme forces the bar green,
        # which reads as "safe" even at 99% phishing. This one is red/blue by verdict
        # and marks where the threshold sits.
        self.prob_bar = tk.Canvas(right, height=34, highlightthickness=0, bg=self.root.cget("bg"))
        self.prob_bar.grid(row=2, column=0, sticky="ew", pady=(4, 10))
        self.prob_bar.bind("<Configure>", lambda _e: self._draw_prob_bar())

        head = ttk.Frame(right)
        head.grid(row=3, column=0, sticky="ew")
        ttk.Label(head, text="Why? Words that influenced the decision", font=self.f_bold).pack(side="left")
        legend = ttk.Frame(right)
        legend.grid(row=4, column=0, sticky="w", pady=(2, 4))
        for tag, label in (("phish_3", "pushes towards phishing"), ("legit_3", "pushes towards legitimate")):
            bg, _fg = highlight.TAG_STYLES[tag]
            tk.Label(legend, text="   ", bg=bg).pack(side="left")
            ttk.Label(legend, text=f" {label}   ", font=self.f_small).pack(side="left")
        ttk.Label(legend, text="(darker = stronger)", font=self.f_small, foreground=MUTED).pack(side="left")

        self.explain = self._scrolled_text(right, row=5)
        self.explain.configure(state="disabled", cursor="arrow")
        for tag, (bg, fg) in highlight.TAG_STYLES.items():
            self.explain.tag_configure(tag, background=bg, foreground=fg)
        self.explain.tag_configure("prefix", font=self.f_bold)

        self.top_words = ttk.Label(right, text="", font=self.f_small, foreground=MUTED, wraplength=460, justify="left")
        self.top_words.grid(row=6, column=0, sticky="w", pady=(4, 0))
        self.note = ttk.Label(right, text="", font=self.f_small, foreground=PHISH_RED)
        self.note.grid(row=7, column=0, sticky="w")
        panes.add(right, weight=1)

    def _scrolled_text(self, parent, row: int) -> tk.Text:
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        text = tk.Text(frame, wrap="word", undo=True, font=self.f_text, relief="solid", borderwidth=1,
                       padx=6, pady=6, height=12, width=50)
        text.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        sb.grid(row=0, column=1, sticky="ns")
        text.configure(yscrollcommand=sb.set)
        return text

    def _build_batch_tab(self):
        tab = self.batch_tab
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(2, weight=1)
        bar = ttk.Frame(tab)
        bar.grid(row=0, column=0, sticky="ew")
        self.batch_btn = ttk.Button(bar, text="Open CSV…", command=self.open_batch)
        self.batch_btn.pack(side="left")
        self.export_btn = ttk.Button(bar, text="Export results…", command=self.export_batch, state="disabled")
        self.export_btn.pack(side="left", padx=6)
        ttk.Label(bar, text="CSV needs a 'body' column; 'subject' and 'id' are optional. "
                            "Double-click a row to open it in the Single email tab.",
                  font=self.f_small, foreground=MUTED).pack(side="left", padx=8)
        self.batch_summary = ttk.Label(tab, text="No file loaded.")
        self.batch_summary.grid(row=1, column=0, sticky="w", pady=6)

        frame = ttk.Frame(tab)
        frame.grid(row=2, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        cols = ("row", "id", "subject", "probability", "verdict", "error")
        widths = (50, 110, 420, 100, 110, 200)
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        for c, w in zip(cols, widths):
            self.tree.heading(c, text=c.title(), command=lambda c=c: self._sort_tree(c))
            self.tree.column(c, width=w, anchor="w" if c in ("id", "subject", "error") else "center",
                             stretch=c == "subject")
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.tag_configure("phishing", background="#fbe3e3")
        self.tree.bind("<Double-1>", self._open_batch_row)
        self._sort_state: dict[str, bool] = {}

    # ------------------------------------------------------------ threading

    def run_async(self, fn, on_ok, on_err=None):
        def worker():
            try:
                self.jobs.put((on_ok, fn()))
            except ApiError as exc:
                self.jobs.put((on_err or self._show_error, exc))
            except Exception as exc:   # never let a worker die silently
                self.jobs.put((on_err or self._show_error, ApiError(f"Unexpected error: {exc}")))
        threading.Thread(target=worker, daemon=True).start()

    def _drain_jobs(self):
        try:
            while True:
                callback, arg = self.jobs.get_nowait()
                callback(arg)
        except queue.Empty:
            pass
        self.root.after(50, self._drain_jobs)

    def _show_error(self, exc: ApiError):
        if exc.status is None:            # connection-level problem
            self._set_status(False, str(exc).splitlines()[0])
        messagebox.showerror("Phishing Email Checker", str(exc), parent=self.root)

    # ------------------------------------------------------------ health

    def check_health(self, manual: bool = False):
        """manual=True (Reconnect / Enter): show 'checking…' at once so the status is never stale.
        Background checks every 15 s update the status silently."""
        url = self.url_var.get().strip() or self.client.base_url
        if manual:
            self.status.configure(text="● checking…", fg=MUTED)
        if url.rstrip("/") != self.client.base_url:
            self.client = ApiClient(url)
        self.run_async(self.client.health, self._on_health, lambda exc: self._set_status(False, str(exc).splitlines()[0]))
        if hasattr(self, "_health_job"):
            self.root.after_cancel(self._health_job)
        self._health_job = self.root.after(HEALTH_EVERY_MS, self.check_health)

    def _on_health(self, h):
        if h.model_loaded:
            self._set_status(True, f"API connected · model {h.model_version} · {h.device}")
        else:
            self._set_status(False, f"API is up but the model is {h.status}")

    def _set_status(self, ok: bool, text: str):
        self.status.configure(text=f"● {text}", fg=OK_GREEN if ok else PHISH_RED)

    # ------------------------------------------------------------ single email

    def load_file(self):
        path = filedialog.askopenfilename(
            parent=self.root, title="Open an email",
            filetypes=[("Email files", "*.eml *.txt"), ("All files", "*.*")],
            initialdir=Path(__file__).resolve().parents[1] / "samples")
        if not path:
            return
        try:
            subject, body = load_email(path)
        except OSError as exc:
            messagebox.showerror("Could not open file", str(exc), parent=self.root)
            return
        self._set_input(subject, body)
        self.root.title(f"Phishing Email Checker · {Path(path).name}")

    def _set_input(self, subject: str, body: str):
        self.subject.delete(0, "end")
        self.subject.insert(0, subject)
        self.body.delete("1.0", "end")
        self.body.insert("1.0", body)

    def clear(self):
        self._set_input("", "")
        self.last_result = None
        self.verdict.configure(text="—", fg=MUTED)
        self.prob_label.configure(text="Paste an email or load a file, then press Check.")
        self._draw_prob_bar()
        self._write_explanation("", [])
        self.top_words.configure(text="")
        self.note.configure(text="")
        self.root.title("Phishing Email Checker")

    def check(self):
        subject = self.subject.get()
        body = self.body.get("1.0", "end-1c")
        if not (subject.strip() or body.strip()):
            messagebox.showinfo("Nothing to check", "Enter a subject or a body first.", parent=self.root)
            return
        if len(subject) > MAX_CHARS or len(body) > MAX_CHARS:
            messagebox.showwarning("Email too long", f"Subject and body are limited to {MAX_CHARS:,} characters each.",
                                   parent=self.root)
            return
        self.check_btn.configure(state="disabled", text="Checking…")
        self.root.configure(cursor="watch")

        def done(result=None):
            self.check_btn.configure(state="normal", text="Check email  (Ctrl+Enter)")
            self.root.configure(cursor="")

        def ok(result):
            done()
            if "connected" not in self.status.cget("text"):   # API came back: refresh the status line
                self.check_health()
            self.show_result(result)

        def err(exc):
            done()
            self._show_error(exc)

        thr = round(self.threshold.get(), 2)
        self.run_async(lambda: self.client.explain(subject, body, thr), ok, err)

    def show_result(self, result):
        self.last_result = result
        self._render_verdict()
        text, offsets = highlight.layout(result.subject, result.body)
        words = [w.model_dump() for w in result.words]
        self._write_explanation(text, highlight.spans(words, offsets))
        phish, legit = highlight.top_words(words)
        def fmt(ws):
            return " · ".join(w["word"].strip(".,:;!?()[]\"'") or w["word"] for w in ws)
        parts = []
        if phish:
            parts.append("Most phishing-like: " + fmt(phish))
        if legit:
            parts.append("Most legitimate-like: " + fmt(legit))
        self.top_words.configure(text="    ".join(parts))
        self.note.configure(text="Only the first part of this email was analysed (the model reads a limited length)."
                            if result.truncated else "")

    def _render_verdict(self):
        r = self.last_result
        if r is None:
            return
        thr = round(self.threshold.get(), 2)
        is_phish = r.probability_phishing >= thr
        self.verdict.configure(text="PHISHING" if is_phish else "LEGITIMATE", fg=PHISH_RED if is_phish else LEGIT_BLUE)
        self.prob_label.configure(text=f"Phishing probability {100 * r.probability_phishing:.1f}%   "
                                       f"(flagged when ≥ {100 * thr:.0f}%)   ·   model {r.model_version}")
        self._draw_prob_bar()

    def _draw_prob_bar(self):
        c = self.prob_bar
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 10:
            return
        bar_top, bar_bot = 4, 18
        c.create_rectangle(0, bar_top, w - 1, bar_bot, fill="#e4e3df", outline="")
        r = self.last_result
        if r is not None:
            thr = round(self.threshold.get(), 2)
            colour = PHISH_RED if r.probability_phishing >= thr else LEGIT_BLUE
            c.create_rectangle(0, bar_top, max(2, r.probability_phishing * (w - 1)), bar_bot, fill=colour, outline="")
        x = round(self.threshold.get(), 2) * (w - 1)          # threshold marker
        c.create_line(x, 0, x, bar_bot + 4, fill="#0b0b0b", width=2)
        anchor = "ne" if x > w - 45 else "nw" if x < 45 else "n"   # keep the label inside the canvas
        c.create_text(x, bar_bot + 4, text="threshold", anchor=anchor, font=self.f_small, fill=MUTED)

    def _write_explanation(self, text: str, spans: list[highlight.Span]):
        w = self.explain
        w.configure(state="normal")
        w.delete("1.0", "end")
        w.insert("1.0", text)
        if text:
            w.tag_add("prefix", "1.0", f"1.0 + {len(highlight.SUBJECT_PREFIX)} chars")
        for s in spans:
            w.tag_add(s.tag, f"1.0 + {s.start} chars", f"1.0 + {s.end} chars")
        w.configure(state="disabled")

    # ------------------------------------------------------------ threshold

    def _on_threshold(self, _value=None):
        thr = round(self.threshold.get(), 2)
        self.thr_label.configure(text=f"{thr:.2f}")
        self._render_verdict()          # purely local: no API call
        self._refresh_batch_verdicts()

    # ------------------------------------------------------------ batch

    def open_batch(self):
        path = filedialog.askopenfilename(parent=self.root, title="Open a CSV of emails",
                                          filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        self.batch_path = Path(path)
        try:
            with self.batch_path.open(newline="", encoding="utf-8-sig") as f:
                local_rows = list(csv.DictReader(f))
        except (OSError, UnicodeDecodeError, csv.Error) as exc:
            messagebox.showerror("Could not read CSV", str(exc), parent=self.root)
            return
        self.batch_btn.configure(state="disabled")
        self.batch_summary.configure(text=f"Scoring {len(local_rows):,} rows from {self.batch_path.name}…")

        def ok(result):
            self.batch_btn.configure(state="normal")
            self.batch_rows = []
            for r in result.results:
                src = local_rows[r.row] if r.row < len(local_rows) else {}
                self.batch_rows.append({"row": r.row, "id": r.id or "", "subject": src.get("subject", "") or "",
                                        "body": src.get("body", "") or "", "prob": r.probability_phishing,
                                        "error": r.error or ""})
            self.export_btn.configure(state="normal")
            self._refresh_batch_verdicts()

        def err(exc):
            self.batch_btn.configure(state="normal")
            self.batch_summary.configure(text="Batch failed.")
            self._show_error(exc)

        thr = round(self.threshold.get(), 2)
        self.run_async(lambda: self.client.predict_batch(self.batch_path, thr), ok, err)

    def _refresh_batch_verdicts(self):
        if not self.batch_rows:
            return
        thr = round(self.threshold.get(), 2)
        self.tree.delete(*self.tree.get_children())
        n_phish = 0
        for i, r in enumerate(self.batch_rows):
            if r["prob"] is None:
                verdict, prob, tags = "—", "—", ()
            else:
                is_phish = r["prob"] >= thr
                n_phish += is_phish
                verdict, prob, tags = ("phishing" if is_phish else "legitimate"), f"{100 * r['prob']:.1f}%", \
                    (("phishing",) if is_phish else ())
            subject = r["subject"] if len(r["subject"]) <= 90 else r["subject"][:87] + "…"
            self.tree.insert("", "end", iid=str(i), values=(r["row"], r["id"], subject, prob, verdict, r["error"]),
                             tags=tags)
        scored = sum(r["prob"] is not None for r in self.batch_rows)
        self.batch_summary.configure(
            text=f"{self.batch_path.name}: {len(self.batch_rows):,} rows · {scored:,} scored · "
                 f"{n_phish:,} flagged as phishing at threshold {thr:.2f}")

    def _sort_tree(self, col: str):
        reverse = self._sort_state[col] = not self._sort_state.get(col, False)
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children()]

        def key(v):
            s = v[0].rstrip("%")
            try:
                return (0, float(s))
            except ValueError:
                return (1, s.lower())
        for idx, (_v, k) in enumerate(sorted(items, key=key, reverse=reverse)):
            self.tree.move(k, "", idx)

    def _open_batch_row(self, _event):
        sel = self.tree.selection()
        if not sel:
            return
        r = self.batch_rows[int(sel[0])]
        self._set_input(r["subject"], r["body"])
        self.tabs.select(self.single_tab)
        self.check()

    def export_batch(self):
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".csv",
                                            initialfile=f"{self.batch_path.stem}_results.csv",
                                            filetypes=[("CSV files", "*.csv")])
        if not path:
            return
        thr = round(self.threshold.get(), 2)
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["row", "id", "subject", "probability_phishing", "label", "threshold", "error"])
            for r in self.batch_rows:
                label = "" if r["prob"] is None else ("phishing" if r["prob"] >= thr else "legitimate")
                w.writerow([r["row"], r["id"], r["subject"], r["prob"] if r["prob"] is not None else "",
                            label, thr, r["error"]])
        self.batch_summary.configure(text=self.batch_summary.cget("text") + f"   ·   exported to {Path(path).name}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Phishing Email Checker (desktop client)")
    parser.add_argument("--api-url", help="API base URL (default: $PHISH_API_URL or http://127.0.0.1:8000)")
    args = parser.parse_args(argv)

    root = tk.Tk()
    root.title("Phishing Email Checker")
    root.minsize(1000, 620)
    root.geometry("1180x720")
    try:
        ttk.Style(root).theme_use("vista")      # native look on Windows
    except tk.TclError:
        pass
    App(root, ApiClient(args.api_url))
    root.mainloop()


if __name__ == "__main__":
    main()
