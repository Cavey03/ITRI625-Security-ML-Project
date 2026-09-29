"""HTTP client for the phishing API. The ONLY module in the app that uses requests.

Every failure (server down, timeout, HTTP error, response not matching the
contract) is turned into ApiError with a message that can be shown to the user.
Responses are validated against api/schemas.py, so a contract mismatch is caught
here instead of surfacing as a confusing KeyError in the GUI.
"""
from __future__ import annotations

import os
from pathlib import Path

import requests
from pydantic import ValidationError

from api.schemas import BatchOut, ExplainOut, HealthOut

DEFAULT_URL = "http://127.0.0.1:8000"
HEALTH_TIMEOUT = 3
EXPLAIN_TIMEOUT = 60      # the first request to the real model on CPU can be slow
BATCH_TIMEOUT = 300


class ApiError(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _detail(resp: requests.Response) -> str:
    try:
        detail = resp.json().get("detail", resp.text)
    except ValueError:
        return resp.text[:300] or resp.reason
    if isinstance(detail, list):   # FastAPI validation errors: [{"loc": [...], "msg": "..."}]
        return "; ".join(d.get("msg", str(d)).removeprefix("Value error, ") for d in detail)
    return str(detail)


class ApiClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or os.environ.get("PHISH_API_URL") or DEFAULT_URL).rstrip("/")
        self.session = requests.Session()

    def _request(self, method: str, path: str, timeout: float, **kwargs) -> dict:
        url = f"{self.base_url}{path}"
        try:
            resp = self.session.request(method, url, timeout=timeout, **kwargs)
        except requests.ConnectionError:
            raise ApiError(f"Cannot reach the API at {self.base_url}.\n"
                           "Is the server running? Start it with:\n"
                           "uvicorn api.mock_app:app --port 8000") from None
        except requests.Timeout:
            raise ApiError(f"The API did not answer within {timeout} s.") from None
        except requests.RequestException as exc:
            raise ApiError(f"Request failed: {exc}") from None
        if not resp.ok:
            raise ApiError(f"API error {resp.status_code}: {_detail(resp)}", status=resp.status_code)
        try:
            return resp.json()
        except ValueError:
            raise ApiError("The API returned something that is not JSON.") from None

    def health(self) -> HealthOut:
        return self._validate(HealthOut, self._request("GET", "/health", HEALTH_TIMEOUT))

    def explain(self, subject: str, body: str, threshold: float = 0.5) -> ExplainOut:
        payload = {"subject": subject, "body": body, "threshold": threshold}
        return self._validate(ExplainOut, self._request("POST", "/explain", EXPLAIN_TIMEOUT, json=payload))

    def predict_batch(self, csv_path: str | Path, threshold: float = 0.5) -> BatchOut:
        path = Path(csv_path)
        with path.open("rb") as f:
            data = self._request("POST", "/predict_batch", BATCH_TIMEOUT, params={"threshold": threshold},
                                 files={"file": (path.name, f, "text/csv")})
        return self._validate(BatchOut, data)

    @staticmethod
    def _validate(model, data: dict):
        try:
            return model.model_validate(data)
        except ValidationError as exc:
            raise ApiError(f"The API response does not match the contract:\n{exc}") from None
