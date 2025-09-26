# core/io.py
import pandas as pd
import numpy as np

# ---- Helpers ---------------------------------------------------------------

def _drop_all_empty_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(axis=1, how="all")
    df.columns = [str(c).strip() for c in df.columns]
    # ensure unique column names
    if len(set(df.columns)) != len(df.columns):
        seen = {}
        newcols = []
        for c in df.columns:
            n = seen.get(c, 0)
            newcols.append(c if n == 0 else f"{c}_{n}")
            seen[c] = n + 1
        df.columns = newcols
    return df

def _best_datetime_col(df: pd.DataFrame) -> str | None:
    best, best_score = None, 0.0
    for c in df.columns:
        s = pd.to_datetime(df[c], errors="coerce", utc=True)
        score = float(s.notna().mean())
        if score > best_score and score > 0.5:
            best, best_score = c, score
    return best

def _best_numeric_col(df: pd.DataFrame, exclude: str | None = None) -> str | None:
    best, best_score = None, 0.0
    for c in df.columns:
        if exclude and c == exclude:
            continue
        s = pd.to_numeric(df[c], errors="coerce")
        score = float(s.notna().mean())
        if score > best_score and score > 0.5:
            best, best_score = c, score
    return best

# ---- Public API ------------------------------------------------------------

def load_prices(file_or_path) -> pd.DataFrame:
    """
    Robust loader for CSV/XLSX price files:
    - Drops empty 'Unnamed' columns
    - Auto-detects best datetime and price-like numeric columns
    - Works with ERCOT headers (e.g., 'UTC Timestamp (Interval Ending)', '*LMP')
    """
    name = getattr(file_or_path, "name", None) or str(file_or_path)
    if str(name).lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(file_or_path)
    else:
        df = pd.read_csv(file_or_path)

    df = _drop_all_empty_columns(df)

    # Name-based hints
    lc = {c: str(c).strip().lower() for c in df.columns}
    ts_aliases = ["timestamp", "time", "datetime", "date", "utc timestamp",
                  "interval", "settlementdate", "delivery", "hour", "he"]
    price_aliases = ["price", "lmp", "settlement point price", "spot", "value", "rtm", "dam", "eur/mwh", "€/mwh"]

    ts_col = None
    for alias in ts_aliases:
        for c, l in lc.items():
            if alias == l or alias in l:
                ts_col = c; break
        if ts_col: break

    price_col = None
    for alias in price_aliases:
        for c, l in lc.items():
            if alias == l or alias in l:
                price_col = c; break
        if price_col: break

    # Heuristics if needed
    if ts_col is None:
        ts_col = _best_datetime_col(df)
    if price_col is None:
        price_col = _best_numeric_col(df, exclude=ts_col)

    # Last-resort fallback
    if (ts_col is None or price_col is None) and df.shape[1] >= 2:
        ts_col = ts_col or df.columns[0]
        price_col = price_col or df.columns[1]

    if ts_col is None or price_col is None:
        raise ValueError(f"Could not infer timestamp/price columns. Columns: {df.columns.tolist()}")

    out = df[[ts_col, price_col]].copy()
    out.columns = ["timestamp", "price"]
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce", utc=True)
    out["price"] = pd.to_numeric(out["price"], errors="coerce")
    out = out.dropna(subset=["timestamp", "price"])
    out = out.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last").reset_index(drop=True)
    return out

def ensure_quarter_hour(df: pd.DataFrame, method: str = "pad", expand_edges: bool = True) -> pd.DataFrame:
    """
    Aligns to 15-min cadence. If expand_edges=True, floors the start and ceils the end,
    so no original data outside range is lost by trimming.
    """
    df = df.copy().set_index("timestamp")
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")

    if expand_edges:
        start = df.index.min().floor("15min")
        end   = df.index.max().ceil("15min")
    else:
        start = df.index.min().ceil("15min")
        end   = df.index.max().floor("15min")

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
