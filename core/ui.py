# core/ui.py
import os
import json
import streamlit as st
from types import SimpleNamespace
from . import constants, economics

def display_logo(logo_path: str):
    if os.path.exists(logo_path):
        st.image(logo_path, use_container_width=True)
    else:
        # Not blocking; just a heads-up.
        st.caption("Logo file not found (logo.png). Place it next to app.py.")

def _scenario_dict_from_params(p: SimpleNamespace) -> dict:
    """Convert SimpleNamespace of parameters to a plain dict for JSON."""
    return {
        "PLANT_CAP_MW": p.PLANT_CAP_MW,
        "MIN_LOAD_PCT": p.MIN_LOAD_PCT,
        "MAX_LOAD_PCT": p.MAX_LOAD_PCT,
        "BREAK_EVEN_EUR_MWH": p.BREAK_EVEN_EUR_MWH,
        "RAMP_LIMIT_MW": p.RAMP_LIMIT_MW,
        "ALWAYS_ON": p.ALWAYS_ON,
        "MWH_PER_TON": p.MWH_PER_TON,
        "MEOH_PRICE": p.MEOH_PRICE,
        "CO2_PRICE": p.CO2_PRICE,
        "CO2_INTENSITY": p.CO2_INTENSITY,
        "MAINT_PCT": p.MAINT_PCT,
        "SGA_PCT": p.SGA_PCT,
        "INS_PCT": p.INS_PCT,
        "WATER_COST_T": p.WATER_COST_T,
        "TRADER_MARGIN_PCT_UI": p.TRADER_MARGIN_PCT_UI,
        "OTHER_OPEX_T": p.OTHER_OPEX_T,
        "TARGET_MARGIN_PCT": p.TARGET_MARGIN_PCT,
        "MARGIN_METHOD": p.MARGIN_METHOD,
        "USE_BENCH_AS_BREAK_EVEN": p.USE_BENCH_AS_BREAK_EVEN,
    }

def _apply_loaded_scenario(d: dict, defaults: dict) -> dict:
    """Merge a loaded dict with defaults to avoid missing keys."""
    out = defaults.copy()
    out.update({k: d.get(k, out.get(k)) for k in out.keys()})
    return out

def sidebar() -> SimpleNamespace:
    d = constants.DEFAULTS

    with st.sidebar:
        st.header("Inputs — Operations")
        uploaded = st.file_uploader("15-min price file (CSV or Excel)", type=["csv","xlsx","xls"])
        st.caption("CSV must include 'timestamp' and 'price' (auto-detected).")

        plant_cap_mw = st.number_input("Plant capacity (MW)", value=d["PLANT_CAP_MW"], min_value=0.1, step=1.0)
        min_load_pct = st.slider("Min load (%)", 0.0, 100.0, d["MIN_LOAD_PCT"], step=1.0)
        max_load_pct = st.slider("Max load (%)", 0.0, 100.0, d["MAX_LOAD_PCT"], step=1.0)
        break_even = st.number_input("Break-even power price (€/MWh)", value=d["BREAK_EVEN_EUR_MWH"], step=1.0)
        ramp_limit = st.number_input("Ramp limit (MW per 15-min) (optional)", value=d["RAMP_LIMIT_MW"], step=0.5)
        always_on = st.checkbox("Always on (≥ min load)", value=d["ALWAYS_ON"])

        st.header("Inputs — Production & Economics")
        mwh_per_ton = st.number_input("Electricity per ton (MWh/t)", value=d["MWH_PER_TON"], step=0.1)
        meoh_price = st.number_input("Methanol price (€/t)", value=d["MEOH_PRICE"], step=10.0)
        co2_price = st.number_input("CO₂ price (€/t)", value=d["CO2_PRICE"], step=1.0)
        co2_intensity = st.number_input("CO₂ needed (t CO₂ per t MeOH)", value=d["CO2_INTENSITY"], step=0.025)
        maint_pct = st.number_input("Maintenance (% of revenue)", value=d["MAINT_PCT"], step=0.5)
        sga_pct = st.number_input("SG&A (% of revenue)", value=d["SGA_PCT"], step=0.5)
        ins_pct = st.number_input("Insurance (% of revenue)", value=d["INS_PCT"], step=0.5)

        st.header("Optional — Benchmark (reference only)")
        st.caption("Formula: (pMeOH − CO₂_need·pCO₂ − water − margin%·pMeOH) / MWh_per_t")
        water_cost = st.number_input("Water cost (€/t)", value=d["WATER_COST_T"], step=0.1)
        margin_ui = st.number_input("Trader margin for benchmark (% of MeOH revenue)", value=d["TRADER_MARGIN_PCT_UI"], step=1.0)

        bench_be = economics.benchmark_power_price(
            p_methanol=meoh_price, p_co2=co2_price, water_cost_eur_per_t=water_cost,
            trader_margin_pct=margin_ui, power_mwh_per_t=mwh_per_ton, co2_t_per_t=co2_intensity
        )
        st.info(f"Benchmark power price = **{bench_be:,.2f} €/MWh**")
        use_bench = st.checkbox("Use this Benchmark as Break-even for dispatch", value=False)

        st.header("Target margin control")
        margin_method = st.radio("Margin method", ["Power-only (vs BE)", "Full-economics"], index=0)
        target_margin_pct = st.number_input("Target margin (%)", value=d["TARGET_MARGIN_PCT"], step=1.0, min_value=0.0, max_value=95.0)

        # Scenario save/load
        st.divider()
        st.subheader("Scenario")
        # Build a dict for current inputs so the download reflects latest values
        current_dict = {
            "PLANT_CAP_MW": plant_cap_mw,
            "MIN_LOAD_PCT": min_load_pct,
            "MAX_LOAD_PCT": max_load_pct,
            "BREAK_EVEN_EUR_MWH": break_even,
            "RAMP_LIMIT_MW": ramp_limit,
            "ALWAYS_ON": always_on,
            "MWH_PER_TON": mwh_per_ton,
            "MEOH_PRICE": meoh_price,
            "CO2_PRICE": co2_price,
            "CO2_INTENSITY": co2_intensity,
            "MAINT_PCT": maint_pct,
            "SGA_PCT": sga_pct,
            "INS_PCT": ins_pct,
            "WATER_COST_T": water_cost,
            "TRADER_MARGIN_PCT_UI": margin_ui,
            "OTHER_OPEX_T": d["OTHER_OPEX_T"],
            "TARGET_MARGIN_PCT": target_margin_pct,
            "MARGIN_METHOD": margin_method,
            "USE_BENCH_AS_BREAK_EVEN": use_bench,
        }
        st.download_button(
            "💾 Download scenario",
            data=json.dumps(current_dict, indent=2).encode("utf-8"),
            file_name="scenario.json",
            mime="application/json",
            use_container_width=True
        )

        uploaded_scn = st.file_uploader("Load scenario (.json)", type=["json"], key="__scn__")
        if uploaded_scn is not None:
            try:
                loaded = json.load(uploaded_scn)
                merged = _apply_loaded_scenario(loaded, constants.DEFAULTS)
                # Overwrite local variables with loaded values
                plant_cap_mw = merged["PLANT_CAP_MW"]
                min_load_pct = merged["MIN_LOAD_PCT"]
                max_load_pct = merged["MAX_LOAD_PCT"]
                break_even = merged["BREAK_EVEN_EUR_MWH"]
                ramp_limit = merged["RAMP_LIMIT_MW"]
                always_on = merged["ALWAYS_ON"]
                mwh_per_ton = merged["MWH_PER_TON"]
                meoh_price = merged["MEOH_PRICE"]
                co2_price = merged["CO2_PRICE"]
                co2_intensity = merged["CO2_INTENSITY"]
                maint_pct = merged["MAINT_PCT"]
                sga_pct = merged["SGA_PCT"]
                ins_pct = merged["INS_PCT"]
                water_cost = merged["WATER_COST_T"]
                margin_ui = merged["TRADER_MARGIN_PCT_UI"]
                target_margin_pct = merged["TARGET_MARGIN_PCT"]
                margin_method = merged["MARGIN_METHOD"]
                use_bench = merged["USE_BENCH_AS_BREAK_EVEN"]
                st.success("Scenario loaded. Adjust values if needed, then run.")
            except Exception as e:
                st.error(f"Failed to load scenario: {e}")

        run = st.button("Run Optimization", use_container_width=True)

    # Return everything as a namespace with UPPERCASE names
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
        WATER_COST_T=float(water_cost),
        TRADER_MARGIN_PCT_UI=float(margin_ui),
        OTHER_OPEX_T=float(constants.DEFAULTS["OTHER_OPEX_T"]),
        TARGET_MARGIN_PCT=float(target_margin_pct),
        MARGIN_METHOD=str(margin_method),
        USE_BENCH_AS_BREAK_EVEN=bool(use_bench),
        BENCHMARK_BE=float(bench_be),
    )
