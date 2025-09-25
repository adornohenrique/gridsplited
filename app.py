# app.py
import os
import streamlit as st
import pandas as pd

from core import ui, io, optimizer

st.set_page_config(page_title="Dispatch Optimizer", layout="wide")

# Header
ui.display_logo("logo.png")
st.title("Quarter-hour Dispatch Optimizer (Profit-Max)")

# --------- Helpers (cached parsing & downsampling) ---------
@st.cache_data(show_spinner=False)
def _parse_prices_cached(file_bytes: bytes, filename: str) -> pd.DataFrame:
    return io.load_prices_from_bytes(file_bytes, filename)

def _downsample(df: pd.DataFrame, max_points: int = 2000) -> pd.DataFrame:
    if len(df) <= max_points:
        return df
    step = max(1, len(df) // max_points)
    return df.iloc[::step, :].reset_index(drop=True)

def _compute_price_cap(params) -> tuple[float, str]:
    be = params.BREAK_EVEN_EUR_MWH
    p = float(params.TARGET_MARGIN_PCT) / 100.0

    if str(params.MARGIN_METHOD).lower().startswith("power"):
        cap = max(0.0, (1.0 - p) * be)
        return cap, "power-only"

    # Full-economics
    o = (params.MAINT_PCT + params.SGA_PCT + params.INS_PCT) / 100.0
    if params.MWH_PER_TON <= 0:
        st.error("Full-economics margin requires Electricity per ton (MWh/t) > 0.")
        return 0.0, "full-econ"
    cap = (params.MEOH_PRICE * (1.0 - p - o) - params.CO2_PRICE * params.CO2_INTENSITY) / params.MWH_PER_TON
    return max(0.0, float(cap)), "full-econ"

# --------- Layout ---------
tabs = st.tabs(["Inputs & Run", "Results", "Charts", "Downloads", "Matrix & Portfolio"])

with tabs[0]:
    st.info("Upload your 15-min price file and click **Run Optimization**. The app auto-detects CSV/Excel formats.")
    params = ui.sidebar()

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

        # Run optimizer with battery
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
            maintenance_pct_of_revenue=params.MAINT_PCT/100.0,
            sga_pct_of_revenue=params.SGA_PCT/100.0,
            insurance_pct_of_revenue=params.INS_PCT/100.0,
            target_margin_fraction=float(params.TARGET_MARGIN_PCT)/100.0,
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

        st.session_state["results"] = results
        st.session_state["kpis"] = kpis

        st.success("Optimization complete.")
        st.info(kpis.get("battery_guidance", ""))

        st.subheader("KPIs (overview)")
        st.dataframe(pd.DataFrame([kpis]), use_container_width=True)

with tabs[1]:
    st.subheader("Results")
    res = st.session_state.get("results")
    if res is None:
        st.info("Run an optimization first.")
    else:
        st.dataframe(res.head(500), use_container_width=True)
        st.json(st.session_state.get("kpis", {}))

with tabs[2]:
    st.subheader("Charts (downsampled to avoid lag)")
    res = st.session_state.get("results")
    if res is None:
        st.info("Run an optimization first.")
    else:
        ds = _downsample(res, max_points=2000).set_index("timestamp")
        if "price_eur_per_mwh" in ds:
            st.line_chart(ds[["price_eur_per_mwh"]], use_container_width=True)
        cols = [c for c in ["dispatch_mw", "grid_mw", "charge_mw", "discharge_mw", "soc_mwh"] if c in ds.columns]
        if cols:
            st.line_chart(ds[cols], use_container_width=True)

with tabs[3]:
    st.subheader("Downloads")
    res = st.session_state.get("results")
    if res is None:
        st.info("Run an optimization first.")
    else:
        st.download_button(
            "Download CSV (results + battery)",
            data=res.to_csv(index=False).encode("utf-8"),
            file_name="dispatch_with_battery.csv",
            mime="text/csv",
            use_container_width=True,
        )

with tabs[4]:
    st.subheader("Matrix & Portfolio")
    st.info("Coming soon: batch scenarios & portfolio view.")
