# Handover: Exploratory Data Analysis (EDA)

**Owner:** teammate · **Branch:** `feat/eda` · **Marks:** supports "Dataset preparation" and the theory write-up
**Depends on:** nothing. The data and cleaned splits are available now.

## Why this matters

The EDA isn't just a set of pretty charts. Its main job is to find out **whether the
dataset has shortcuts**: things that give away the label without having anything to do
with phishing. A model that learns a shortcut gets 99% in the notebook and fails on real
email. Your findings feed directly into how Kyle cleans the data in Milestone 4.

## Getting the data

Follow `START_HERE.md` steps 2–3. You'll then have:

* `data/raw/*.csv`: the six source corpora plus the pre-merged file, exactly as downloaded
* `data/processed/{train,val,test}.parquet`: cleaned and deduplicated emails with columns
  `id, subject, body, text, label, source` (label 0 = legitimate, 1 = phishing/spam/fraud)

**Use `data/processed/train.parquet` for the analysis**, since that's what the models learn
from. Don't look at the test split: it's reserved for the final evaluation.

## Files

```
src/eda.py              # functions only (load, compute stats, make figures). No top-level code that runs on import.
notebooks/eda.ipynb     # calls src/eda.py and shows the outputs. You own this notebook.
figures/eda_*.png       # every figure saved with an eda_ prefix
results/eda_*.csv       # every table saved with an eda_ prefix
docs/eda_findings.md    # short written summary (see below)
```

Kyle copies the functions from `src/eda.py` into the main notebook. Keeping the logic in
`src/` means we never both edit the same `.ipynb`, which avoids merge conflicts.

## What to analyse

**Already done by Kyle in the main notebook, section 2. Don't redo these; just cite the
numbers in your findings:** the file inventory, the fact that `phishing_email.csv` is the
six files stacked, the label mix per source (Nazario and Nigerian_Fraud are 100% label 1)
and the duplicate counts. Read section 2 first. It explains the cleaning and what was removed.

Your analyses, on `train.parquet`:

1. **Class balance**, overall and per source, as a bar chart with counts and percentages.
2. **Length:** characters and words per email, split by class. Use histograms or
   boxplots with a **log x-axis**, because email lengths are very skewed. Report the
   median and 95th percentile per class. The notebook's section 3.3 already covers token
   counts. Yours is characters and words, and **per source**.
3. **URLs:** count of URLs per email by class, the share of emails with at least one URL,
   and the top 20 URL domains by class.
4. **Common words by class:** top 25 words after removing stop words (use
   `sklearn.feature_extraction.text.ENGLISH_STOP_WORDS`), one horizontal bar chart per
   class.
5. **Shortcut hunt on the *cleaned* text:** look for tokens that are nearly perfect predictors but aren't about
   phishing, such as leftover header lines (`Message-ID`, `X-Mailer`), mailing-list
   footers, collection-specific boilerplate or date formats. One quick method is to rank
   tokens by how much more often they appear in one class, keeping only tokens that
   occur at least 50 times. List anything suspicious. This checks whether the cleaning
   missed anything, which is useful whatever you find.

## `docs/eda_findings.md` (about 1 page)

Write bullet points with numbers, for example (made-up numbers): "Source X contributes
N rows, 100% legitimate → source leakage risk". Finish with a section called **Recommendations for
cleaning**, listing what you think should be removed or checked.

## Acceptance criteria

- [ ] `notebooks/eda.ipynb` runs from top to bottom on a fresh kernel, and **all outputs
      are saved in the committed file**.
- [ ] Every figure has a title, axis labels and a legend where needed, and is saved to
      `figures/eda_*.png`.
- [ ] Items 1–5 above are all covered.
- [ ] `docs/eda_findings.md` exists and has the recommendations section.
- [ ] No data files committed (`git status` shows nothing under `data/`).
- [ ] Merged into `main` (see CONTRIBUTING.md).
