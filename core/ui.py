# core/ui.py
import os
import io
import pandas as pd
import streamlit as st
from types import SimpleNamespace
from . import constants

# ---- Header helpers ----
def display_logo(logo_path: str):
    """
    Show a logo centered at the top, if present.
    """
    if os.path.exists(logo_path):
        st.image(logo_path, use_container_width=True)
    else:
        st.warning(f"⚠️ Logo file not found ({logo_path}). Place it next to app.py.")

# ---- Sidebar / input mask ----
def sidebar() -> SimpleNamespace:
    with st.sidebar:
        st.header("Inputs — Operations")
        uploaded = st.file_uploader("15-min price file (CSV or Excel)", type=["csv", "xlsx", "xls"])
        st.caption("Needs columns (or autodetected): timestamp and price.")

        d = dict(constants.DEFAULTS)  # start from defaults

        # Operations
        d["PLANT_CAP_MW"] = st.number_input("Plant capacity (MW)", value=d["PLANT_CAP_MW"], min_value=0.1, step=1.0)
        d["MIN_LOAD_PCT"] = st.slider("Min load (%)", 0.0, 100.0, float(d["MIN_LOAD_PCT"]), step=1.0)
        d["MAX_LOAD_PCT"] = st.slider("Max load (%)", 0.0, 100.0, float(d["MAX_LOAD_PCT"]), step=1.0)
        d["BREAK_EVEN_EUR_MWH"] = st.number_input("Break-even power price (€/MWh)", value=d["BREAK_EVEN_EUR_MWH"], step=1.0)
        d["RAMP_LIMIT_MW"] = st.number_input("Ramp limit (MW per 15-min) (optional)", value=d["RAMP_LIMIT_MW"], step=0.5)
        d["ALWAYS_ON"] = st.checkbox("Always on (≥ min load)", value=d["ALWAYS_ON"])

        st.header("Inputs — Production & Economics")
        d["MWH_PER_TON"] = st.number_input("Electricity per ton (MWh/t)", value=d["MWH_PER_TON"], step=0.1)
        d["MEOH_PRICE"] = st.number_input("Methanol price (€/t)", value=d["MEOH_PRICE"], step=10.0)
        d["CO2_PRICE"] = st.number_input("CO₂ price (€/t)", value=d["CO2_PRICE"], step=1.0)
        d["CO2_INTENSITY"] = st.number_input("CO₂ needed (t CO₂ per t MeOH)", value=d["CO2_INTENSITY"], step=0.025)
        d["MAINT_PCT"] = st.number_input("Maintenance (% of revenue)", value=d["MAINT_PCT"], step=0.5) / 100.0
        d["SGA_PCT"]   = st.number_input("SG&A (% of revenue)", value=d["SGA_PCT"], step=0.5) / 100.0
        d["INS_PCT"]   = st.number_input("Insurance (% of revenue)", value=d["INS_PCT"], step=0.5) / 100.0

        st.header("Optional — Benchmark & OPEX")
        st.caption(
            f"Using Electricity per ton = {d['MWH_PER_TON']} MWh/t and CO₂ need = {d['CO2_INTENSITY']} t/t from 'Production & Economics'."
        )
        d["WATER_COST_T"] = st.number_input("Water cost (€/t)", value=d["WATER_COST_T"], step=0.1, min_value=0.0)
        d["TRADER_MARGIN_PCT_UI"] = st.number_input(
            "Trader margin for benchmark (% of MeOH revenue)", value=d["TRADER_MARGIN_PCT_UI"], step=1.0, min_value=0.0, max_value=100.0
        )
        d["OTHER_OPEX_T"] = st.number_input("Other variable OPEX (€/t)", value=d["OTHER_OPEX_T"], step=1.0, min_value=0.0)

        d["USE_BENCH_AS_BREAK_EVEN"] = st.checkbox(
            "Use this Benchmark as Break-even for dispatch",
            value=False,
            help="If checked, replaces the main Break-even (€/MWh) with the computed benchmark above."
        )

        st.header("Target margin control")
        d["MARGIN_METHOD"] = st.radio(
            "Margin method",
            ["Power-only (vs BE)", "Full-economics"],
            index=0 if constants.DEFAULTS["MARGIN_METHOD_DEFAULT"].startswith("Power") else 1,
            help="Choose how to compute the price cap used for dispatch."
        )
        d["TARGET_MARGIN_PCT"] = st.number_input("Target margin (%)", value=d["TARGET_MARGIN_PCT"], step=1.0, min_value=0.0, max_value=95.0)

        # Battery
        st.header("Battery (optional)")
        d["BATTERY_ENABLED"] = st.checkbox("Enable battery optimization", value=d["BATTERY_ENABLED"])
        if d["BATTERY_ENABLED"]:
            d["BATT_CAP_MWH"] = st.number_input("Battery energy capacity (MWh)", value=d["BATT_CAP_MWH"], step=1.0, min_value=0.0)
            d["BATT_P_CHARGE_MW"] = st.number_input("Max charge power (MW)", value=d["BATT_P_CHARGE_MW"], step=0.5, min_value=0.0)
            d["BATT_P_DISCHARGE_MW"] = st.number_input("Max discharge power (MW)", value=d["BATT_P_DISCHARGE_MW"], step=0.5, min_value=0.0)
            d["BATT_ETA_CHARGE"] = st.number_input("Charge efficiency (0–1)", value=d["BATT_ETA_CHARGE"], step=0.01, min_value=0.0, max_value=1.0)
            d["BATT_ETA_DISCHARGE"] = st.number_input("Discharge efficiency (0–1)", value=d["BATT_ETA_DISCHARGE"], step=0.01, min_value=0.0, max_value=1.0)
            d["BATT_SOC_INIT_PCT"] = st.number_input("Initial SoC (%)", value=d["BATT_SOC_INIT_PCT"], step=1.0, min_value=0.0, max_value=100.0)
            d["BATT_SOC_MIN_PCT"] = st.number_input("Min SoC (%)", value=d["BATT_SOC_MIN_PCT"], step=1.0, min_value=0.0, max_value=100.0)
            d["BATT_SOC_MAX_PCT"] = st.number_input("Max SoC (%)", value=d["BATT_SOC_MAX_PCT"], step=1.0, min_value=0.0, max_value=100.0)
            d["BATT_LOW_PRICE"] = st.number_input("Charge when price ≤ (€/MWh)", value=d["BATT_LOW_PRICE"], step=1.0)
            d["BATT_HIGH_PRICE"] = st.number_input("Discharge when price ≥ (€/MWh)", value=d["BATT_HIGH_PRICE"], step=1.0)
            d["BATT_DEGR_EUR_PER_MWH"] = st.number_input("Degradation cost (€/MWh throughput)", value=d["BATT_DEGR_EUR_PER_MWH"], step=0.5, min_value=0.0)
            d["BATT_ENFORCE_FINAL_SOC"] = st.checkbox("Enforce final SoC = initial SoC", value=d["BATT_ENFORCE_FINAL_SOC"])

        # Run button
        run = st.button("Run Optimization")

    # normalize/pack
    d["uploaded"] = uploaded
    d["run"] = run

    return SimpleNamespace(**d)
