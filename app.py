# app.py
import os
import yaml
import numpy as np
import pandas as pd
import streamlit as st

from core import ui, io, optimizer, economics, battery, report

st.set_page_config(page_title="Quarter-hour Dispatch Optimizer", layout="wide")

# ---------------- Config ----------------
@st.cache_data(show_spinner=False)
def load_config(path: str = "config.yaml") -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

CFG = load_config()
D    = (CFG.get("defaults") or {})
BDEF = (CFG.get("battery_defaults") or {})
UI_C = (CFG.get("ui") or {})

# ---------------- Header ----------------
ui.display_logo(UI_C.get("logo", "logo.png"))
st.title("Quarter-hour Dispatch Optimizer (Profit-Max)")
ui.how_it_works_expander()

# ---------------- Sidebar ----------------
with st.sidebar:
    st.markdown("### Controls")

    st.markdown("#### 1) Price file")
    uploaded = st.file_uploader(
        "Upload CSV/XLSX with columns for time & price (any reasonable headers)",
        type=["csv", "xlsx", "xls"],
    )

    st.markdown("#### 2) Plant parameters")
    cap      = st.number_input("Plant capacity (MW)", 0.0, 1_000_000.0, float(D.get("PLANT_CAP_MW", 20.0)), 0.1)
    min_pct  = st.number_input("Min load (% of cap)", 0.0, 100.0, float(D.get("MIN_LOAD_PCT", 10.0)), 1.0)
    max_pct  = st.number_input("Max load (% of cap)", 0.0, 100.0, float(D.get("MAX_LOAD_PCT", 100.0)), 1.0)
    be       = st.number_input("Break-even (€/MWh)", -10_000.0, 10_000.0, float(D.get("BREAK_EVEN_EUR_MWH", 50.0)), 1.0)
    ramp     = st.number_input("Ramp limit per 15-min (MW)", 0.0, 1_000_000.0, float(D.get("RAMP_LIMIT_MW", 2.0)), 0.1)
    always_on = st.toggle("Always keep ≥ Min load", value=bool(D.get("ALWAYS_ON", True)))

    st.markdown("#### 3) Economics (MeOH)")
    mwh_per_ton  = st.number_input("MWh per ton MeOH", 0.0, 100_000.0, float(D.get("MWH_PER_TON", 11.0)), 0.1)
    meoh_price   = st.number_input("MeOH price (€/t)", 0.0, 1_000_000.0, float(D.get("MEOH_PRICE", 1000.0)), 1.0)
    co2_price    = st.number_input("CO₂ price (€/t)", 0.0, 1_000_000.0, float(D.get("CO2_PRICE", 40.0)), 1.0)
    co2_intensity= st.number_input("CO₂ intensity (t/t MeOH)", 0.0, 1000.0, float(D.get("CO2_INTENSITY", 1.375)), 0.001)
    maint_pct    = st.number_input("Maintenance (% revenue)", 0.0, 100.0, float(D.get("MAINT_PCT", 3.0)), 0.1)
    sga_pct      = st.number_input("SG&A (% revenue)", 0.0, 100.0, float(D.get("SGA_PCT", 2.0)), 0.1)
    ins_pct      = st.number_input("Insurance (% revenue)", 0.0, 100.0, float(D.get("INS_PCT", 1.0)), 0.1)
    water_cost_t = st.number_input("Water cost (€/t MeOH)", 0.0, 1_000_000.0, float(D.get("WATER_COST_T", 7.3)), 0.1)
    other_opex_t = st.number_input("Other OPEX (€/t MeOH)", 0.0, 1_000_000.0, float(D.get("OTHER_OPEX_T", 0.0)), 0.1)

    st.markdown("#### 4) Battery (optional)")
    use_batt = st.toggle("Enable battery", value=bool(BDEF.get("enabled", False)))
    if use_batt:
        e_mwh  = st.number_input("Energy capacity (MWh)", 0.0, 1_000_000.0, float(BDEF.get("e_mwh", 10.0)), 0.1)
        p_ch   = st.number_input("Charge power limit (MW)", 0.0, 1_000_000.0, float(BDEF.get("p_ch_mw", 5.0)), 0.1)
        p_dis  = st.number_input("Discharge power limit (MW)", 0.0, 1_000_000.0, float(BDEF.get("p_dis_mw", 5.0)), 0.1)
        eff_ch = st.number_input("Charge efficiency (0–1)", 0.0, 1.0, float(BDEF.get("eff_ch", 0.95)), 0.01)
        eff_dis= st.number_input("Discharge efficiency (0–1)", 0.0, 1.0, float(BDEF.get("eff_dis", 0.95)), 0.01)
        soc_min= st.number_input("SOC min (0–1)", 0.0, 1.0, float(BDEF.get("soc_min", 0.10)), 0.01)
        soc_max= st.number_input("SOC max (0–1)", 0.0, 1.0, float(BDEF.get("soc_max", 0.90)), 0.01)
        price_low  = st.number_input("Price to charge ≤ (€/MWh)", -10_000.0, 10_000.0, float(BDEF.get("price_low", 30.0)), 1.0)
        price_high = st.number_input("Price to discharge ≥ (€/MWh)", -10_000.0, 10_000.0, float(BDEF.get("price_high", 90.0)), 1.0)
        degr  = st.number_input("Degradation (€/MWh throughput)", 0.0, 10_000.0, float(BDEF.get("degradation_eur_per_mwh", 0.0)), 0.1)

# ---------------- Cache: load + align ----------------
@st.cache_data(show_spinner=False)
def load_and_align(file):
    raw = io.load_prices(file)
    aligned = io.ensure_quarter_hour(raw, method="pad", expand_edges=True)
    return raw, aligned

# ---------------- Tabs ----------------
tabs = st.tabs(["Data", "Dispatch", "Economics", "Battery", "Matrix & Portfolio"])

df_raw = df_prices = None
if uploaded:
    try:
        df_raw, df_prices = load_and_align(uploaded)
        issues = io.sanity_checks(df_prices)
        if issues:
            st.sidebar.warning(f"Data quality notes: {issues}")
        st.sidebar.success(f"Rows loaded: raw={len(df_raw):,} → aligned(qh)={len(df_prices):,}")
    except Exception as e:
        st.error(f"Failed to load prices: {e}")

with tabs[0]:
    st.subheader("Price data — preview (first 96 rows)")
    if df_prices is None:
        st.info("Upload a file to see data.")
    else:
        st.caption(f"Full dataset length: {len(df_prices):,} rows at 15-min cadence.")
        st.dataframe(df_prices.head(96), use_container_width=True)

with tabs[1]:
    st.subheader("Dispatch")
    if df_prices is None:
        st.info("Upload a file first.")
    else:
        if st.button("Run optimization", use_container_width=True):
            with st.spinner("Optimizing…"):
                out = optimizer.run_dispatch(
                    df_prices,
                    plant_capacity_mw=cap,
                    min_load_pct=min_pct,
                    max_load_pct=max_pct,
                    break_even_eur_per_mwh=be,
                    ramp_limit_mw_per_step=(ramp if ramp > 0 else None),
                    always_on=always_on,
                )
            st.session_state["prices_aligned"] = df_prices
            st.session_state["dispatch_df"] = out
            st.write(f"Computed rows: {len(out):,}")
            st.success("Done.")
            st.dataframe(out.head(96), use_container_width=True)
            st.download_button(
                "Download CSV (dispatch)",
                data=out.to_csv(index=False).encode("utf-8"),
                file_name="dispatch.csv",
                mime="text/csv",
                use_container_width=True,
            )

with tabs[2]:
    st.subheader("Economics")
    if df_prices is None:
        st.info("Upload a file first.")
    else:
        if st.button("Compute methanol economics", use_container_width=True):
            with st.spinner("Calculating…"):
                disp = optimizer.run_dispatch(
                    df_prices,
                    plant_capacity_mw=cap,
                    min_load_pct=min_pct,
                    max_load_pct=max_pct,
                    break_even_eur_per_mwh=be,
                    ramp_limit_mw_per_step=(ramp if ramp > 0 else None),
                    always_on=always_on,
                )
                kpis = economics.compute_kpis(
                    disp,
                    mwh_per_ton=mwh_per_ton,
                    meoh_price_eur_per_ton=meoh_price,
                    co2_price_eur_per_ton=co2_price,
                    co2_t_per_ton_meoh=co2_intensity,
                    maint_pct=maint_pct,
                    sga_pct=sga_pct,
                    ins_pct=ins_pct,
                    water_cost_eur_per_ton=water_cost_t,
                    other_opex_eur_per_ton=other_opex_t,
                    break_even_eur_per_mwh=be,
                )
            st.session_state["prices_aligned"] = df_prices
            st.session_state["dispatch_df"]   = disp
            st.session_state["kpis"]          = kpis
            ui.show_kpis(kpis)

with tabs[3]:
    st.subheader("Battery")
    if not use_batt:
        st.info("Battery is disabled (toggle it ON in the sidebar).")
    elif df_prices is None:
        st.info("Upload a file first.")
    else:
        if st.button("Run with battery", use_container_width=True):
            with st.spinner("Optimizing with battery…"):
                res = battery.run_battery_strategy(
                    df_prices,
                    e_mwh=e_mwh, p_ch_mw=p_ch, p_dis_mw=p_dis,
                    eff_ch=eff_ch, eff_dis=eff_dis,
                    soc_min=soc_min, soc_max=soc_max,
                    price_low=price_low, price_high=price_high,
                    degradation_eur_per_mwh=degr,
                )
            st.session_state["prices_aligned"] = df_prices
            st.session_state["battery_df"]    = res
            st.success("Done.")
            st.dataframe(res.head(96), use_container_width=True)
            st.download_button(
                "Download CSV (battery)",
                data=res.to_csv(index=False).encode("utf-8"),
                file_name="battery_dispatch.csv",
                mime="text/csv",
                use_container_width=True,
            )

with tabs[4]:
    st.subheader("Matrix & Portfolio")
    st.info("Coming soon: batch scenarios & portfolio view.")

# ---------------- Sidebar: Excel report ----------------
if st.session_state.get("prices_aligned") is not None:
    report_bytes = report.build_report(
        prices_aligned=st.session_state.get("prices_aligned"),
        dispatch_df=st.session_state.get("dispatch_df"),
        kpis=st.session_state.get("kpis"),
        battery_df=st.session_state.get("battery_df"),
    )
    st.sidebar.download_button(
        "Download Excel report",
        data=report_bytes,
        file_name="dispatch_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
