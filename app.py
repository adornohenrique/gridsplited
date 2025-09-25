# app.py
import os
import streamlit as st
import pandas as pd

from core import ui, io, optimizer

st.set_page_config(page_title="Dispatch Optimizer", layout="wide")
ui.display_logo("logo.png")
st.title("Quarter-hour Dispatch Optimizer (Profit-Max)")

tabs = st.tabs(["Inputs & Run", "Results", "Charts", "Downloads", "Matrix & Portfolio"])

def _compute_price_cap(p):
    break_even = p.BENCHMARK_BE if p.USE_BENCH_AS_BREAK_EVEN else p.BREAK_EVEN_EUR_MWH
    target = float(p.TARGET_MARGIN_PCT) / 100.0

    if str(p.MARGIN_METHOD).lower().startswith("power"):
        cap = max(0.0, (1.0 - target) * float(break_even))
        return cap, "power-only"

    # full-economics
    opex_pct = (p.MAINT_PCT + p.SGA_PCT + p.INS_PCT) / 100.0
    if float(p.MWH_PER_TON) <= 0:
        st.error("Full-economics margin requires Electricity per ton (MWh/t) > 0.")
        return 0.0, "full-econ"

    cap = (
        p.MEOH_PRICE * (1.0 - target - opex_pct)
        - p.CO2_PRICE * p.CO2_INTENSITY
    ) / p.MWH_PER_TON
    return max(0.0, float(cap)), "full-econ"

# ---------------- Tab 1 ----------------
with tabs[0]:
    st.info("Upload your 15-min price file and click **Run Optimization**. CSV/Excel autodetected.")
    params = ui.sidebar()
    price_cap, method_tag = _compute_price_cap(params)

    if params.run:
        if params.uploaded is None:
            st.error("Please upload a CSV or Excel with timestamp and price.")
            st.stop()

        try:
            df_prices = io.load_prices(params.uploaded)
        except Exception as e:
            st.exception(e)
            st.stop()

        results, kpis = optimizer.run_dispatch(
            df=df_prices,
            plant_capacity_mw=params.PLANT_CAP_MW,
            min_load_pct=params.MIN_LOAD_PCT,
            max_load_pct=params.MAX_LOAD_PCT,
            break_even_eur_per_mwh=(params.BENCHMARK_BE if params.USE_BENCH_AS_BREAK_EVEN else params.BREAK_EVEN_EUR_MWH),
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
        )

        st.session_state["results"] = results
        st.session_state["kpis"] = kpis

        st.success("Optimization complete.")
        st.info(
            f"Applied dispatch price cap: **{price_cap:,.2f} €/MWh** "
            f"(method: {method_tag}, target margin: {params.TARGET_MARGIN_PCT:.1f}%)"
        )

        st.subheader("KPIs (preview)")
        st.dataframe(pd.DataFrame([kpis]))

# ---------------- Tab 2 ----------------
with tabs[1]:
    st.subheader("Results")
    if "results" not in st.session_state:
        st.info("Run an optimization first.")
    else:
        st.dataframe(st.session_state["results"].head(300), use_container_width=True)
        st.json(st.session_state["kpis"])

# ---------------- Tab 3 ----------------
with tabs[2]:
    st.subheader("Charts")
    res = st.session_state.get("results")
    if res is None:
        st.info("Run an optimization first.")
    else:
        if {"timestamp", "price_eur_per_mwh"} <= set(res.columns):
            st.line_chart(res.set_index("timestamp")[["price_eur_per_mwh"]], use_container_width=True)
        if {"timestamp", "dispatch_mw"} <= set(res.columns):
            st.line_chart(res.set_index("timestamp")[["dispatch_mw"]], use_container_width=True)

# ---------------- Tab 4 ----------------
with tabs[3]:
    st.subheader("Downloads")
    res = st.session_state.get("results")
    if res is None:
        st.info("Run an optimization first.")
    else:
        st.download_button(
            "Download CSV (full results)",
            data=res.to_csv(index=False).encode("utf-8"),
            file_name="dispatch_plan.csv",
            mime="text/csv",
            use_container_width=True,
        )

# ---------------- Tab 5 ----------------
with tabs[4]:
    st.subheader("Matrix & Portfolio")
    st.info("Coming soon: scenario matrix + batch runs.")
