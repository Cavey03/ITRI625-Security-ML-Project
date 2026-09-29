"""Download the phishing email dataset from Kaggle into data/raw/.

Usage:  python -m src.download_data

Uses kagglehub, which caches the download under ~/.cache/kagglehub. If Kaggle
asks for credentials, create an API token at kaggle.com -> Settings -> API and
save it as ~/.kaggle/kaggle.json (never commit it).
"""
from __future__ import annotations

import shutil
from pathlib import Path

import kagglehub

DATASET = "naserabdullahalam/phishing-email-dataset"
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def download(raw_dir: Path = RAW_DIR) -> list[Path]:
    cache = Path(kagglehub.dataset_download(DATASET))
    raw_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for src in sorted(cache.rglob("*.csv")):
        dst = raw_dir / src.name
        if not dst.exists() or dst.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dst)
        copied.append(dst)
    return copied


if __name__ == "__main__":
    for p in download():
        print(f"{p.stat().st_size / 1e6:8.1f} MB  {p.relative_to(RAW_DIR.parents[1])}")
