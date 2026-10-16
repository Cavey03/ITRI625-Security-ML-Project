"""Helpers shared by the real API (api/main.py) and the mock (api/mock_app.py),
so the two can never disagree about CSV handling or response shape."""
from __future__ import annotations

import csv
import io

from fastapi import HTTPException, UploadFile

from api.schemas import MAX_BATCH_BYTES, MAX_BATCH_ROWS, MAX_CHARS

# The csv module rejects fields over 131,072 characters by default, which made one long
# email fail the whole upload. Allow anything up to the file-size cap; over-long emails
# are then reported per row by row_problem().
csv.field_size_limit(MAX_BATCH_BYTES)


def prediction(prob: float, threshold: float, model_version: str) -> dict:
    label_id = int(prob >= threshold)
    return {"label": ("legitimate", "phishing")[label_id], "label_id": label_id,
            "probability_phishing": round(float(prob), 6), "threshold": threshold,
            "model_version": model_version}


def row_problem(subject: str, body: str) -> str | None:
    """Why a batch row can't be scored (same rules as a single /predict request), or None."""
    if not (subject.strip() or body.strip()):
        return "empty subject and body"
    if len(subject) > MAX_CHARS or len(body) > MAX_CHARS:
        return f"subject or body longer than {MAX_CHARS:,} characters"
    return None


async def read_batch_csv(file: UploadFile) -> list[dict]:
    """Parse an uploaded CSV into rows. Raises 413 (too big) or 400 (unreadable / no body column)."""
    raw = await file.read(MAX_BATCH_BYTES + 1)
    if len(raw) > MAX_BATCH_BYTES:
        raise HTTPException(413, f"file larger than {MAX_BATCH_BYTES} bytes")
    try:
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise HTTPException(400, f"could not parse CSV: {exc}") from exc
    if rows and "body" not in rows[0]:
        raise HTTPException(400, "CSV must have a 'body' column (and optionally 'subject', 'id')")
    if len(rows) > MAX_BATCH_ROWS:
        raise HTTPException(413, f"more than {MAX_BATCH_ROWS} rows")
    return rows
