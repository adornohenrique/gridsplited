# core/ui.py
import os
from types import SimpleNamespace
import streamlit as st

def display_logo(logo_path: str = "logo.png") -> None:
    """Show a top-centered logo if the file exists."""
    if os.path.exists(logo_path):
        st.image(logo_path, use_container_width=True)
    else:
        st.warning(f"Logo file not found ({logo_path}). Place it next to app.py.")

def sidebar() -> SimpleNamespace:
    """All sidebar inputs collected into a SimpleNamespace."""
    st.sidebar.header("Inputs — Operations")

    uploaded = st.sidebar.file_uploader(
        "15-min price file (CSV or Excel)", type=["csv", "xlsx", "xls"]
    )
    st.sidebar.caption("Needs columns (or autodetected): timestamp and price.")

    # --- Operations
    plant_capacity_mw = st.sidebar.number_input(
        "Plant capacity (MW)", value=20.0, min_value=0.1, step=1.0
    )
    min_load_pct = st.sidebar.slider("Min load (%)", 0.0, 100.0, 10.0, step=1.0) / 100.0
    max_load_pct = st.sidebar.slider("Max load (%)", 0.0, 100.0, 100.0, step=1.0) / 100.0
    break_even = st.sidebar.number_input(
        "Break-even power price (€/MWh)", value=50.0, step=1.0
    )
    ramp_limit = st.sidebar.number_input(
        "Ramp limit (MW per 15-min) (optional)", value=2.0, step=0.5, min_value=0.0
    )
    always_on = st.sidebar.checkbox("Always on (≥ min load)", value=True)

    st.sidebar.header("Inputs — Production & Economics")
    mwh_per_ton = st.sidebar.number_input("Electricity per ton (MWh/t)", value=11.0, step=0.1)
    methanol_price = st.sidebar.number_input("Methanol price (€/t)", value=1000.0, step=10.0)
    co2_price = st.sidebar.number_input("CO₂ price (€/t)", value=40.0, step=1.0)
    co2_intensity = st.sidebar.number_input("CO₂ needed (t CO₂ per t MeOH)", value=1.375, step=0.025)
    maint_pct = st.sidebar.number_input("Maintenance (% of revenue)", value=3.0, step=0.5) / 100.0
    sga_pct   = st.sidebar.number_input("SG&A (% of revenue)", value=2.0, step=0.5) / 100.0
    ins_pct   = st.sidebar.number_input("Insurance (% of revenue)", value=1.0, step=0.5) / 100.0

    st.sidebar.header("Target margin control")
    margin_method = st.sidebar.radio(
        "Margin method",
        ["Power-only (vs BE)", "Full-economics"],
        index=0,
        help="Choose how to compute the price cap used for dispatch."
    )
    target_margin_pct = st.sidebar.number_input(
        "Target margin (%)", value=30.0, step=1.0, min_value=0.0, max_value=95.0
    )

    run = st.sidebar.button("Run Optimization", use_container_width=True)

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
        margin_method=margin_method,
        target_margin_pct=target_margin_pct,
        run=run,
    )

def to_base_params(params: SimpleNamespace, price_cap: float, method_tag: str) -> dict:
    """
    Create a base-param dict used by matrix/portfolio utilities.
    """
    return {
        "plant_capacity_mw": params.plant_capacity_mw,
        "min_load_pct": params.min_load_pct,
        "max_load_pct": params.max_load_pct,
        "break_even_eur_per_mwh": params.break_even,
        "ramp_limit_mw_per_step": (params.ramp_limit if params.ramp_limit > 0 else None),
        "always_on": params.always_on,
        "dispatch_threshold_eur_per_mwh": float(price_cap),
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
