# core/ui.py
import os
import streamlit as st
from types import SimpleNamespace
from . import constants

def display_logo(logo_path: str):
    if os.path.exists(logo_path):
        st.image(logo_path, use_container_width=True)

def sidebar() -> SimpleNamespace:
    d = constants.DEFAULTS

    with st.sidebar:
        st.header("Inputs — Operations")
        uploaded = st.file_uploader("15-min price file (CSV or Excel)", type=["csv","xlsx","xls"])
        st.caption("CSV/Excel autodetected (needs 'timestamp' and 'price' columns).")

        plant_cap_mw = st.number_input("Plant capacity (MW)", value=d["PLANT_CAP_MW"], min_value=0.1, step=1.0)
        min_load_pct = st.slider("Min load (%)", 0.0, 100.0, d["MIN_LOAD_PCT"], step=1.0)
        max_load_pct = st.slider("Max load (%)", 0.0, 100.0, d["MAX_LOAD_PCT"], step=1.0)
        break_even = st.number_input("Break-even power price (€/MWh)", value=d["BREAK_EVEN_EUR_MWH"], step=1.0)
        ramp_limit = st.number_input("Ramp limit (MW per 15-min) (optional)", value=d["RAMP_LIMIT_MW"], step=0.5)
        always_on = st.checkbox("Always on (≥ min load)", value=d["ALWAYS_ON"])

        st.header("Production & Economics")
        mwh_per_ton = st.number_input("Electricity per ton (MWh/t)", value=d["MWH_PER_TON"], step=0.1)
        meoh_price = st.number_input("Methanol price (€/t)", value=d["MEOH_PRICE"], step=10.0)
        co2_price = st.number_input("CO₂ price (€/t)", value=d["CO2_PRICE"], step=1.0)
        co2_intensity = st.number_input("CO₂ needed (t CO₂ per t MeOH)", value=d["CO2_INTENSITY"], step=0.025)
        maint_pct = st.number_input("Maintenance (% of revenue)", value=d["MAINT_PCT"], step=0.5)
        sga_pct   = st.number_input("SG&A (% of revenue)", value=d["SGA_PCT"], step=0.5)
        ins_pct   = st.number_input("Insurance (% of revenue)", value=d["INS_PCT"], step=0.5)

        st.header("Target margin control")
        margin_method = st.radio("Margin method", ["Power-only (vs BE)", "Full-economics"], index=0)
        target_margin_pct = st.number_input("Target margin (%)", value=d["TARGET_MARGIN_PCT"], step=1.0, min_value=0.0, max_value=95.0)

        st.header("Battery (optional)")
        batt_energy_mwh = st.number_input("Battery capacity (MWh)", value=d["BATTERY_ENERGY_MWH"], min_value=0.0, step=1.0)
        batt_power_mw   = st.number_input("Battery power (MW)", value=d["BATTERY_POWER_MW"], min_value=0.0, step=0.5)
        eff_chg         = st.number_input("Charge efficiency", value=d["BATTERY_EFF_CHG"], min_value=0.5, max_value=1.0, step=0.01)
        eff_dis         = st.number_input("Discharge efficiency", value=d["BATTERY_EFF_DIS"], min_value=0.5, max_value=1.0, step=0.01)
        soc_init_pct    = st.number_input("Initial SOC (%)", value=d["SOC_INIT_PCT"], min_value=0.0, max_value=100.0, step=1.0)
        soc_min_pct     = st.number_input("Min SOC (%)", value=d["SOC_MIN_PCT"], min_value=0.0, max_value=99.0, step=1.0)
        soc_max_pct     = st.number_input("Max SOC (%)", value=d["SOC_MAX_PCT"], min_value=1.0, max_value=100.0, step=1.0)
        deadband_frac   = st.number_input("Battery price deadband (%)", value=d["DEADBAND_FRAC"]*100, min_value=0.0, max_value=20.0, step=0.5) / 100.0

        run = st.button("Run Optimization", use_container_width=True)

    return SimpleNamespace(
        uploaded=uploaded,
        run=run,
        PLANT_CAP_MW=float(plant_cap_mw),
        MIN_LOAD_PCT=float(min_load_pct),
        MAX_LOAD_PCT=float(max_load_pct),
        BREAK_EVEN_EUR_MWH=float(break_even),
        RAMP_LIMIT_MW=float(ramp_limit),
        ALWAYS_ON=bool(always_on),
        MWH_PER_TON=float(mwh_per_ton),
        MEOH_PRICE=float(meoh_price),
        CO2_PRICE=float(co2_price),
        CO2_INTENSITY=float(co2_intensity),
        MAINT_PCT=float(maint_pct),
        SGA_PCT=float(sga_pct),
        INS_PCT=float(ins_pct),
        TARGET_MARGIN_PCT=float(target_margin_pct),
        MARGIN_METHOD=str(margin_method),
        BATTERY_ENERGY_MWH=float(batt_energy_mwh),
        BATTERY_POWER_MW=float(batt_power_mw),
        BATTERY_EFF_CHG=float(eff_chg),
        BATTERY_EFF_DIS=float(eff_dis),
        SOC_INIT_PCT=float(soc_init_pct),
        SOC_MIN_PCT=float(soc_min_pct),
        SOC_MAX_PCT=float(soc_max_pct),
        DEADBAND_FRAC=float(deadband_frac),
    )
