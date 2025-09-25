# core/io.py
import io as _io
import streamlit as st
import pandas as pd

EXPECTED_FREQ_MIN = 15

@st.cache_data(show_spinner=False)
def load_prices(uploaded) -> pd.DataFrame:
    name = uploaded.name.lower()
    if name.endswith((".xlsx", ".xls")):
        xls = pd.ExcelFile(uploaded)
        df = None
        for sh in xls.sheet_names:
            try:
                tmp = pd.read_excel(xls, sheet_name=sh)
                df = _standardize_cols(tmp)
                if df is not None:
                    break
            except Exception:
                continue
        if df is None:
            raise ValueError("Could not find timestamp/price columns in the Excel file.")
    else:
        content = uploaded.read()
        uploaded.seek(0)
        df = None
        # sniff
        try:
            tmp = pd.read_csv(_io.BytesIO(content), sep=None, engine="python")
            df = _standardize_cols(tmp)
        except Exception:
            pass
        if df is None:
            for sep in [";", "\t", ","]:
                try:
                    tmp = pd.read_csv(_io.BytesIO(content), sep=sep)
                    df = _standardize_cols(tmp)
                    if df is not None:
                        break
                except Exception:
                    continue
        if df is None:
            raise ValueError("CSV must contain timestamp and price columns.")

    df = _clean_types(df)
    validate_timeseries(df)
    return df

def _standardize_cols(df0: pd.DataFrame):
    if df0 is None or df0.empty:
        return None
    cols_map = {str(c).strip().lower(): c for c in df0.columns}
    ts_key = next((k for k in cols_map if any(x in k for x in ["timestamp","time","datetime","interval","start","date"])), None)
    pr_key = next((k for k in cols_map if any(x in k for x in ["price","lmp","eur_per_mwh","usd_per_mwh","$/mwh","€/mwh","eur/mwh"])), None)
    if ts_key and pr_key:
        out = df0[[cols_map[ts_key], cols_map[pr_key]]].copy()
        out.columns = ["timestamp", "price_eur_per_mwh"]
        return out
    if df0.shape[1] == 2:
        out = df0.copy()
        out.columns = ["timestamp", "price_eur_per_mwh"]
        return out
    return None

def _clean_types(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(how="all")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    if df["price_eur_per_mwh"].dtype == object:
        df["price_eur_per_mwh"] = df["price_eur_per_mwh"].astype(str).str.replace(",", ".", regex=False)
    df["price_eur_per_mwh"] = pd.to_numeric(df["price_eur_per_mwh"], errors="coerce")
    df = df.dropna(subset=["timestamp", "price_eur_per_mwh"]).sort_values("timestamp").drop_duplicates("timestamp")
    return df.reset_index(drop=True)

def validate_timeseries(df: pd.DataFrame) -> None:
    if not {"timestamp","price_eur_per_mwh"} <= set(df.columns):
        raise ValueError("Missing columns: 'timestamp', 'price_eur_per_mwh'")
    if len(df) < 4:
        raise ValueError("Not enough rows.")
    step = df["timestamp"].diff().dropna().mode().iloc[0]
    mins = int(step.total_seconds()//60)
    if mins != EXPECTED_FREQ_MIN:
        raise ValueError(f"Expected {EXPECTED_FREQ_MIN}-minute data; got ~{mins} minutes.")
