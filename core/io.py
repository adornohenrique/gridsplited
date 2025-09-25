# core/io.py
import pandas as pd
import numpy as np

REQUIRED_COLS = {"timestamp", "price"}

def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {}
    for c in df.columns:
        lc = str(c).strip().lower()
        if lc in {"timestamp", "time", "datetime", "data", "date"}:
            rename_map[c] = "timestamp"
        elif lc in {"price", "preco", "€/mwh", "eur/mwh", "euro/mwh", "value", "spot"}:
            rename_map[c] = "price"
    if rename_map:
        df = df.rename(columns=rename_map)
    return df

def load_prices(file) -> pd.DataFrame:
    name = getattr(file, "name", None)
    if name and name.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(file)
    else:
        df = pd.read_csv(file)
    df = _normalize_columns(df)
    missing = REQUIRED_COLS - set(map(str.lower, df.columns))
    if missing:
        raise ValueError(f"Missing columns: {missing}")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    if df["timestamp"].isna().any():
        raise ValueError("Some timestamps could not be parsed.")
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df = df.dropna(subset=["price"])
    df = df.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last").reset_index(drop=True)
    return df

def ensure_quarter_hour(df: pd.DataFrame, method: str = "pad") -> pd.DataFrame:
    df = df.copy().set_index("timestamp")
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    start = df.index.min().ceil("15min")
    end = df.index.max().floor("15min")
    idx = pd.date_range(start, end, freq="15min", tz=df.index.tz)
    df = df.reindex(idx)
    if method == "linear":
        df["price"] = df["price"].interpolate(method="time", limit_direction="both")
    else:
        df["price"] = df["price"].ffill().bfill()
    return df.reset_index(names="timestamp")

def sanity_checks(df: pd.DataFrame, price_max_reasonable: float = 1000) -> dict:
    issues = {}
    diffs = df["timestamp"].diff().dropna()
    off = diffs[~diffs.eq(pd.Timedelta(minutes=15))]
    if len(off) > 0:
        issues["irregular_cadence"] = int(len(off))
    if (df["price"] < -2000).any() or (df["price"] > price_max_reasonable).any():
        issues["price_outliers"] = int(((df["price"] < -2000) | (df["price"] > price_max_reasonable)).sum())
    return issues
