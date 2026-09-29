# Handover: demo sample emails + user documentation

**Owner:** teammate · **Branches:** `docs/samples`, then `docs/user-guide` · **Marks:** supports "Desktop application" (15) and the demo
**Depends on:** part A needs nothing, so start now. Part B needs Kyle's desktop app (built against the mock API, so it exists before the real model).

Do this as two separate pull requests. Part A can merge long before part B.

---

## Part A: sample emails (`samples/`)

These are the emails we'll load into the desktop app during the demo, so they need to
show the model working, and also its limits.

**Files**

```
samples/
  legit/      *.eml and *.txt
  phishing/   *.eml and *.txt
  README.md
```

**Rules**

- At least **6 legitimate + 6 phishing**, with a mix of `.eml` and `.txt`.
- **Write them yourself.** Don't copy real emails from your inbox or from the dataset. Real
  emails contain real people's data, and dataset emails might be in our test set, which
  would make the demo look better than the model really is.
- Use only `example.com`, `example.org` or `example.net` domains, and made-up names.
  Don't imitate a real bank or company by name or logo. Use invented ones like "Northwind Bank".
- `.txt` format: first line `Subject: ...`, then a blank line, then the body.
- `.eml` format: a minimal valid email (see the template below). At least 2 should be
  HTML (`Content-Type: text/html`) to show that the app strips HTML.

**Include these hard cases** (label them in the README):

| case | why it's interesting |
|---|---|
| legitimate password-reset email | looks phishy (urgent, has a link) but isn't |
| phishing with **no link** (for example "reply with your details" or gift-card fraud) | the model can't rely on URLs |
| very short phishing email (1–2 lines) | little text to go on |
| long legitimate HTML newsletter | many links, long text (tests truncation) |
| obvious phishing with typos and a fake login link | the easy case, showing the model works |
| legitimate internal work email | the easy legitimate case |

**`.eml` template**

```
From: Northwind Bank <alerts@northwind-bank.example.com>
To: you@example.org
Subject: Unusual sign-in activity
MIME-Version: 1.0
Content-Type: text/plain; charset="utf-8"

Dear customer, ...
```

**`samples/README.md`:** a table with columns file, true label, hard case? (yes/no),
and what it shows. After Milestone 8, add a column with the real model's probability,
so we can talk honestly about any it gets wrong.

**Acceptance criteria (A)**

- [ ] At least 12 files, and every hard case above is covered.
- [ ] Every file opens without errors using Python's email parser:
      `python -c "import email,email.policy,sys; email.message_from_binary_file(open(sys.argv[1],'rb'),policy=email.policy.default)" samples/phishing/x.eml`
- [ ] No real company names, real people or real domains.
- [ ] Merged into `main` through a pull request.

---

## Part B: user guide + README usage sections

Start this once Kyle's desktop app is merged. Run it against the mock
(`uvicorn api.mock_app:app --port 8000`) and later the real API.

**Files**

```
docs/user_guide.md     how to use the desktop app, with screenshots
docs/demo_script.md    step-by-step script for the live demo, about 5 minutes
docs/img/*.png         screenshots used in the guide
README.md              only the "Using the desktop app" and "Troubleshooting" sections
```

**`docs/user_guide.md` should cover:**

1. Starting the API, then the app (exact commands).
2. Each part of the window, with a labelled screenshot: subject and body inputs, the
   Load button, the Check button, the verdict and probability, the threshold slider, the
   highlighted explanation, and the connection status.
3. **What the threshold means**, in plain language. Lower = catches more phishing but
   flags more legitimate mail; higher = the opposite. Include one screenshot of the same
   email at two thresholds.
4. **How to read the highlighting.** Red = pushes towards phishing, green = pushes towards
   legitimate. It shows what the model reacted to, not proof the email is safe. Mention
   the "only the first part was analysed" note.
5. What the app does when the API is down, with a screenshot of the error.

**`docs/demo_script.md`:** the order of what to click and say. Use 3–4 samples from part A,
including at least one hard case the model gets wrong or is unsure about. Showing the
limits is worth marks in the theory analysis.

**README sections:** keep them short and link to the user guide for detail.
Troubleshooting should cover at least: "API unreachable", port 8000 already in use, and
`.eml` file won't load.

**Acceptance criteria (B)**

- [ ] Someone who has never seen the project can start the API and app, and check a
      sample email, using only the user guide.
- [ ] Every screenshot is current (matches the latest app) and saved in `docs/img/`.
- [ ] Merged into `main` through a pull request.
