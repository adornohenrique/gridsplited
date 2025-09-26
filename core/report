# report.py
from io import BytesIO
import pandas as pd

def build_report(prices_aligned: pd.DataFrame,
                 dispatch_df: pd.DataFrame | None = None,
                 kpis: dict | None = None,
                 battery_df: pd.DataFrame | None = None) -> bytes:
    bio = BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as xw:
        (prices_aligned or pd.DataFrame()).to_excel(xw, sheet_name="Prices", index=False)
        if dispatch_df is not None and not dispatch_df.empty:
            dispatch_df.to_excel(xw, sheet_name="Dispatch", index=False)
        if kpis:
            pd.DataFrame([kpis]).to_excel(xw, sheet_name="KPIs", index=False)
        if battery_df is not None and not battery_df.empty:
            battery_df.to_excel(xw, sheet_name="Battery", index=False)
        pd.DataFrame({"Info":[
            "All steps are 15-minute intervals.",
            "Prices aligned to quarter-hours (edges expanded, gaps filled).",
            "Dispatch uses parameters set at run time.",
        ]}).to_excel(xw, sheet_name="README", index=False)
    bio.seek(0)
    return bio.getvalue()
