# Start here: teammate guide

Welcome to the ITRI625 phishing email classifier project. This page takes you from zero to
your first merged task. Read it top to bottom once. It takes about 10 minutes, and the setup
takes about 30 (mostly downloads).

## The project in one paragraph

We classify emails as **legitimate (0)** or **phishing/spam (1)**. Kyle has built the data
pipeline, a fine-tuned **DistilBERT** model (test F1 0.989), its evaluation, and a **Tkinter
desktop app** that talks to the model through an HTTP API. Your part is three well-scoped
tasks: a **TF-IDF + Logistic Regression baseline** to compare against DistilBERT, an
**exploratory data analysis (EDA)**, and the **demo sample emails + user documentation**.
None of your tasks block Kyle, and none of Kyle's block you.

---

## Step 1: Get access (one time)

1. Send Kyle your **GitHub username**. He adds you as a collaborator.
2. Accept the invitation: GitHub emails you, or look at <https://github.com/notifications>.
3. Install, if you don't have them:
   * **Python 3.12**: <https://www.python.org/downloads/>. On Windows, tick "Add python.exe to PATH".
   * **Git**: <https://git-scm.com/downloads>. On Windows this includes **Git Bash**. Use Git Bash
     for all the commands below.
4. Tell git who you are, so your commits show your name. This matters: marks depend on the
   history showing both of us.
   ```bash
   git config --global user.name "Your Name"
   git config --global user.email "the-email-on-your-github-account@example.com"
   ```

## Step 2: Set up the project (one time)

```bash
git clone https://github.com/Cavey03/ITRI625-Security-ML-Project.git
cd ITRI625-Security-ML-Project
py -3.12 -m venv .venv                 # macOS/Linux: python3.12 -m venv .venv
source .venv/Scripts/activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt        # large download, mostly PyTorch
python -m ipykernel install --user --name itri625 --display-name "ITRI625 (.venv)"
```

* Activate the environment (`source .venv/Scripts/activate`) **every time** you open a new
  terminal. Your prompt then starts with `(.venv)`.
* No NVIDIA GPU? That's fine: none of your tasks need one. To skip the 3 GB CUDA download,
  delete the `--extra-index-url` line in `requirements.txt` **before** installing, then undo
  that edit afterwards (`git checkout requirements.txt`) so you don't commit it.
* In Jupyter or VS Code, pick the kernel **"ITRI625 (.venv)"**.

## Step 3: Get the data (one time, about 2 minutes)

```bash
python -m src.download_data     # downloads the Kaggle dataset into data/raw/ (no login needed)
python -m src.data              # cleans + deduplicates + splits into data/processed/
git diff results/data_report.json
```

The last command must print **nothing**. That proves your splits are identical to Kyle's
(same fingerprints). If it prints differences, stop and tell Kyle.

What you now have:

| path | contents |
|---|---|
| `data/raw/*.csv` | the six source corpora + a pre-merged file, as downloaded |
| `data/processed/train.parquet` | 51,965 cleaned emails, **use this for training and analysis** |
| `data/processed/val.parquet` | 11,136 emails, for tuning (for example the baseline's C) |
| `data/processed/test.parquet` | 11,136 emails, **only for the final score, never for decisions** |

Columns: `id, subject, body, text, label, source`. Use `text` as the model input.
`source` is for analysis only, never a feature. `label`: 0 = legitimate, 1 = phishing/spam.

**Before starting, read sections 2 and 4 of `notebooks/itri625_phishing.ipynb`** (it opens
with outputs already shown on GitHub). They explain the data, the cleaning, and the
DistilBERT results you'll be comparing against.

## Step 4: How we use git (every task)

```bash
git switch main
git pull                                   # always start from the latest main
git switch -c feat/tfidf-baseline          # one branch per task (names are in each brief)

# ... work, then commit small steps with clear messages:
git add src/baseline.py
git commit -m "baseline: add TF-IDF + logistic regression pipeline"

# when the task is done and its checklist is ticked:
git switch main
git pull
git merge --no-ff feat/tfidf-baseline     # --no-ff keeps your branch visible in the history
git push
git branch -d feat/tfidf-baseline
```

Rules (details in [CONTRIBUTING.md](../../CONTRIBUTING.md)):

* **Never edit `notebooks/itri625_phishing.ipynb`.** It's Kyle's, and notebooks merge badly.
  Put code in `src/` or in your own notebook (`notebooks/eda.ipynb`).
* **Never commit** `data/`, `models/`, `.venv/` or `kaggle.json`. `.gitignore` handles this,
  but check `git status` before every commit.
* **Commit notebooks with their outputs visible.** Run all cells, save, then commit.
* Commit messages: `<area>: <what, in the imperative>`, for example `eda: add URL domain analysis`.
* Small commits, several per task. The marker reads the history.

---

## Step 5: Your tasks, in this order

### Task 1: TF-IDF baseline (top priority, about 3–5 hours)

**Brief:** [02_tfidf_baseline.md](02_tfidf_baseline.md) · **Branch:** `feat/tfidf-baseline`

Build `src/baseline.py`, a TF-IDF + Logistic Regression model on `text`. Tune `C` on the
**validation** set and score the test set **once**. `python -m src.baseline` must write
five files, including **`results/baseline_test_predictions.csv`** (`id, label, prob_phishing`).

Why it's first: the main notebook already has a comparison section (4.7) that turns on as
soon as that CSV exists. It draws the baseline's ROC/PR curves and confusion matrix next
to DistilBERT's. Until then, that section just says "baseline predictions not available yet".

Done when the brief's checklist is ticked, `pytest tests/test_baseline.py` passes, and you've
merged and pushed. Put your test-set F1 and AUC in the merge commit message.

### Task 2: EDA (about 4–6 hours)

**Brief:** [01_eda.md](01_eda.md) · **Branch:** `feat/eda`

Functions in `src/eda.py`, called from your own `notebooks/eda.ipynb` (committed with outputs),
figures saved as `figures/eda_*.png`, and a one-page `docs/eda_findings.md`. Some analyses are
already in the main notebook, and the brief says which ones to cite instead of redoing.
The **shortcut hunt** (item 5) is the most valuable: it checks whether the data cleaning missed
anything that gives the answer away.

### Task 3: Demo samples + user documentation (about 4–6 hours)

**Brief:** [03_samples_and_docs.md](03_samples_and_docs.md) · **Branches:** `docs/samples`, then `docs/user-guide`

* **Part A:** at least 12 self-written demo emails in `samples/` (6 legitimate, 6 phishing,
  including the listed hard cases) + `samples/README.md`. **Write them yourself.** Never copy
  real emails or emails from the dataset.
* **Part B:** `docs/user_guide.md` with screenshots, `docs/demo_script.md` (a 5-minute demo),
  and the README's "Using the desktop app" and "Troubleshooting" sections.

To run the app for screenshots, use two terminals, both with the environment activated:

```bash
uvicorn api.mock_app:app --port 8000     # terminal 1: the mock API (fake scores for now)
python -m app.main                       # terminal 2: the desktop app
```

Screenshots taken against the mock show `model mock-0`. Once Kyle's real API exists, retake
them with the real model. Kyle will tell you when.

---

## Checking your work before you merge

```bash
pytest                    # all tests must pass, not just yours
git status                # nothing under data/ or models/, no stray files
```

Then tick the checklist at the bottom of your brief.

## When you're stuck

| problem | fix |
|---|---|
| `py` not found | use `python` instead, or reinstall Python and tick "Add to PATH" |
| `ModuleNotFoundError: No module named 'src'` | run commands from the repo root folder, with `.venv` activated |
| `pip install` is very slow | that's PyTorch (about 3 GB); see the no-GPU tip in step 2 |
| Kaggle download asks for credentials | kaggle.com → Settings → API → Create New Token, save as `~/.kaggle/kaggle.json` (never commit it) |
| `git push` rejected ("fetch first") | `git pull`, then push again. If there's a conflict, ask Kyle before resolving it |
| Jupyter can't find packages | select the "ITRI625 (.venv)" kernel (top right of the notebook) |
| a brief seems wrong or unclear | ask Kyle before working around it; the briefs are meant to be correct |

## Contact

Anything unclear, blocked for more than 30 minutes, or a finding that looks important (for
example the shortcut hunt finding a leak): message Kyle straight away.
