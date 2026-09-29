# Handover: TF-IDF + Logistic Regression baseline

**Owner:** teammate · **Branch:** `feat/tfidf-baseline` · **Marks:** part of "Model development" (20)
**Depends on:** Milestone 4 (Kyle's saved splits). You can write and test the code on a small fake DataFrame before then.

## Why a baseline

DistilBERT has 66 million parameters. A simple bag-of-words model is fast, easy to
explain and often strong on email data. The comparison tells us, and the marker, whether
the transformer is actually worth its cost. If the baseline gets 99% too, that's worth
knowing. It may also mean the data is too easy or has shortcuts (see the EDA brief).

## Inputs (produced by Kyle in Milestone 4, now available)

Recreate them with `python -m src.download_data` then `python -m src.data`. Check that the
`split_fingerprints` in `results/data_report.json` match the committed file.

```
data/processed/train.parquet   ~70%
data/processed/val.parquet     ~15%
data/processed/test.parquet    ~15%
```

| column | type | meaning |
|---|---|---|
| `id` | str | stable email id, unique across all splits |
| `subject`, `body` | str | cleaned subject and body (for inspection) |
| `text` | str | **model input**: cleaned `subject + "\n\n" + body` |
| `label` | int | 0 = legitimate, 1 = phishing |
| `source` | str | which original collection the email came from (for analysis only; **never a feature**) |

Load with `pd.read_parquet(...)`. Use **only** the `text` column as input. That way both
models see identical text, and the comparison is fair.

## Files

```
src/baseline.py
tests/test_baseline.py
```

`src/baseline.py` must provide:

```python
def build_pipeline(C: float = 1.0) -> sklearn.pipeline.Pipeline: ...
def tune_and_fit(train_df, val_df, C_grid=(0.01, 0.1, 1, 10, 100)) -> tuple[Pipeline, pd.DataFrame]:
    """Fit one model per C on train, score each on val, refit the best C on train.
    Returns the fitted best pipeline and a table of C vs val metrics."""
def predict_proba(pipe, texts: list[str]) -> np.ndarray:   # P(phishing), shape (n,)
def main(): ...   # run everything and write the outputs below
if __name__ == "__main__": main()
```

Recommended settings, as a starting point:

- `TfidfVectorizer(lowercase=True, ngram_range=(1, 2), min_df=2, max_df=0.95, max_features=200_000, sublinear_tf=True)`
- `LogisticRegression(C=..., max_iter=2000, solver="liblinear", class_weight="balanced")`
- Choose `C` by **validation F1**. **Never look at the test set while tuning.** Only
  score it once, at the end, with the chosen model.
- Fix `random_state=42` wherever it's accepted.

## Outputs (`python -m src.baseline` must write all of these)

| file | contents |
|---|---|
| `models/baseline_tfidf_lr.joblib` | fitted pipeline (git ignores it) |
| `results/baseline_val_tuning.csv` | one row per C: accuracy, precision, recall, F1, ROC AUC on val |
| `results/baseline_test_metrics.csv` | one row: the same metrics on **test**, plus the chosen C |
| `results/baseline_test_predictions.csv` | columns `id, label, prob_phishing`, one row per test email |
| `results/baseline_top_features.csv` | top 30 phishing-leaning and top 30 legitimate-leaning n-grams, with their coefficients |

Kyle draws the ROC, precision-recall and confusion-matrix plots for **both** models in
Milestone 7 from the predictions files, so both models get identical plots. You don't
need to make those plots.

The top-features file is a cheap, faithful explanation of what the baseline uses. It's
also a quick shortcut check: if the top features include things like corpus names or
header fragments, report it.

## Tests (`tests/test_baseline.py`)

- On a tiny made-up DataFrame (about 20 rows), `tune_and_fit` runs and `predict_proba`
  returns values in [0, 1] with the right shape.
- The pipeline makes no use of the `source` column. Check this by dropping the column
  and confirming it still runs.

## Acceptance criteria

- [ ] `python -m src.baseline` runs from a fresh clone (after the splits exist) in a few
      minutes on a CPU.
- [ ] All five output files are created. Test metrics are computed once, with the C chosen on val.
- [ ] `pytest tests/test_baseline.py` passes.
- [ ] No test-set information is used in tuning (a reviewer should be able to see this in the code).
- [ ] Merged into `main` through a pull request. Post the test metrics in the pull request description.
