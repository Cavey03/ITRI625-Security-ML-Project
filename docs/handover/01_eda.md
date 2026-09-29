# Handover: Exploratory Data Analysis (EDA)

**Owner:** teammate · **Branch:** `feat/eda` · **Marks:** supports "Dataset preparation" and the theory write-up
**Depends on:** being able to download the dataset. You don't need to wait for the cleaned splits.

## Why this matters

The EDA isn't just a set of pretty charts. Its main job is to find out **whether the
dataset has shortcuts**: things that give away the label without having anything to do
with phishing. A model that learns a shortcut gets 99% in the notebook and fails on real
email. Your findings feed directly into how Kyle cleans the data in Milestone 4.

## Getting the data

Dataset: <https://www.kaggle.com/datasets/naserabdullahalam/phishing-email-dataset>

```python
import kagglehub
path = kagglehub.dataset_download("naserabdullahalam/phishing-email-dataset")
```

If this asks for credentials, create a Kaggle API token and put it in
`~/.kaggle/kaggle.json`. **Never commit that file.** Copy the CSVs into `data/raw/`,
which git ignores.

The dataset is built from several older email collections. We expect files roughly like
`CEAS_08.csv`, `Enron.csv`, `Ling.csv`, `Nazario.csv`, `Nigerian_Fraud.csv`,
`SpamAssasin.csv`, plus a combined `phishing_email.csv`. **Check this; don't assume it.**
Recording what each file actually contains is your first deliverable.

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

1. **File inventory table.** For each CSV: number of rows, column names, label values,
   phishing-to-legitimate count, and number of empty or missing bodies.
2. **Is the combined file just the others stacked together?** Check whether
   `phishing_email.csv` is a concatenation of the individual files. Hash the text and
   count the overlap. This tells Kyle which file(s) to build from.
3. **Label by source (most important).** Make a crosstab of source file against label
   and draw a stacked bar chart. If a source is almost 100% one class (for example if
   Enron is all legitimate), the model can learn "looks like Enron = legitimate", which
   is **corpus leakage**. Write down every source where one class makes up more than 95%.
4. **Class balance** overall, as a bar chart with counts and percentages.
5. **Length:** characters and words per email, split by class. Use histograms or
   boxplots with a **log x-axis**, because email lengths are very skewed. Report the
   median and 95th percentile. Also estimate the share of emails longer than about 256
   DistilBERT tokens, using words × 1.3 as a rough estimate. That share is how much text
   our model will cut off.
6. **URLs:** count of URLs per email by class, the share of emails with at least one URL,
   and the top 20 URL domains by class.
7. **Common words by class:** top 25 words after removing stop words (use
   `sklearn.feature_extraction.text.ENGLISH_STOP_WORDS`), one horizontal bar chart per
   class.
8. **Shortcut hunt:** look for tokens that are nearly perfect predictors but aren't about
   phishing, such as leftover header lines (`Message-ID`, `X-Mailer`), mailing-list
   footers, collection-specific boilerplate or date formats. One quick method is to rank
   tokens by how much more often they appear in one class, keeping only tokens that
   occur at least 50 times. List anything suspicious.
9. **Duplicates:** count exact duplicate texts, both overall and duplicates that appear
   under **both** labels. Report the numbers only; Kyle removes them in Milestone 4.

## `docs/eda_findings.md` (about 1 page)

Write bullet points with numbers, for example (made-up numbers): "Source X contributes
N rows, 100% legitimate → source leakage risk". Finish with a section called **Recommendations for
cleaning**, listing what you think should be removed or checked.

## Acceptance criteria

- [ ] `notebooks/eda.ipynb` runs from top to bottom on a fresh kernel, and **all outputs
      are saved in the committed file**.
- [ ] Every figure has a title, axis labels and a legend where needed, and is saved to
      `figures/eda_*.png`.
- [ ] Items 1–9 above are all covered.
- [ ] `docs/eda_findings.md` exists and has the recommendations section.
- [ ] No data files committed (`git status` shows nothing under `data/`).
- [ ] Merged into `main` (see CONTRIBUTING.md).
