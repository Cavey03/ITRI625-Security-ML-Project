"""API contract: request/response models shared by the real API and the mock.

This file IS the contract. docs/api_contract.md describes it in prose; if the two
ever disagree, this file wins. Changing a field here is a breaking change for the
desktop app, so do it in a PR that both team members review.

Label convention everywhere in the project: 0 = legitimate, 1 = phishing.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

API_VERSION = "1.0"

# Limits (enforced by both the real API and the mock)
MAX_CHARS = 100_000        # per field; longer input is rejected with 422
MAX_BATCH_ROWS = 1_000     # /predict_batch
MAX_BATCH_BYTES = 5 * 1024 * 1024

Label = Literal["legitimate", "phishing"]


# ---------------------------------------------------------------- requests

class EmailIn(BaseModel):
    """One email. Either field may be empty, but not both."""

    subject: str = Field("", max_length=MAX_CHARS, examples=["Your account has been suspended"])
    body: str = Field(..., max_length=MAX_CHARS,
                      examples=["Dear customer, verify your details at http://secure-login.example.com"])
    threshold: float = Field(0.5, ge=0.0, le=1.0,
                             description="Decision threshold on probability_phishing. "
                                         "Only affects `label`; the probability is unchanged.")

    @model_validator(mode="after")
    def not_blank(self) -> "EmailIn":
        if not (self.subject.strip() or self.body.strip()):
            raise ValueError("subject and body are both empty")
        return self


class ExplainIn(EmailIn):
    method: Literal["integrated_gradients"] = "integrated_gradients"


# ---------------------------------------------------------------- responses

class Prediction(BaseModel):
    label: Label
    label_id: Literal[0, 1]
    probability_phishing: float = Field(..., ge=0.0, le=1.0)
    threshold: float
    model_version: str


class HealthOut(BaseModel):
    status: Literal["ok", "loading", "error"]
    model_loaded: bool
    model_version: str | None
    device: str | None
    api_version: str = API_VERSION


class BatchRow(BaseModel):
    row: int = Field(..., description="0-based row index in the uploaded CSV (header excluded)")
    id: str | None = Field(None, description="Copied from the CSV `id` column if present")
    label: Label | None
    label_id: Literal[0, 1] | None
    probability_phishing: float | None
    error: str | None = Field(None, description="Set when this row could not be scored")


class BatchOut(BaseModel):
    n_rows: int
    n_scored: int
    threshold: float
    model_version: str
    results: list[BatchRow]


class WordScore(BaseModel):
    """One word with its attribution. Offsets index into ExplainOut.subject / .body."""

    field: Literal["subject", "body"]
    start: int = Field(..., ge=0, description="Character offset, inclusive")
    end: int = Field(..., gt=0, description="Character offset, exclusive")
    word: str
    score: float = Field(..., ge=-1.0, le=1.0,
                         description="> 0 pushes towards phishing, < 0 towards legitimate. "
                                     "Normalised so the strongest word has |score| = 1.")


class ExplainOut(Prediction):
    method: str
    subject: str = Field(..., description="Cleaned subject exactly as the model saw it")
    body: str = Field(..., description="Cleaned body exactly as the model saw it")
    words: list[WordScore]
    truncated: bool = Field(..., description="True if the text exceeded the model's max length; "
                                             "words past the cut-off are not scored")
