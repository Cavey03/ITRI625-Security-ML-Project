# ITRI625: who does what

Phishing email classifier: **0 = legitimate, 1 = phishing/spam**. DistilBERT model, FastAPI, Tkinter app.

## ✅ Done (Kyle)

| Area | What exists | Where |
|---|---|---|
| Repo + environment | Folder layout, `requirements.txt` + lock file, git workflow | `CONTRIBUTING.md` |
| API contract | Request/response schemas, mock API with fake scores, 9 contract tests | `api/schemas.py`, `api/mock_app.py`, `docs/api_contract.md` |
| Data | Download, cleaning, leakage removal, deduplication (8,237 removed), stratified 70/15/15 splits | `src/`, notebook §2, `data/processed/*.parquet` |
| Data analysis | Source inventory, class balance, label mix per source, duplicates, token lengths, corpus fingerprints | notebook §2, §3.3 |
| Desktop app | Single-email + batch CSV tabs, `.eml`/`.txt` loading, threshold slider, word highlighting, handles the API being down | `app/`, `docs/app_spec.md` |
| DistilBERT | Custom training loop, logging, early stopping (stopped at step 1800, best step 1200) | notebook §3 |
| Evaluation | Test set: **accuracy 0.989, F1 0.989, AUC 0.999**. Curves, ROC/PR, confusion matrices, per-source results, error analysis | notebook §4, `figures/`, `results/` |

## 🔲 Teammate: to implement

### Setup (once)

1. Send Kyle your GitHub username, then accept the invite. Set `git config --global user.name` and `user.email` (the email on your GitHub account).
2. In Git Bash:
   ```bash
   git clone https://github.com/Cavey03/ITRI625-Security-ML-Project.git && cd ITRI625-Security-ML-Project
   py -3.12 -m venv .venv && source .venv/Scripts/activate      # macOS/Linux: python3.12 / .venv/bin/activate
   pip install -r requirements.txt
   python -m src.download_data && python -m src.data
   git diff results/data_report.json                            # must print nothing (= same splits as Kyle)
   ```
3. Read notebook §2 and §4 on GitHub (outputs are visible) before starting.

### Tasks (in this order)

| # | Task | Branch | You deliver | Done when |
|---|---|---|---|---|
| **1** | **TF-IDF + Logistic Regression baseline** (top priority) | `feat/tfidf-baseline` | `src/baseline.py`, `tests/test_baseline.py`, and from `python -m src.baseline`: `results/baseline_test_predictions.csv` (`id,label,prob_phishing`), `baseline_test_metrics.csv`, `baseline_val_tuning.csv`, `baseline_top_features.csv`, `models/baseline_tfidf_lr.joblib` | tests pass; C chosen on **val** by F1; test scored **once**; merged |
| 2 | **EDA (what's not already in the notebook)** | `feat/eda` | `src/eda.py`, `notebooks/eda.ipynb` (with outputs), `figures/eda_*.png`, `docs/eda_findings.md` (1 page) | 4 analyses below done; findings written; merged |
| 3a | **Demo sample emails** | `docs/samples` | ≥ 6 legitimate + 6 phishing in `samples/legit/`, `samples/phishing/` (`.eml` + `.txt`), `samples/README.md` | hard cases covered; all load in the app; merged |
| 3b | **User guide + demo script** | `docs/user-guide` | `docs/user_guide.md` + screenshots in `docs/img/`, `docs/demo_script.md`, README sections "Using the desktop app" + "Troubleshooting" | a newcomer can run the app from the guide alone; merged |

**1. Baseline:** `TfidfVectorizer(ngram_range=(1,2), min_df=2, max_df=0.95, sublinear_tf=True)` + `LogisticRegression(class_weight="balanced", max_iter=2000)`. Input is the `text` column only (never `source`). Try `C` in {0.01, 0.1, 1, 10, 100} on val, refit the best, and score test once. Kyle's notebook §4.7 turns on automatically when the predictions CSV exists. Full spec: [02_tfidf_baseline.md](02_tfidf_baseline.md).

**2. EDA:** on `data/processed/train.parquet` only. Don't redo what the "Done" table lists.
1. **URLs:** URLs per email by class, % of emails with at least one URL, top 20 domains per class.
2. **Common words:** top 25 per class after stop words (`ENGLISH_STOP_WORDS`), one bar chart per class.
3. **Length per source:** characters and words by class and source (log axis, median, 95th percentile).
4. **Label shortcut hunt:** tokens (≥ 50 occurrences) that almost perfectly predict the label but aren't about phishing. List anything suspicious and tell Kyle immediately.

Full spec: [01_eda.md](01_eda.md).

**3a. Samples:** **write them yourself** (no real emails, nothing from the dataset). Use `example.com` domains and invented companies. Must include: a legitimate password reset, phishing with no link, a very short phishing email, a long legitimate HTML newsletter, obvious phishing, and a normal work email. Full spec: [03_samples_and_docs.md](03_samples_and_docs.md) part A.

**3b. Docs:** run the app with `uvicorn api.mock_app:app --port 8000` (terminal 1) and `python -m app.main` (terminal 2). Cover: how to start it, every part of the window, what the threshold means, how to read the red/blue highlighting, and what happens when the API is down. **Retake the screenshots once Kyle's real API is ready** (it currently shows `mock-0`). Full spec: part B of the same brief.

### Rules

* One branch per task → small commits (`area: what changed`) → `git switch main && git pull && git merge --no-ff <branch> && git push`.
* **Never edit `notebooks/itri625_phishing.ipynb`** (Kyle's). Never commit `data/`, `models/`, `.venv/`.
* Commit notebooks **with outputs**. Run `pytest` before merging. Never use the test split for decisions.
* Stuck for more than 30 minutes, or found something that looks like a leak? Message Kyle.

## ⏳ Remaining (Kyle)

| # | Task |
|---|---|
| 8 | Real FastAPI serving DistilBERT (`api/main.py`), passing the same contract tests as the mock |
| 9 | Point the desktop app at the real API, test end to end |
| 10 | Bonus: Integrated Gradients explanations (`/explain` + app highlights), robustness check, Dockerfile |
| 11 | Final clean notebook run including the baseline comparison, final README |
| — | Theory write-up (30 marks): split between Kyle and teammate, to be agreed |
