# core/report.py
from io import BytesIO
import pandas as pd
from pandas.api.types import is_datetime64tz_dtype, is_categorical_dtype

def _safe_df(obj) -> pd.DataFrame:
    """Return a DataFrame no matter what we get (None, dict, list, etc.)."""
    if obj is None:
        return pd.DataFrame()
    if isinstance(obj, pd.DataFrame):
        return obj
    try:
        return pd.DataFrame(obj)
    except Exception:
        return pd.DataFrame()

def _prep_for_excel(df: pd.DataFrame) -> pd.DataFrame:
    """Make sure Excel can write it: drop tz info, stringify categoricals."""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    for c in out.columns:
        s = out[c]
        if is_datetime64tz_dtype(s):
            # Excel can't handle tz-aware; convert to naive UTC
            out[c] = s.dt.tz_convert("UTC").dt.tz_localize(None)
        elif is_categorical_dtype(s):
            out[c] = s.astype(str)
    return out

def build_report(prices_aligned,
                 dispatch_df=None,
                 kpis: dict | None = None,
                 battery_df=None) -> bytes:
    prices_aligned = _prep_for_excel(_safe_df(prices_aligned))
    dispatch_df    = _prep_for_excel(_safe_df(dispatch_df))
    battery_df     = _prep_for_excel(_safe_df(battery_df))

    # KPIs (dict) -> single-row DataFrame
    kpis_df = pd.DataFrame([kpis]) if isinstance(kpis, dict) and len(kpis) else pd.DataFrame()

    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as xw:
        prices_aligned.to_excel(xw, sheet_name="Prices", index=False)
        if not dispatch_df.empty:
            dispatch_df.to_excel(xw, sheet_name="Dispatch", index=False)
        if not kpis_df.empty:
            kpis_df.to_excel(xw, sheet_name="KPIs", index=False)
        if not battery_df.empty:
            battery_df.to_excel(xw, sheet_name="Battery", index=False)
        pd.DataFrame({"Info":[
            "All steps are 15-minute intervals.",
            "Prices aligned to quarter-hours (edges expanded, gaps filled).",
            "Dispatch uses parameters set at run time.",
        ]}).to_excel(xw, sheet_name="README", index=False)

    bio.seek(0)
    return bio.getvalue()
