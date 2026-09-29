"""Corpus-leakage diagnostics.

If a simple model can tell WHICH corpus an email came from, and corpora differ in
their label mix, a classifier can score well by recognising the corpus instead of
phishing. These functions measure how identifiable the source is from text.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split


def source_identifiability(texts: pd.Series, sources: pd.Series, top_k: int = 12,
                           seed: int = 0) -> tuple[float, pd.DataFrame]:
    """Train TF-IDF + LR to predict the source corpus from text.

    Returns (macro F1 on a held-out 20%, table of the top_k most source-indicative
    tokens per corpus). Chance-level macro F1 for 6 imbalanced classes is ~0.17.
    """
    x_tr, x_te, y_tr, y_te = train_test_split(texts, sources, test_size=0.2,
                                              stratify=sources, random_state=seed)
    vec = TfidfVectorizer(min_df=3, max_features=100_000, sublinear_tf=True)
    clf = LogisticRegression(max_iter=2000, C=5)
    clf.fit(vec.fit_transform(x_tr), y_tr)
    f1 = f1_score(y_te, clf.predict(vec.transform(x_te)), average="macro")
    names = np.array(vec.get_feature_names_out())
    top = {c: names[np.argsort(clf.coef_[i])[::-1][:top_k]] for i, c in enumerate(clf.classes_)}
    return float(f1), pd.DataFrame(top).T.rename(columns=lambda i: f"#{i + 1}")
