# core/io.py
import io
import pandas as pd

def _standardize_cols(df0: pd.DataFrame):
    if df0 is None or df0.empty:
        return None
    cols_map = {str(c).strip().lower(): c for c in df0.columns}
    ts_key = next((k for k in cols_map if any(x in k for x in ["timestamp","time","datetime","interval","start","date"])), None)
    pr_key = next((k for k in cols_map if any(x in k for x in ["price","lmp","eur_per_mwh","usd_per_mwh","$/mwh","€/mwh"])), None)
    if ts_key and pr_key:
        out = df0[[cols_map[ts_key], cols_map[pr_key]]].copy()
        out.columns = ["timestamp", "price_eur_per_mwh"]
        return out
    if df0.shape[1] == 2:
        out = df0.copy()
        out.columns = ["timestamp", "price_eur_per_mwh"]
        return out
    return None

def load_prices(uploaded) -> pd.DataFrame:
    name = uploaded.name.lower()
    df = None

    if name.endswith((".xlsx", ".xls")):
        xls = pd.ExcelFile(uploaded)
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
        try:
            tmp = pd.read_csv(io.BytesIO(content), sep=None, engine="python")
            df = _standardize_cols(tmp)
        except Exception:
            df = None
        if df is None:
            for sep in [";", "\t", ","]:
                try:
                    tmp = pd.read_csv(io.BytesIO(content), sep=sep)
                    df = _standardize_cols(tmp)
                    if df is not None:
                        break
                except Exception:
                    continue
        if df is None:
            raise ValueError("CSV must contain timestamp and price columns. Save as CSV (UTF-8) with headers: timestamp, price_eur_per_mwh.")

    df = df.dropna(how="all")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    if df["price_eur_per_mwh"].dtype == object:
        df["price_eur_per_mwh"] = df["price_eur_per_mwh"].astype(str).str.replace(",", ".", regex=False)
    df["price_eur_per_mwh"] = pd.to_numeric(df["price_eur_per_mwh"], errors="coerce")
    df = df.dropna(subset=["timestamp", "price_eur_per_mwh"])
    df = df.sort_values("timestamp").drop_duplicates(subset=["timestamp"]).reset_index(drop=True)
    if df.empty:
        raise ValueError("No valid rows after parsing. Check your timestamp and price columns.")
    return df
