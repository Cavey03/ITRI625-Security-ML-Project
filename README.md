# ITRI625: Phishing Email Classifier

This project classifies emails as **legitimate (0)** or **phishing (1)**. The main model is a
fine-tuned DistilBERT, compared against a TF-IDF + Logistic Regression baseline. A FastAPI
service serves the model, and a Tkinter desktop app calls that service.

> Status: in development. Each section below is filled in as its milestone lands.

## Repository layout

```
notebooks/itri625_phishing.ipynb   main notebook: data, training, evaluation (committed WITH outputs)
src/                               reusable Python: data prep, model, training, explanations
api/                               FastAPI service
app/                               Tkinter desktop client
models/                            trained weights (gitignored, see "Model weights")
data/raw, data/processed           dataset + saved splits (gitignored, see "Data")
figures/                           every plot, saved as PNG
results/                           training logs + metric tables (CSV)
samples/                           demo emails (legitimate + phishing)
docs/api_contract.md               API endpoints and JSON formats
docs/app_spec.md                   desktop app requirements
docs/handover/                     task briefs for teammates
tests/                             pytest tests
```

## Setup

You need Python 3.12 and git. An NVIDIA GPU is optional; training falls back to the CPU.

```bash
git clone https://github.com/Cavey03/ITRI625-Security-ML-Project.git
cd ITRI625-Security-ML-Project
py -3.12 -m venv .venv          # macOS/Linux: python3.12 -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m ipykernel install --user --name itri625 --display-name "ITRI625 (.venv)"
```

`requirements.txt` lists the direct dependencies. `requirements-lock.txt` pins every package
at the exact version that produced the committed results. Install from the lock file if you
need an exact reproduction.

To check that the GPU is visible:

```bash
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

## Data

This project uses the **Phishing Email Dataset** by Naser Abdullah Alam (Kaggle), the dataset linked in the
ITRI625 brief: <https://www.kaggle.com/datasets/naserabdullahalam/phishing-email-dataset>

The data is not committed to git. To recreate it:

```bash
python -m src.download_data     # downloads about 77 MB into data/raw/ (no Kaggle login needed for this public dataset)
python -m src.data              # cleans, deduplicates and splits into data/processed/{train,val,test}.parquet
```

The pipeline is deterministic (seed 42). `results/data_report.json` holds a fingerprint of each
split. If yours match, you have exactly the same data as the committed results.

| step | rows |
|---|---|
| raw (six source corpora) | 82,486 |
| after removing junk and 8,237 exact or near duplicates | 74,237 |
| train / val / test (70/15/15, stratified on corpus × label) | 51,965 / 11,136 / 11,136 |

Each split has columns `id, subject, body, text, label, source`. `text` is the model input
(cleaned `subject + "\n\n" + body`), and `label` is 0 = legitimate, 1 = phishing/spam/fraud.
`source` is for analysis only and is never a model input. Section 2 of the notebook explains
every cleaning rule and the corpus-leakage checks.

## Model weights

The weights are not committed to git: the checkpoint is about 255 MB. Section 3 of the notebook
produces them:

```
models/distilbert_best/      model.safetensors, config.json, tokenizer files, train_config.json
results/distilbert_train_log.csv    one row per validation check (losses + metrics)
results/distilbert_run_info.json    best step, early-stopping outcome, training time, config
```

To recreate them, run the notebook with `RETRAIN = True`. On an RTX 5070 training takes about
4 minutes, because early stopping ends it after about 1.1 epochs. The full 3-epoch maximum
would take about 12 minutes. Set `SMALL_RUN = True` for a quick CPU check on a 2,000-email subset. With
`RETRAIN = False`, the notebook reuses an existing checkpoint and training log instead of
training again.

## Running the API and desktop app

The API's endpoints and JSON formats are defined in [docs/api_contract.md](docs/api_contract.md).
Until the real model is served, a **mock API** returns fake, keyword-based scores in the
same formats, so the desktop app can be built and tested:

```bash
uvicorn api.mock_app:app --port 8000
```

Then start the desktop app in a second terminal:

```bash
python -m app.main                       # or: python -m app.main --api-url http://host:port
```

The app has two tabs:
- **Single email:** paste an email or load a `.txt`/`.eml` file, then press **Check** (Ctrl+Enter).
  You get the verdict, the phishing probability, and the words that pushed the decision
  (red = towards phishing, blue = towards legitimate). The **threshold slider** re-labels
  the result instantly, without a new request.
- **Batch CSV:** open a CSV with a `body` column (optional `subject`, `id`), get a sortable
  table of results, and export it. Double-click a row to inspect it in the Single email tab.

If the API isn't running, the status line turns red and the app shows the reason. The app
never crashes because of it. The real API replaces the mock in Milestone 8.

## Tests

```bash
pytest
```

The contract tests in `tests/test_contract.py` check that each API implementation
follows `api/schemas.py`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the branch, pull request and commit rules.
