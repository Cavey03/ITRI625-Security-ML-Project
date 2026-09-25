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

It is not committed to git. The download and cleaning steps are added in Milestone 4.

## Model weights

These are not committed to git. Instructions are added in Milestone 6.

## Running the API and desktop app

The API's endpoints and JSON formats are defined in [docs/api_contract.md](docs/api_contract.md).
Until the real model is served, a **mock API** returns fake, keyword-based scores in the
same formats, so the desktop app can be built and tested:

```bash
uvicorn api.mock_app:app --port 8000
```

The real API and app instructions are added in Milestones 8 and 9.

## Tests

```bash
pytest
```

The contract tests in `tests/test_contract.py` check that each API implementation
follows `api/schemas.py`.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the branch, pull request and commit rules.
