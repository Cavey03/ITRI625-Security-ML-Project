# Phishing classifier API (CPU).
#
# Build:  docker build -t phishing-api .
# Run:    docker run --rm -p 8000:8000 -v "$(pwd)/models/distilbert_best:/models/distilbert_best:ro" phishing-api
#         (Windows PowerShell: -v "${PWD}/models/distilbert_best:/models/distilbert_best:ro")
# Check:  curl http://localhost:8000/health
#
# The trained weights are mounted at run time rather than copied into the image:
# they are not in git, the image stays small, and a new checkpoint needs no rebuild.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PHISH_MODEL_DIR=/models/distilbert_best \
    PHISH_DEVICE=cpu \
    HF_HUB_OFFLINE=1

WORKDIR /app

# Dependencies first, so code changes don't invalidate this (slow) layer
COPY requirements-api.txt .
RUN pip install -r requirements-api.txt

COPY api/ api/
COPY src/__init__.py src/preprocess.py src/

# Run as a non-root user
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
    CMD python -c "import urllib.request,json,sys; sys.exit(0 if json.load(urllib.request.urlopen('http://localhost:8000/health'))['model_loaded'] else 1)"

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
