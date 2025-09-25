# app.py — fixed version
import os
from math import ceil
from types import SimpleNamespace
import io as pyio

import streamlit as st
import pandas as pd

# Import only what we need from core to avoid circular imports
import core.optimizer as optimizer
from core import render_help_button  # from core/help.py

# ---------- Page config ----------
st.set_page_config(page_title="Dispatch Optimizer", layout="wide")

# ---------- Header ----------
if os.path.exists("logo.png"):
    st.image("logo.png", width=220)
st.title("Quarter-hour Dispatch Optimizer (Profit-Max)")

# Help toggle (only in main header)
render_help_button("main")


# ---------- Sidebar UI ----------
def sidebar() -> SimpleNamespace:
    with st.sidebar:
        st.markdown("### Controls")

        st.markdown("#### 1) Price file")
        uploaded = st.file_uploader(
            "Upload CSV/Excel with columns: timestamp, price",
            type=["csv", "xlsx", "xls"],
            key="file_uploader_main"
        )

        st.markdown("#### 2) Plant")
        PLANT_CAP_MW = st.number_input("Plant capacity (MW)", min_value=0.0, value=20.0, step=1.0)
        MIN_LOAD_PCT = st.slider("Min load (%)", 0, 100, 0)
        MAX_LOAD_PCT = st.slider("Max load (%)", 0, 100, 100)
        RAMP_LIMIT_MW = st.number_input("Ramp limit (MW per 15-min, 0 = none)", min_value=0.0, value=0.0, step=0.5)
        ALWAYS_ON = st.checkbox("Always on (no on/off decisions)", value=False)

        st.markdown("#### 3) Economics")
        BREAK_EVEN_EUR_MWH = st.number_input("Break-even (€/MWh)", min_value=0.0, value=60.0, step=1.0)
        MWH_PER_TON = st.number_input("MWh per ton product (optional, 0 = ignore)", min_value=0.0, value=0.0, step=0.1)
        MEOH_PRICE = st.number_input("Product price (€/t)", min_value=0.0, value=1200.0, step=10.0)
        CO2_PRICE = st.number_input("CO₂ price (€/t)", min_value=0.0, value=0.0, step=1.0)
        CO2_INTENSITY = st.number_input("CO₂ intensity (t CO₂ / t product)", min_value=0.0, value=0.0, step=0.01)
        MAINT_PCT = st.number_input("Maintenance (% of revenue)", min_value=0.0, value=2.0, step=0.1)
        SGA_PCT = st.number_input("SG&A (% of revenue)", min_value=0.0, value=2.0, step=0.1)
        INS_PCT = st.number_input("Insurance (% of revenue)", min_value=0.0, value=1.0, step=0.1)
        TARGET_MARGIN_PCT = st.number_input("Target margin (%)", min_value=0.0, value=10.0, step=0.5)

        st.markdown("#### 4) Battery (optional)")
        BATTERY_ENERGY_MWH = st.number_input("Battery energy (MWh)", min_value=0.0, value=0.0, step=1.0)
        BATTERY_POWER_MW = st.number_input("Battery power (MW)", min_value=0.0, value=0.0, step=0.5)
        BATTERY_EFF_CHG = st.number_input("Charge efficiency (0–1)", min_value=0.0, max_value=1.0, value=0.98, step=0.01)
        BATTERY_EFF_DIS = st.number_input("Discharge efficiency (0–1)", min_value=0.0, max_value=1.0, value=0.98, step=0.01)
        SOC_INIT_PCT = st.number_input("SOC initial (%)", min_value=0.0, max_value=100.0, value=50.0, step=1.0)
        SOC_MIN_PCT = st.number_input("SOC min (%)", min_value=0.0, max_value=100.0, value=0.0, step=1.0)
        SOC_MAX_PCT = st.number_input("SOC max (%)", min_value=0.0, max_value=100.0, value=100.0, step=1.0)
        DEADBAND_FRAC = st.number_input("Price deadband (fraction, e.g., 0.02 = 2%)", min_value=0.0, max_value=1.0, value=0.02, step=0.01)

        run = st.button("▶️ Run Optimization", use_container_width=True)

    return SimpleNamespace(
        uploaded=uploaded,
        PLANT_CAP_MW=PLANT_CAP_MW,
        MIN_LOAD_PCT=MIN_LOAD_PCT,
        MAX_LOAD_PCT=MAX_LOAD_PCT,
        RAMP_LIMIT_MW=RAMP_LIMIT_MW,
        ALWAYS_ON=ALWAYS_ON,
        BREAK_EVEN_EUR_MWH=BREAK_EVEN_EUR_MWH,
        MWH_PER_TON=MWH_PER_TON,
        MEOH_PRICE=MEOH_PRICE,
        CO2_PRICE=CO2_PRICE,
        CO2_INTENSITY=CO2_INTENSITY,
        MAINT_PCT=MAINT_PCT,
        SGA_PCT=SGA_PCT,
        INS_PCT=INS_PCT,
        TARGET_MARGIN_PCT=TARGET_MARGIN_PCT,
        BATTERY_ENERGY_MWH=BATTERY_ENERGY_MWH,
        BATTERY_POWER_MW=BATTERY_POWER_MW,
        BATTERY_EFF_CHG=BATTERY_EFF_CHG,
        BATTERY_EFF_DIS=BATTERY_EFF_DIS,
        SOC_INIT_PCT=SOC_INIT_PCT,
        SOC_MIN_PCT=SOC_MIN_PCT,
        SOC_MAX_PCT=SOC_MAX_PCT,
        DEADBAND_FRAC=DEADBAND_FRAC,
        run=run,
    )


# ---------- Helpers ----------
def _compute_price_cap(params: SimpleNamespace) -> tuple[float, str]:
    return float(params.BREAK_EVEN_EUR_MWH), "break_even"


@st.cache_data(show_spinner=False)
def _parse_prices_cached(file_bytes: bytes, filename: str) -> pd.DataFrame:
    ext = os.path.splitext(filename)[1].lower()
    if ext in [".xlsx", ".xls"]:
        data = pd.read_excel(pyio.BytesIO(file_bytes))
    else:
        data = pd.read_csv(pyio.BytesIO(file_bytes))

    cols_lower = {c.lower(): c for c in data.columns}
    ts_col = cols_lower.get("timestamp") or cols_lower.get("time") or list(data.columns)[0]
    price_col = cols_lower.get("price") or list(data.columns)[1]

    df = data[[ts_col, price_col]].rename(columns={ts_col: "timestamp", price_col: "price_eur_per_mwh"})
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).reset_index(drop=True)
    return df.sort_values("timestamp").reset_index(drop=True)


def _downsample(df: pd.DataFrame, max_points: int = 2000) -> pd.DataFrame:
    if len(df) <= max_points:
        return df.copy()
    step = ceil(len(df) / max_points)
    return df.iloc[::step, :].reset_index(drop=True)


# ---------- Layout ----------
params = sidebar()  # ✅ only once

tabs = st.tabs(["Inputs & Run", "Results", "Charts", "Downloads", "Matrix & Portfolio"])

with tabs[0]:
    ...
    # (unchanged: use params normally here)

with tabs[4]:
    st.subheader("Project Design Advisor")

    st.write("""
    Upload your energy profile and the tool will determine:
    - Whether a battery is required to keep the plant above minimum load,
    - The **optimal battery size** (if needed),
    - Methanol production and revenues.
    """)

    if params.uploaded is None:
        st.info("Upload your 15-min energy price profile in the sidebar to continue.")
        st.stop()

    file_bytes = params.uploaded.getvalue()
    filename = params.uploaded.name
    df_prices = _parse_prices_cached(file_bytes, filename)

    ...
    # (rest of Advisor code unchanged, but using params from above)
