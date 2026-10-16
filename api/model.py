"""Inference wrapper around the fine-tuned DistilBERT checkpoint.

The model is TRAINED in the notebook (section 3). This module only loads the saved
checkpoint and reproduces the notebook's input pipeline exactly:
  * cleaning: src.preprocess.clean_email (the same function the data pipeline used)
  * truncation: first max_len tokens, [CLS] ... [SEP], max_len from train_config.json
tests/test_api.py checks that the API's probabilities match the notebook's saved
test-set predictions.

Explanations use Integrated Gradients (Sundararajan et al., 2017) on the embedding
layer: attributions are integrated along a straight path from a baseline input
(all [PAD] between [CLS] and [SEP]) to the real input, for the phishing-vs-legitimate
log-odds. Token attributions are summed into words and mapped back to character
offsets in the cleaned subject/body, which is what the desktop app highlights.
"""
from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from captum.attr import LayerIntegratedGradients
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from transformers.utils import logging as hf_logging

from src.preprocess import build_text, clean_email

hf_logging.set_verbosity_error()
hf_logging.disable_progress_bar()

DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "distilbert_best"
_WORD = re.compile(r"\S+")


@dataclass
class Explanation:
    subject: str
    body: str
    probability: float
    words: list[dict]
    truncated: bool


class PhishingClassifier:
    def __init__(self, model_dir: str | Path = DEFAULT_MODEL_DIR, device: str | None = None):
        model_dir = Path(model_dir)
        cfg = json.loads((model_dir / "train_config.json").read_text())
        self.max_len = int(cfg["max_len"])
        self.version = f"distilbert-step{cfg.get('best_step', 'na')}"
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.tokenizer = AutoTokenizer.from_pretrained(model_dir)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_dir).to(self.device).eval()
        self._lock = threading.Lock()   # one request at a time on the model (single GPU / CPU)

    # ------------------------------------------------------------------ prediction

    def _encode(self, texts: list[str]) -> dict:
        return self.tokenizer(texts, truncation=True, max_length=self.max_len, padding=True,
                              return_tensors="pt").to(self.device)

    @torch.no_grad()
    def predict_texts(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        """P(phishing) for already-cleaned model texts."""
        out = []
        with self._lock:
            for i in range(0, len(texts), batch_size):
                logits = self.model(**self._encode(texts[i:i + batch_size])).logits.float()
                out.append(torch.softmax(logits, dim=-1)[:, 1].cpu())
        return torch.cat(out).numpy() if out else np.zeros(0)

    def predict(self, subject: str, body: str) -> float:
        return float(self.predict_texts([clean_email(subject, body)[2]])[0])

    # ------------------------------------------------------------------ explanation

    def _log_odds(self, input_ids, attention_mask):
        logits = self.model(input_ids=input_ids, attention_mask=attention_mask).logits
        return logits[:, 1] - logits[:, 0]          # > 0 means phishing

    def explain(self, subject: str, body: str, n_steps: int = 50) -> Explanation:
        subject, body, text = clean_email(subject, body)
        enc = self.tokenizer(text, truncation=True, max_length=self.max_len, return_offsets_mapping=True,
                             return_tensors="pt")
        truncated = len(self.tokenizer(text, truncation=False, verbose=False)["input_ids"]) > self.max_len
        offsets = enc.pop("offset_mapping")[0].tolist()
        input_ids, mask = enc["input_ids"].to(self.device), enc["attention_mask"].to(self.device)

        baseline = torch.full_like(input_ids, self.tokenizer.pad_token_id)
        baseline[0, 0], baseline[0, -1] = self.tokenizer.cls_token_id, self.tokenizer.sep_token_id
        lig = LayerIntegratedGradients(self._log_odds, self.model.distilbert.embeddings)
        with self._lock:
            with torch.no_grad():
                prob = float(torch.softmax(self.model(input_ids=input_ids, attention_mask=mask).logits.float(), -1)[0, 1])
            attr = lig.attribute(input_ids, baselines=baseline, additional_forward_args=(mask,),
                                 n_steps=n_steps, internal_batch_size=min(n_steps, 25))
        token_scores = attr.sum(dim=-1)[0].detach().float().cpu().numpy()   # one number per token

        words = self._words(subject, body, offsets, token_scores)
        peak = max((abs(w["score"]) for w in words), default=0.0)
        for w in words:
            w["score"] = round(w["score"] / peak, 4) if peak > 0 else 0.0
        return Explanation(subject, body, prob, words, truncated)

    @staticmethod
    def _words(subject: str, body: str, offsets: list, token_scores: np.ndarray) -> list[dict]:
        """Sum token attributions into whitespace-separated words of each field."""
        body_start = len(subject) + 2 if subject else 0      # build_text: subject + "\n\n" + body
        spans = [("subject", 0, m) for m in _WORD.finditer(subject)] + \
                [("body", body_start, m) for m in _WORD.finditer(body)]
        starts = np.array([base + m.start() for _, base, m in spans])
        totals, seen = np.zeros(len(spans)), np.zeros(len(spans), dtype=bool)
        for (a, b), s in zip(offsets, token_scores):
            if b <= a or len(spans) == 0:                    # special tokens have (0, 0)
                continue
            k = int(np.searchsorted(starts, a, side="right") - 1)   # word whose span starts at or before a
            if k >= 0:
                totals[k] += s
                seen[k] = True
        return [{"field": f, "start": m.start(), "end": m.end(), "word": m.group(), "score": float(totals[k])}
                for k, (f, _base, m) in enumerate(spans) if seen[k]]


assert build_text("s", "b") == "s\n\nb"   # _words relies on this layout
