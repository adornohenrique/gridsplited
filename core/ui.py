# core/ui.py
import os
import io
import json
from types import SimpleNamespace

import streamlit as st
import pandas as pd

from . import constants
from . import economics  # used by the optional benchmark block


# ---------------------------------------------------------------------
# Utilities for scenario save/load (SAFE JSON only)
# ---------------------------------------------------------------------
def _to_jsonable(v):
    """
    Return a JSON-safe version of v or None if it can't be serialized.
    Keeps primitives (bool/int/float/str/None) and lists/dicts of primitives.
    Drops objects like file handles, Streamlit widgets, modules, etc.
    """
    try:
        import numpy as np
        np_types = (np.integer, np.floating, np.bool_)
    except Exception:
        np_types = tuple()

    if v is None:
        return None
    if isinstance(v, (bool, int, float, str)):
        return v
    if np_types and isinstance(v, np_types):
        try:
            return v.item()
        except Exception:
            return float(v)
    if isinstance(v, (list, tuple)):
        out = [_to_jsonable(x) for x in v]
        return out if any(x is not None for x in out) else None
    if isinstance(v, dict):
        out = {str(k): _to_jsonable(x) for k, x in v.items()}
        out = {k: x for k, x in out.items() if x is not None}
        return out or None
    return None


def _scenario_download(params: dict):
    """
    Offer a download of a JSON scenario with only JSON-safe primitives.
    Filters out obvious non-serializable entries (e.g., uploaded file).
    """
    DROP_KEYS = {
        "uploaded",          # Streamlit file-uploader object
        "run",               # button state not useful to persist
    }

    clean = {}
    for k, v in params.items():
        if k.startswith("_") or k in DROP_KEYS:
            continue
        if callable(v) or str(type(v)).startswith("<module"):
            continue
        jv = _to_jsonable(v)
        if jv is not None:
            clean[k] = jv

    st.download_button(
        "💾 Download scenario",
        data=json.dumps(clean, indent=2).encode("utf-8"),
        file_name="scenario.json",
        mime="application/json",
        use_container_width=True,
    )


def _scenario_upload():
    """Load a JSON scenario and return it as a dict, or None on failure."""
    up = st.file_uploader("Load scenario (.json)", type=["json"], key="scen_json_up")
    if not up:
        return None
    try:
        loaded = json.loads(up.getvalue().decode("utf-8"))
        if not isinstance(loaded, dict):
            st.error("Scenario file must be a JSON object.")
            return None
        st.success("Scenario loaded. Values will be applied where possible.")
        return loaded
    except Exception as e:
        st.error(f"Could not parse scenario JSON: {e}")
        return None


# ---------------------------------------------------------------------
# Visual helpers
# ---------------------------------------------------------------------
def display_logo(logo_path: str = "logo.png"):
    """Show a logo centered if the file exists."""
    if os.path.exists(logo_path):
        st.image(logo_path, use_container_width=True)
    else:
        st.warning(f"⚠️ Logo file not found ({logo_path}). Place it next to app.py.")


# ---------------------------------------------------------------------
# Sidebar (input mask)
# ---------------------------------------------------------------------
def sidebar() -> SimpleNamespace:
    """
    Build the sidebar UI and return all parameters as a SimpleNamespace.
    The names match what app.py and other modules expect.
    """
    with st.sidebar:
        st.header("Inputs — Operations")
        uploaded = st.file_uploader("15-min price file (CSV or Excel)", type=["csv", "xlsx", "xls"])
        st.caption("Needs columns (or autodetected): timestamp and price.")

        d = constants.DEFAULTS

        # Core plant operation inputs
        PLANT_CAP_MW = st.number_input(
            "Plant capacity (MW)", value=d["PLANT_CAP_MW"], min_value=0.1, step=1.0
        )
        MIN_LOAD_PCT = st.slider(
            "Min load (%)", 0.0, 100.0, d["MIN_LOAD_PCT"], step=1.0
        ) / 100.0
        MAX_LOAD_PCT = st.slider(
            "Max load (%)", 0.0, 100.0, d["MAX_LOAD_PCT"], step=1.0
        ) / 100.0

        BREAK_EVEN_EUR_MWH = st.number_input(
            "Break-even power price (€/MWh)", value=d["BREAK_EVEN_EUR_MWH"], step=1.0
        )
        RAMP_LIMIT_MW = st.number_input(
            "Ramp limit (MW per 15-min) (optional)", value=d["RAMP_LIMIT_MW"], step=0.5
        )
        ALWAYS_ON = st.checkbox("Always on (≥ min load)", value=d["ALWAYS_ON"])

        st.header("Inputs — Production & Economics")
        MWH_PER_TON = st.number_input(
            "Electricity per ton (MWh/t)", value=d["MWH_PER_TON"], step=0.1
        )
        MEOH_PRICE = st.number_input(
            "Methanol price (€/t)", value=d["MEOH_PRICE"], step=10.0
        )
        CO2_PRICE = st.number_input(
            "CO₂ price (€/t)", value=d["CO2_PRICE"], step=1.0
        )
        CO2_INTENSITY = st.number_input(
            "CO₂ needed (t CO₂ per t MeOH)", value=d["CO2_INTENSITY"], step=0.025
        )
        MAINT_PCT = st.number_input(
            "Maintenance (% of revenue)", value=d["MAINT_PCT"], step=0.5
        )
        SGA_PCT = st.number_input(
            "SG&A (% of revenue)", value=d["SGA_PCT"], step=0.5
        )
        INS_PCT = st.number_input(
            "Insurance (% of revenue)", value=d["INS_PCT"], step=0.5
        )

        # Optional benchmark section (power BE from full economics)
        st.header("Optional — Benchmark & OPEX")
        WATER_COST_T = st.number_input("Water cost (€/t)", value=d["WATER_COST_T"], step=0.1, min_value=0.0)
        TRADER_MARGIN_PCT_UI = st.number_input(
            "Trader margin for benchmark (% of MeOH revenue)",
            value=d["TRADER_MARGIN_PCT_UI"], step=1.0, min_value=0.0, max_value=100.0
        )
        OTHER_OPEX_T = st.number_input("Other variable OPEX (€/t)", value=d["OTHER_OPEX_T"], step=1.0, min_value=0.0)

        be_from_benchmark = economics.benchmark_power_price(
            p_methanol=MEOH_PRICE,
            p_co2=CO2_PRICE,
            water_cost_eur_per_t=WATER_COST_T,
            trader_margin_pct=TRADER_MARGIN_PCT_UI,
            power_mwh_per_t=float(MWH_PER_TON),
            co2_t_per_t=float(CO2_INTENSITY),
        )
        st.caption("Benchmark: (pMeOH − CO₂_need·pCO₂ − water − margin%·pMeOH) / MWh_per_t")
        st.info(f"Benchmark power price = **{be_from_benchmark:,.2f} €/MWh**")

        power_cost_at_BE_per_t = float(BREAK_EVEN_EUR_MWH) * float(MWH_PER_TON)
        co2_cost_per_t = float(CO2_PRICE) * float(CO2_INTENSITY)
        non_power_opex_per_t = WATER_COST_T + OTHER_OPEX_T
        total_variable_cost_BE = power_cost_at_BE_per_t + co2_cost_per_t + non_power_opex_per_t

        st.markdown(
            f"""
- Power cost @ BE: **{power_cost_at_BE_per_t:,.2f} €/t**  
- CO₂ cost: **{co2_cost_per_t:,.2f} €/t**  
- Water + other OPEX: **{non_power_opex_per_t:,.2f} €/t**  
**Total variable cost @ BE:** **{total_variable_cost_BE:,.2f} €/t**
            """
        )

        USE_BENCH_AS_BREAK_EVEN = st.checkbox(
            "Use this Benchmark as Break-even for dispatch",
            value=False,
            help="If checked, replaces the Break-even (€/MWh) with the computed benchmark above."
        )

        st.header("Target margin control")
        MARGIN_METHOD = st.radio(
            "Margin method",
            ["Power-only (vs BE)", "Full-economics"],
            index=0,
            help="Choose how to compute the price cap used for dispatch."
        )
        TARGET_MARGIN_PCT = st.number_input(
            "Target margin (%)", value=d["TARGET_MARGIN_PCT"], step=1.0, min_value=0.0, max_value=95.0
        )

        # Run button
        run = st.button("Run Optimization", use_container_width=True)

        # Scenario save/load
        st.markdown("---")
        _scenario_download(locals())
        loaded = _scenario_upload()
        if loaded:
            # Apply loaded scenario to session_state so widgets pick it up
            for k, v in loaded.items():
                # only set known keys; ignore unknown entries
                st.session_state[k] = v
            st.info("Loaded scenario values. Adjust if needed and click Run.")

    # Return all params to caller
    return SimpleNamespace(
        # uploader and action
        uploaded=uploaded,
        run=run,

        # core ops
        PLANT_CAP_MW=PLANT_CAP_MW,
        MIN_LOAD_PCT=MIN_LOAD_PCT,
        MAX_LOAD_PCT=MAX_LOAD_PCT,
        BREAK_EVEN_EUR_MWH=BREAK_EVEN_EUR_MWH,
        RAMP_LIMIT_MW=RAMP_LIMIT_MW,
        ALWAYS_ON=ALWAYS_ON,

        # economics
        MWH_PER_TON=MWH_PER_TON,
        MEOH_PRICE=MEOH_PRICE,
        CO2_PRICE=CO2_PRICE,
        CO2_INTENSITY=CO2_INTENSITY,
        MAINT_PCT=MAINT_PCT,
        SGA_PCT=SGA_PCT,
        INS_PCT=INS_PCT,

        # benchmark inputs / opex
        WATER_COST_T=WATER_COST_T,
        TRADER_MARGIN_PCT_UI=TRADER_MARGIN_PCT_UI,
        OTHER_OPEX_T=OTHER_OPEX_T,
        USE_BENCH_AS_BREAK_EVEN=USE_BENCH_AS_BREAK_EVEN,
        BENCHMARK_BE=be_from_benchmark,

        # margin control
        MARGIN_METHOD=MARGIN_METHOD,
        TARGET_MARGIN_PCT=TARGET_MARGIN_PCT,

        # useful derived opex to show elsewhere if needed
        POWER_COST_AT_BE_T=power_cost_at_BE_per_t,
        CO2_COST_PER_T=co2_cost_per_t,
        NON_POWER_OPEX_T=non_power_opex_per_t,
        TOTAL_VARIABLE_COST_BE_T=total_variable_cost_BE,
    )
