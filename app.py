# app.py — full working file (drop-in)
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

# Help toggle (place in main; for sidebar use render_help_button('sidebar'))
render_help_button("main")


# ---------- Sidebar UI (replaces old ui.sidebar()) ----------
def sidebar() -> SimpleNamespace:
    with st.sidebar:
        st.markdown("### Controls")
        render_help_button("sidebar")

        st.markdown("#### 1) Price file")
        uploaded = st.file_uploader(
            "Upload CSV/Excel with columns: timestamp, price",
            type=["csv", "xlsx", "xls"],
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


# ---------- Helpers that were previously missing ----------
def _compute_price_cap(params: SimpleNamespace) -> tuple[float, str]:
    """
    Minimal placeholder for your price-cap logic.
    Returns (cap_value, method_tag).
    """
    return float(params.BREAK_EVEN_EUR_MWH), "break_even"


@st.cache_data(show_spinner=False)
def _parse_prices_cached(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """
    Accepts CSV/XLS(X) with columns:
      - 'timestamp' (datetime-like)
      - 'price' (€/MWh)
    Returns DataFrame with ['timestamp','price_eur_per_mwh'].
    """
    ext = os.path.splitext(filename)[1].lower()
    data = None
    if ext in [".xlsx", ".xls"]:
        data = pd.read_excel(pyio.BytesIO(file_bytes))
    else:
        data = pd.read_csv(pyio.BytesIO(file_bytes))

    # Flexible column handling
    cols_lower = {c.lower(): c for c in data.columns}
    ts_col = cols_lower.get("timestamp") or cols_lower.get("time") or list(data.columns)[0]
    price_col = cols_lower.get("price") or list(data.columns)[1]

    df = data[[ts_col, price_col]].rename(columns={ts_col: "timestamp", price_col: "price_eur_per_mwh"})
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).reset_index(drop=True)

    # Ensure sorted
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def _downsample(df: pd.DataFrame, max_points: int = 2000) -> pd.DataFrame:
    if len(df) <= max_points:
        return df.copy()
    step = ceil(len(df) / max_points)
    return df.iloc[::step, :].reset_index(drop=True)


# ---------- Layout ----------
tabs = st.tabs(["Inputs & Run", "Results", "Charts", "Downloads", "Matrix & Portfolio"])

with tabs[0]:
    st.info("Upload your 15-min price file and click **Run Optimization**. The app auto-detects CSV/Excel formats.")
    params = sidebar()

    price_cap, method_tag = _compute_price_cap(params)
    st.caption(f"Calculated price cap: **{price_cap:,.2f} €/MWh** (method: {method_tag})")

    if params.run:
        if params.uploaded is None:
            st.error("Please upload a CSV or Excel with 'timestamp' and 'price'.")
            st.stop()

        # Parse with caching to avoid lag on reruns
        file_bytes = params.uploaded.getvalue()
        filename = params.uploaded.name
        try:
            df_prices = _parse_prices_cached(file_bytes, filename)
        except Exception as e:
            st.exception(e)
            st.stop()

        # ---- Run optimizer (with battery parameters) ----
        try:
            results, kpis = optimizer.run_dispatch_with_battery(
                df=df_prices,
                plant_capacity_mw=params.PLANT_CAP_MW,
                min_load_pct=params.MIN_LOAD_PCT,
                max_load_pct=params.MAX_LOAD_PCT,
                break_even_eur_per_mwh=params.BREAK_EVEN_EUR_MWH,
                ramp_limit_mw_per_step=(params.RAMP_LIMIT_MW if params.RAMP_LIMIT_MW > 0 else None),
                always_on=params.ALWAYS_ON,
                dispatch_threshold_eur_per_mwh=price_cap,
                mwh_per_ton=(params.MWH_PER_TON if params.MWH_PER_TON > 0 else None),
                methanol_price_eur_per_ton=params.MEOH_PRICE,
                co2_price_eur_per_ton=params.CO2_PRICE,
                co2_t_per_ton_meoh=params.CO2_INTENSITY,
                maintenance_pct_of_revenue=params.MAINT_PCT / 100.0,
                sga_pct_of_revenue=params.SGA_PCT / 100.0,
                insurance_pct_of_revenue=params.INS_PCT / 100.0,
                target_margin_fraction=float(params.TARGET_MARGIN_PCT) / 100.0,
                margin_method=method_tag,
                batt_energy_mwh=params.BATTERY_ENERGY_MWH,
                batt_power_mw=params.BATTERY_POWER_MW,
                eff_chg=params.BATTERY_EFF_CHG,
                eff_dis=params.BATTERY_EFF_DIS,
                soc_init_pct=params.SOC_INIT_PCT,
                soc_min_pct=params.SOC_MIN_PCT,
                soc_max_pct=params.SOC_MAX_PCT,
                deadband_frac=params.DEADBAND_FRAC,
            )
        except Exception as e:
            st.error("The optimizer raised an exception. Please check parameters or contact support.")
            st.exception(e)
            st.stop()

        st.session_state["results"] = results
        st.session_state["kpis"] = kpis

        st.success("Optimization complete.")
        if isinstance(kpis, dict):
            st.info(kpis.get("battery_guidance", ""))

        st.subheader("KPIs (overview)")
        try:
            st.dataframe(pd.DataFrame([kpis]), use_container_width=True)
        except Exception:
            st.json(kpis)

with tabs[1]:
    st.subheader("Results")
    res = st.session_state.get("results")
    if res is None:
        st.info("Run an optimization first.")
    else:
        # Show up to 500 rows to keep the UI responsive
        try:
            st.dataframe(res.head(500), use_container_width=True)
        except Exception:
            # If it's not a DataFrame
            st.json(res)
        st.json(st.session_state.get("kpis", {}))

with tabs[2]:
    st.subheader("Charts (downsampled to avoid lag)")
    res = st.session_state.get("results")
    if res is None:
        st.info("Run an optimization first.")
    else:
        try:
            ds = _downsample(res, max_points=2000).set_index("timestamp")
            if "price_eur_per_mwh" in ds:
                st.line_chart(ds[["price_eur_per_mwh"]], use_container_width=True)
            cols = [c for c in ["dispatch_mw", "grid_mw", "charge_mw", "discharge_mw", "soc_mwh"] if c in ds.columns]
            if cols:
                st.line_chart(ds[cols], use_container_width=True)
        except Exception as e:
            st.warning("Could not render charts from results; ensure 'timestamp' column exists.")
            st.exception(e)

with tabs[3]:
    st.subheader("Downloads")
    res = st.session_state.get("results")
    if res is None:
        st.info("Run an optimization first.")
    else:
        try:
            st.download_button(
                "Download CSV (results + battery)",
                data=res.to_csv(index=False).encode("utf-8"),
                file_name="dispatch_with_battery.csv",
                mime="text/csv",
                use_container_width=True,
            )
        except Exception as e:
            st.warning("Results are not a DataFrame; cannot export CSV.")
            st.exception(e)

with tabs[4]:
    st.subheader("Matrix & Portfolio")
    st.info("Coming soon: batch scenarios & portfolio view.")
