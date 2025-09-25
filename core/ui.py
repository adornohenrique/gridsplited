# core/ui.py
import os
import json
import streamlit as st
import pandas as pd
from types import SimpleNamespace
from . import constants

def display_logo(logo_path: str):
    if os.path.exists(logo_path):
        st.image(logo_path, use_container_width=True)
    else:
        st.warning(f"⚠️ Logo file not found ({logo_path}). Place it next to app.py.")

def _scenario_download(params: dict):
    st.download_button(
        "💾 Download scenario",
        data=json.dumps(params, indent=2).encode(),
        file_name="scenario.json",
        mime="application/json",
        use_container_width=True
    )

def _scenario_upload():
    up = st.file_uploader("Load scenario (.json)", type=["json"], key="scen_json_up")
    if up:
        try:
            loaded = json.loads(up.getvalue().decode())
            st.success("Scenario loaded. Values will be applied where possible.")
            return loaded
        except Exception as e:
            st.error(f"Could not parse scenario JSON: {e}")
    return None

def sidebar() -> SimpleNamespace:
    st.sidebar.header("Inputs — Operations")
    uploaded = st.sidebar.file_uploader("15-min price file (CSV or Excel)", type=["csv","xlsx","xls"], accept_multiple_files=False)
    st.sidebar.caption("Needs columns (or autodetected): timestamp and price.")

    d = constants.DEFAULTS

    plant_capacity_mw = st.sidebar.number_input("Plant capacity (MW)", value=d["PLANT_CAP_MW"], min_value=0.1, step=1.0)
    min_load_pct = st.sidebar.slider("Min load (%)", 0.0, 100.0, d["MIN_LOAD_PCT"], step=1.0) / 100.0
    max_load_pct = st.sidebar.slider("Max load (%)", 0.0, 100.0, d["MAX_LOAD_PCT"], step=1.0) / 100.0
    break_even = st.sidebar.number_input("Break-even power price (€/MWh)", value=d["BREAK_EVEN_EUR_MWH"], step=1.0)
    ramp_limit = st.sidebar.number_input("Ramp limit (MW per 15-min) (optional)", value=d["RAMP_LIMIT_MW"], step=0.5)
    always_on = st.sidebar.checkbox("Always on (≥ min load)", value=d["ALWAYS_ON"])

    st.sidebar.header("Inputs — Production & Economics")
    mwh_per_ton = st.sidebar.number_input("Electricity per ton (MWh/t)", value=d["MWH_PER_TON"], step=0.1)
    methanol_price = st.sidebar.number_input("Methanol price (€/t)", value=d["MEOH_PRICE"], step=10.0)
    co2_price = st.sidebar.number_input("CO₂ price (€/t)", value=d["CO2_PRICE"], step=1.0)
    co2_intensity = st.sidebar.number_input("CO₂ needed (t CO₂ per t MeOH)", value=d["CO2_INTENSITY"], step=0.025)
    maint_pct = st.sidebar.number_input("Maintenance (% of revenue)", value=d["MAINT_PCT"], step=0.5) / 100.0
    sga_pct   = st.sidebar.number_input("SG&A (% of revenue)", value=d["SGA_PCT"], step=0.5) / 100.0
    ins_pct   = st.sidebar.number_input("Insurance (% of revenue)", value=d["INS_PCT"], step=0.5) / 100.0

    st.sidebar.header("Optional — Benchmark & OPEX")
    water_cost_t = st.sidebar.number_input("Water cost (€/t)", value=d["WATER_COST_T"], step=0.1, min_value=0.0)
    trader_margin_pct_ui = st.sidebar.number_input(
        "Trader margin for benchmark (% of MeOH revenue)", value=d["TRADER_MARGIN_PCT_UI"], step=1.0, min_value=0.0, max_value=100.0
    )
    other_opex_t = st.sidebar.number_input("Other variable OPEX (€/t)", value=d["OTHER_OPEX_T"], step=1.0, min_value=0.0)
    use_bench_as_break_even = st.sidebar.checkbox("Use Benchmark as Break-even for dispatch", value=False)

    st.sidebar.header("Target margin control")
    MARGIN_METHOD = st.sidebar.radio("Margin method", ["Power-only (vs BE)", "Full-economics"], index=0)
    TARGET_MARGIN_PCT = st.sidebar.number_input("Target margin (%)", value=d["TARGET_MARGIN_PCT"], step=1.0, min_value=0.0, max_value=95.0)

    # ---------------- TOLLING (optional) ----------------
    st.sidebar.header("Tolling (optional)")
    TOLLING_ENABLED = st.sidebar.checkbox("Enable tolling mode?", value=False, help="Use capacity + variable toll revenues instead of product sales.")
    contracted_mw = st.sidebar.number_input("Contracted MW (≤ Plant cap)", value=0.0, min_value=0.0, max_value=float(plant_capacity_mw), step=0.5)
    toll_cap_fee = st.sidebar.number_input("Capacity fee (€/MW-month)", value=0.0, step=10.0, min_value=0.0)
    toll_var_fee = st.sidebar.number_input("Variable fee (€/MWh)", value=0.0, step=1.0, min_value=0.0)
    toll_other_mwh = st.sidebar.number_input("Other variable cost (€/MWh)", value=0.0, step=0.5, min_value=0.0)
    st.sidebar.caption("In Tolling mode, % OPEX (Maint/SGA/Insurance) apply to variable toll revenue.")

    # ---------------- Battery ----------------
    st.sidebar.header("Battery (optional)")
    bat_en = st.sidebar.checkbox("Enable battery?", value=False)
    e_mwh = st.sidebar.number_input("Energy (MWh)", value=10.0)
    p_ch = st.sidebar.number_input("Charge power (MW)", value=5.0)
    p_dis = st.sidebar.number_input("Discharge power (MW)", value=5.0)
    eff_ch = st.sidebar.number_input("Charge efficiency", value=0.95, min_value=0.5, max_value=1.0, step=0.01)
    eff_dis = st.sidebar.number_input("Discharge efficiency", value=0.95, min_value=0.5, max_value=1.0, step=0.01)
    soc_min = st.sidebar.number_input("SOC min (0–1)", value=0.10, min_value=0.0, max_value=1.0, step=0.01)
    soc_max = st.sidebar.number_input("SOC max (0–1)", value=0.90, min_value=0.0, max_value=1.0, step=0.01)
    price_low = st.sidebar.number_input("Charge when price ≤", value=30.0)
    price_high = st.sidebar.number_input("Discharge when price ≥", value=90.0)
    degr = st.sidebar.number_input("Degradation (€/MWh throughput)", value=0.0)

    run = st.sidebar.button("Run Optimization", use_container_width=True)

    # Scenario save/load
    st.sidebar.markdown("---")
    _scenario_download(locals())
    loaded = _scenario_upload()
    if loaded:
        for k, v in loaded.items():
            if k in locals():
                st.session_state[k] = v
        st.sidebar.info("Loaded scenario. Adjust if needed and click Run.")

    return SimpleNamespace(**locals())
