import numpy as np
import pandas as pd
import pytest

from data import DATA_SHA256, Encoding, clean, fetch_csv, fit_encoding


def raw_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "customerID": ["a", "b", "c"],
            "Contract": ["Two year", "Month-to-month", "One year"],
            "SeniorCitizen": [0, 1, 0],
            "tenure": [12, 1, 40],
            "MonthlyCharges": [20.5, 80.0, 55.25],
            "TotalCharges": ["246", " ", "2210"],
            "Churn": ["No", "Yes", "No"],
        }
    )


def test_clean_drops_blank_total_charges_and_id() -> None:
    df, y = clean(raw_frame())
    assert list(df.columns) == [
        "Contract",
        "SeniorCitizen",
        "tenure",
        "MonthlyCharges",
        "TotalCharges",
    ]
    assert len(df) == 2  # the row with a blank TotalCharges is gone
    assert df["TotalCharges"].tolist() == [246.0, 2210.0]
    assert y.tolist() == [0, 0]


def test_encoding_uses_sorted_label_codes_like_label_encoder() -> None:
    df, _ = clean(raw_frame())
    enc = fit_encoding(df)
    assert enc.levels == {"Contract": ["One year", "Two year"]}
    X = enc.transform(df)
    assert X[:, 0].tolist() == [1.0, 0.0]  # Two year -> 1, One year -> 0
    assert X[:, 2].tolist() == [12.0, 40.0]


def test_encoding_rejects_unknown_categories() -> None:
    enc = Encoding(columns=["Contract"], levels={"Contract": ["One year"]})
    with pytest.raises(ValueError, match="unknown category"):
        enc.transform(pd.DataFrame({"Contract": ["Lifetime"]}))


def test_fetch_refuses_a_file_with_the_wrong_hash(tmp_path) -> None:
    path = tmp_path / "data.csv"
    path.write_text("not the dataset")
    with pytest.raises(ValueError, match="expected"):
        fetch_csv(path, url="https://invalid.example")
    assert len(DATA_SHA256) == 64


def test_numeric_columns_stay_numeric() -> None:
    df, _ = clean(raw_frame())
    X = fit_encoding(df).transform(df)
    assert X.dtype == np.float64
