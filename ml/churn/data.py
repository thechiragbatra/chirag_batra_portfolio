"""The Telco churn dataset: download (pinned by hash), clean and encode it the way the
customer-churn-mlops notebooks do, so the exported model matches the project."""

from __future__ import annotations

import hashlib
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

DATA_URL = (
    "https://raw.githubusercontent.com/thechiragbatra/customer-churn-mlops/main/"
    "WA_Fn-UseC_-Telco-Customer-Churn.csv"
)
DATA_SHA256 = "88be4b93fbe0cc83421af1c503794c97c342eca914c1576db7c276e61d61358a"
DATA_PATH = Path(__file__).resolve().parent / "data" / "telco-churn.csv"

TARGET = "Churn"
NUMERIC = ("SeniorCitizen", "tenure", "MonthlyCharges", "TotalCharges")


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch_csv(path: Path = DATA_PATH, url: str = DATA_URL) -> Path:
    """Download the dataset once and refuse it if the bytes are not the pinned file."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=60) as response:  # fixed https URL
            path.write_bytes(response.read())
    digest = sha256_of(path)
    if digest != DATA_SHA256:
        raise ValueError(f"{path} has sha256 {digest}, expected {DATA_SHA256}")
    return path


def clean(raw: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    """Notebook cleaning: TotalCharges to numeric, drop the ~11 blank rows and the id.
    Returns the feature frame (original string categories) and the 0/1 target."""
    df = raw.copy()
    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce")
    df = df.dropna().drop(columns="customerID").reset_index(drop=True)
    y = (df.pop(TARGET) == "Yes").astype(int).to_numpy()
    return df, y


@dataclass(frozen=True)
class Encoding:
    """Column order and category codes. Codes are the sorted category index, which is
    exactly what the notebooks' per-column LabelEncoder produces."""

    columns: list[str]
    levels: dict[str, list[str]]

    def transform(self, df: pd.DataFrame) -> np.ndarray:
        out = np.empty((len(df), len(self.columns)), dtype=np.float64)
        for j, col in enumerate(self.columns):
            if col in self.levels:
                codes = {level: i for i, level in enumerate(self.levels[col])}
                mapped = df[col].map(codes)
                if mapped.isna().any():
                    raise ValueError(f"unknown category in {col}: {set(df[col]) - set(codes)}")
                out[:, j] = mapped.to_numpy(dtype=np.float64)
            else:
                out[:, j] = df[col].to_numpy(dtype=np.float64)
        return out


def fit_encoding(df: pd.DataFrame) -> Encoding:
    columns = list(df.columns)
    levels = {c: sorted(df[c].astype(str).unique()) for c in columns if c not in NUMERIC}
    return Encoding(columns=columns, levels=levels)


def load(path: Path | None = None) -> tuple[pd.DataFrame, np.ndarray]:
    return clean(pd.read_csv(path or fetch_csv()))
