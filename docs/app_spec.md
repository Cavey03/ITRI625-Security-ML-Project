# Spec: Tkinter desktop app

**Owner:** Kyle · **Branch:** `feat/desktop-app` · **Marks:** part of "Desktop application" (15)
**Depends on:** nothing. Built against the mock API (Milestone 4b), then pointed at the real API in Milestone 9.
Demo sample emails and the user guide are the teammate's (see [handover brief 03](handover/03_samples_and_docs.md)).

## What to build

A desktop window where a user pastes or loads an email and sees whether it's phishing,
how confident the model is, and which words drove the decision. The app only talks to
the model through the HTTP API; it never loads the model itself.

## Inputs and outputs

- **Talks to:** the API described in [`docs/api_contract.md`](api_contract.md). Use `requests`.
- **API URL:** default `http://127.0.0.1:8000`. Let the user override it with an
  environment variable `PHISH_API_URL` or a field in the app.
- **Run the mock:** `uvicorn api.mock_app:app --port 8000`. Its scores are fake, but its
  response shapes match the real API exactly.

## Files

```
app/
  main.py         # entry point: python -m app.main
  api_client.py   # the ONLY file that uses requests; one function per endpoint
  eml_loader.py   # .txt / .eml -> (subject, body)
tests/test_eml_loader.py
```

Keep all HTTP calls inside `api_client.py`. That way the GUI code never deals with JSON or
connection errors directly, and the client can be tested without opening a window.

## Required features

1. **Input:** a single-line `Entry` for the subject and a multi-line `Text` (with a
   scrollbar) for the body.
2. **"Load .txt / .eml" button** (`filedialog`).
   - `.eml`: parse with the standard library, `email.message_from_binary_file(f, policy=email.policy.default)`.
     Subject comes from the header. For the body, use the `text/plain` part if there is
     one, otherwise the `text/html` part (the API strips HTML).
   - `.txt`: if the first line starts with `Subject:`, use it as the subject. Everything
     else is the body.
3. **"Check" button** calls `POST /explain`. It returns both the prediction and the
   word scores, so you only need one request.
4. **Verdict:** a large label showing `PHISHING` or `LEGITIMATE`, coloured red or green,
   with the probability as a percentage and a progress bar.
5. **Threshold slider** (`ttk.Scale`, 0.05–0.95, default 0.50). Moving it re-labels the
   last result **locally**, using `label = prob >= threshold`, with no new API call.
   Show the current value next to the slider.
6. **Word highlighting:** a read-only `Text` widget showing the `subject` and `body`
   **from the API response**, not the user's input (see the contract for why). For each
   item in `words`, add a tag on `[start, end)`:
   - `score > 0`: red background. `score < 0`: green background.
   - Use 3 intensity buckets by `|score|`: 0.15–0.4 light, 0.4–0.7 medium, >0.7 strong.
     Skip words with `|score| < 0.15`, or everything ends up coloured.
   - Offsets are per field. Put the subject and body in the widget separately and convert
     each `start`/`end` to a Tk index with `"1.0 + {n} chars"`, adding the field's
     starting offset.
   - Add a small legend: red = pushes towards phishing, green = pushes towards legitimate.
   - If `truncated` is true, show "Only the first part of this email was analysed".
7. **API down:**
   - At startup, call `GET /health` and show a status line (`● API connected` / `● API unreachable`).
   - Wrap every call in `try/except requests.exceptions.RequestException` with a timeout
     (3 s for health, 30 s for explain).
   - On failure, show a `messagebox` with the reason. The app must never crash or freeze.
   - Show the `detail` from 4xx/5xx responses to the user.
8. **Don't freeze the UI.** Run API calls in a `threading.Thread`, then pass the
   result back with `root.after(...)`. Tkinter widgets can only be touched from the main
   thread. Disable the Check button while a request is running.

**Optional (only if time allows):** a "Batch CSV" button that sends a file to `/predict_batch`
and shows the results in a `ttk.Treeview`.

## Acceptance criteria

- [ ] `python -m app.main` opens the window with the mock running.
- [ ] `.eml` (plain, HTML-only, multipart) and `.txt` files load correctly. Later, every file in `samples/` too.
- [ ] Moving the slider changes the verdict without sending a request (check the server log).
- [ ] Words are highlighted in the right places, including after HTML is stripped.
      Test with an email containing `<b>verify</b>`.
- [ ] Stop the API: the app shows an error message and stays usable. Restart the API:
      the next Check works.
- [ ] Empty subject and body shows the API's 422 `detail` or a local check, not a crash.
- [ ] `pytest tests/test_eml_loader.py` passes.
- [ ] Merged into `main` through a pull request. Put a screenshot in the pull request
      description (reusable in the write-up).

## Contract changes

If the app needs something the contract doesn't provide, change `api/schemas.py`,
`docs/api_contract.md` and the contract tests together, in one pull request.
