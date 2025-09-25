# core/ui.py
import os
import io
import json
import pandas as pd
import streamlit as st
from types import SimpleNamespace
from . import constants
from . import economics  # for benchmark display
from .io import load_prices

# ----------------------- Field help texts -----------------------
H = {
    "PLANT_CAP_MW": "Nameplate power at 100% load.",
    "MIN_LOAD_PCT": "Minimum technical load as a percentage of capacity.",
    "MAX_LOAD_PCT": "Maximum allowed load as a percentage of capacity (≤100%).",
    "BREAK_EVEN_EUR_MWH": "Power-only break-even price. Used by 'Power-only' margin method.",
    "RAMP_LIMIT_MW": "Max MW change per 15-min step. Set 0 to ignore.",
    "ALWAYS_ON": "If enabled, the plant never drops below Min load.",
    "MWH_PER_TON": "Electricity needed per tonne of product.",
    "MEOH_PRICE": "Product (e.g., methanol) sales price (€/t).",
    "CO2_PRICE": "CO₂ purchase cost (€/t).",
    "CO2_INTENSITY": "CO₂ required in t per tonne of product.",
    "MAINT_PCT": "Maintenance cost as % of revenue.",
    "SGA_PCT": "SG&A cost as % of revenue.",
    "INS_PCT": "Insurance cost as % of revenue.",
    "TARGET_MARGIN_PCT": "Minimum target margin. Drives the dispatch price cap.",
}

# ----------------------- Logo -----------------------
def display_logo(logo_path: str):
    if os.path.exists(logo_path):
        st.image(logo_path, use_container_width=True)
    else:
        st.warning(f"Logo file not found ({logo_path}). Place it next to app.py.")

# ----------------------- Scenario JSON (save/load) -----------------------
def scenario_download(locals_dict):
    """Download a small JSON with your current sidebar inputs (for reuse)."""
    btn = st.download_button(
        "💾 Download scenario",
        data=json.dumps(locals_dict, indent=2),
        file_name="scenario.json",
        mime="application/json",
        use_container_width=True,
    )
    return btn

def scenario_upload():
    """Upload a .json to prefill inputs."""
    up = st.file_uploader("Load scenario (.json)", type=["json"])
    if up is None:
        return {}
    try:
        payload = json.load(up)
        st.success("Scenario loaded.")
        return payload
    except Exception as e:
        st.error(f"Invalid JSON: {e}")
        return {}

# ----------------------- Sidebar -----------------------
def sidebar() -> SimpleNamespace:
    with st.sidebar:
        st.header("Inputs — Operations")
        uploaded = st.file_uploader("15-min price file (CSV or Excel)", type=["csv","xlsx","xls"])
        st.caption("CSV/Excel autodetected. Needs timestamp & price columns.")
        d = constants.DEFAULTS

        plant_capacity_mw = st.number_input("Plant capacity (MW)", value=d["PLANT_CAP_MW"], min_value=0.1, step=1.0, help=H["PLANT_CAP_MW"])
        min_load_pct = st.slider("Min load (%)", 0.0, 100.0, d["MIN_LOAD_PCT"], step=1.0, help=H["MIN_LOAD_PCT"]) / 100.0
        max_load_pct = st.slider("Max load (%)", 0.0, 100.0, d["MAX_LOAD_PCT"], step=1.0, help=H["MAX_LOAD_PCT"]) / 100.0
        break_even = st.number_input("Break-even power price (€/MWh)", value=d["BREAK_EVEN_EUR_MWH"], step=1.0, help=H["BREAK_EVEN_EUR_MWH"])
        ramp_limit = st.number_input("Ramp limit (MW per 15-min)", value=d["RAMP_LIMIT_MW"], step=0.5, help=H["RAMP_LIMIT_MW"])
        always_on = st.checkbox("Always on (≥ min load)", value=d["ALWAYS_ON"], help=H["ALWAYS_ON"])

        st.header("Inputs — Production & Economics")
        mwh_per_ton = st.number_input("Electricity per ton (MWh/t)", value=d["MWH_PER_TON"], step=0.1, help=H["MWH_PER_TON"])
        methanol_price = st.number_input("Methanol price (€/t)", value=d["MEOH_PRICE"], step=10.0, help=H["MEOH_PRICE"])
        co2_price = st.number_input("CO₂ price (€/t)", value=d["CO2_PRICE"], step=1.0, help=H["CO2_PRICE"])
        co2_intensity = st.number_input("CO₂ needed (t/t)", value=d["CO2_INTENSITY"], step=0.025, help=H["CO2_INTENSITY"])
        maint_pct = st.number_input("Maintenance (% of revenue)", value=d["MAINT_PCT"], step=0.5, help=H["MAINT_PCT"]) / 100.0
        sga_pct   = st.number_input("SG&A (% of revenue)", value=d["SGA_PCT"], step=0.5, help=H["SGA_PCT"]) / 100.0
        ins_pct   = st.number_input("Insurance (% of revenue)", value=d["INS_PCT"], step=0.5, help=H["INS_PCT"]) / 100.0

        st.header("Target margin control")
        margin_method = st.radio("Margin method", ["Power-only (vs BE)", "Full-economics"], index=0)
        target_margin_pct = st.number_input("Target margin (%)", value=d["TARGET_MARGIN_PCT"], step=1.0, min_value=0.0, max_value=95.0)

        # Buttons
        run = st.button("Run Optimization", use_container_width=True)

        # Scenario save/load
        st.divider()
        st.caption("Scenario tools")
        return SimpleNamespace(
            uploaded=uploaded,
            plant_capacity_mw=float(plant_capacity_mw),
            min_load_pct=float(min_load_pct),
            max_load_pct=float(max_load_pct),
            break_even=float(break_even),
            ramp_limit=float(ramp_limit),
            always_on=bool(always_on),
            mwh_per_ton=float(mwh_per_ton),
            methanol_price=float(methanol_price),
            co2_price=float(co2_price),
            co2_intensity=float(co2_intensity),
            maint_pct=float(maint_pct),
            sga_pct=float(sga_pct),
            ins_pct=float(ins_pct),
            margin_method=str(margin_method),
            target_margin_pct=float(target_margin_pct),
            run=run,
        )

# ----------------------- Convenience -----------------------
def to_base_params(params: SimpleNamespace, price_cap: float, method_tag: str) -> dict:
    """Pack parameters for batch runners (matrix/portfolio)."""
    return {
        "plant_capacity_mw": params.plant_capacity_mw,
        "min_load_pct": params.min_load_pct,
        "max_load_pct": params.max_load_pct,
        "break_even_eur_per_mwh": params.break_even,
        "ramp_limit_mw_per_step": (params.ramp_limit if params.ramp_limit > 0 else None),
        "always_on": params.always_on,
        "dispatch_threshold_eur_per_mwh": price_cap,
        "mwh_per_ton": params.mwh_per_ton,
        "methanol_price_eur_per_ton": params.methanol_price,
        "co2_price_eur_per_ton": params.co2_price,
        "co2_t_per_ton_meoh": params.co2_intensity,
        "maintenance_pct_of_revenue": params.maint_pct,
        "sga_pct_of_revenue": params.sga_pct,
        "insurance_pct_of_revenue": params.ins_pct,
        "target_margin_fraction": params.target_margin_pct / 100.0,
        "margin_method": method_tag,
    }
