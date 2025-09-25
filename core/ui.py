# core/ui.py
import os
import io
import pandas as pd
import streamlit as st
from types import SimpleNamespace
from . import constants
from . import economics  # for benchmark display

def display_logo(logo_path: str):
    if os.path.exists(logo_path):
        st.image(logo_path, use_container_width=True)
    else:
        st.warning(f"⚠️ Logo file not found ({logo_path}). Place it next to app.py.")

def sidebar() -> SimpleNamespace:
    with st.sidebar:
        st.header("Inputs — Operations")
        uploaded = st.file_uploader("15-min price file (CSV or Excel)", type=["csv","xlsx","xls"])
        st.caption("Needs columns (or autodetected): timestamp and price.")

        d = constants.DEFAULTS
        plant_capacity_mw = st.number_input("Plant capacity (MW)", value=d["PLANT_CAP_MW"], min_value=0.1, step=1.0)
        min_load_pct = st.slider("Min load (%)", 0.0, 100.0, d["MIN_LOAD_PCT"], step=1.0) / 100.0
        max_load_pct = st.slider("Max load (%)", 0.0, 100.0, d["MAX_LOAD_PCT"], step=1.0) / 100.0
        break_even = st.number_input("Break-even power price (€/MWh)", value=d["BREAK_EVEN_EUR_MWH"], step=1.0)
        ramp_limit = st.number_input("Ramp limit (MW per 15-min) (optional)", value=d["RAMP_LIMIT_MW"], step=0.5)
        always_on = st.checkbox("Always on (≥ min load)", value=d["ALWAYS_ON"])

        st.header("Inputs — Production & Economics")
        mwh_per_ton = st.number_input("Electricity per ton (MWh/t)", value=d["MWH_PER_TON"], step=0.1)
        methanol_price = st.number_input("Methanol price (€/t)", value=d["MEOH_PRICE"], step=10.0)
        co2_price = st.number_input("CO₂ price (€/t)", value=d["CO2_PRICE"], step=1.0)
        co2_intensity = st.number_input("CO₂ needed (t CO₂ per t MeOH)", value=d["CO2_INTENSITY"], step=0.025)
        maint_pct = st.number_input("Maintenance (% of revenue)", value=d["MAINT_PCT"], step=0.5) / 100.0
        sga_pct   = st.number_input("SG&A (% of revenue)", value=d["SGA_PCT"], step=0.5) / 100.0
        ins_pct   = st.number_input("Insurance (% of revenue)", value=d["INS_PCT"], step=0.5) / 100.0

        st.header("Optional — Benchmark & OPEX")
        water_cost_t = st.number_input("Water cost (€/t)", value=d["WATER_COST_T"], step=0.1, min_value=0.0)
        trader_margin_pct_ui = st.number_input("Trader margin (% of MeOH revenue)", value=d["TRADER_MARGIN_PCT_UI"], step=1.0, min_value=0.0)
        other_opex_per_t = st.number_input("Other variable OPEX (€/t)", value=d["OTHER_OPEX_T"], step=1.0, min_value=0.0)

        # Display benchmark value based on current entries (preview only)
        be_from_benchmark = economics.benchmark_power_price(
            p_methanol=methanol_price,
            p_co2=co2_price,
            water_cost_eur_per_t=water_cost_t,
            trader_margin_pct=trader_margin_pct_ui,
            power_mwh_per_t=float(mwh_per_ton),
            co2_t_per_t=float(co2_intensity),
        )
        st.caption("Benchmark formula: (pMeOH − CO₂_need·pCO₂ − water − margin%·pMeOH) / MWh_per_t")
        st.info(f"Benchmark power price = **{be_from_benchmark:,.2f} €/MWh**")
        use_bench_as_break_even = st.checkbox("Use this Benchmark as Break-even for dispatch", value=False)

        st.header("Target margin control")
        margin_method = st.radio("Margin method", ["Power-only (vs BE)", "Full-economics"], index=0)
        target_margin_pct = st.number_input("Target margin (%)", value=d["TARGET_MARGIN_PCT"], step=1.0, min_value=0.0, max_value=95.0)

        run = st.button("Run Optimization")

    return SimpleNamespace(
        uploaded=uploaded,
        plant_capacity_mw=plant_capacity_mw,
        min_load_pct=min_load_pct,
        max_load_pct=max_load_pct,
        break_even=break_even,
        ramp_limit=ramp_limit,
        always_on=always_on,
        mwh_per_ton=mwh_per_ton,
        methanol_price=methanol_price,
        co2_price=co2_price,
        co2_intensity=co2_intensity,
        maint_pct=maint_pct,
        sga_pct=sga_pct,
        ins_pct=ins_pct,
        water_cost_t=water_cost_t,
        trader_margin_pct_ui=trader_margin_pct_ui,
        other_opex_per_t=other_opex_per_t,
        use_bench_as_break_even=use_bench_as_break_even,
        margin_method=margin_method,
        target_margin_pct=target_margin_pct,
        run=run,
    )

def downloads(results_df: pd.DataFrame, out_xlsx_path: str):
    st.download_button("Download Excel (full results)",
                       data=open(out_xlsx_path, "rb").read(),
                       file_name="dispatch_plan.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.download_button("Download CSV (full results)",
                       data=results_df.to_csv(index=False).encode("utf-8"),
                       file_name="dispatch_plan.csv",
                       mime="text/csv")
