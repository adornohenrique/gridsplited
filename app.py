# app.py
import streamlit as st
import pandas as pd

from core import ui, io, economics, optimizer, constants, show_help_panel
from core.battery import BatteryParams, simulate_price_band

st.set_page_config(page_title="Dispatch Optimizer", layout="wide")

# ---- Header ----
ui.display_logo("logo.png")
st.title("Quarter-hour Dispatch Optimizer (Profit-Max)")

# Help button
show_help_panel()

st.info("Upload your 15-min price file and click **Run Optimization**. "
        "This app autodetects CSV/Excel, separators, and comma-decimal formats.")

# ---- Sidebar ----
params = ui.sidebar()

# ---- Benchmark break-even (optional) ----
break_even = float(params.BREAK_EVEN_EUR_MWH)
if params.USE_BENCH_AS_BREAK_EVEN:
    be_from_benchmark = economics.benchmark_power_price(
        p_methanol=float(params.MEOH_PRICE),
        p_co2=float(params.CO2_PRICE),
        water_cost_eur_per_t=float(params.WATER_COST_T),
        trader_margin_pct=float(params.TRADER_MARGIN_PCT_UI),
        power_mwh_per_t=float(params.MWH_PER_TON),
        co2_t_per_t=float(params.CO2_INTENSITY),
    )
    st.caption("Benchmark = (pMeOH − CO₂_need·pCO₂ − water − margin%·pMeOH) / MWh_per_t")
    st.info(f"Benchmark power price = **{be_from_benchmark:,.2f} €/MWh** (applied)")
    break_even = be_from_benchmark

# ---- Price cap from target margin ----
price_cap, method_tag, err = economics.compute_price_cap(
    margin_method=str(params.MARGIN_METHOD),
    target_margin_pct=float(params.TARGET_MARGIN_PCT),
    break_even_eur_per_mwh=break_even,
    maint_pct=float(params.MAINT_PCT),
    sga_pct=float(params.SGA_PCT),
    ins_pct=float(params.INS_PCT),
    mwh_per_ton=float(params.MWH_PER_TON),
    methanol_price=float(params.MEOH_PRICE),
    co2_price=float(params.CO2_PRICE),
    co2_t_per_t=float(params.CO2_INTENSITY),
)
if err:
    st.error(err)

# ---- Run ----
if not params.run:
    st.stop()

if params.uploaded is None:
    st.error("Please upload a CSV or Excel with timestamp and price.")
    st.stop()

# Load price file
try:
    df = io.load_prices(params.uploaded)
except Exception as e:
    st.exception(e)
    st.stop()

st.info(f"Applied dispatch price cap: **{price_cap:,.2f} €/MWh**  "
        f"(method: {method_tag}, target margin: {float(params.TARGET_MARGIN_PCT):.1f}%)")

# Plant dispatch
results, kpis, out_xlsx = optimizer.run_dispatch(
    df=df,
    plant_capacity_mw=float(params.PLANT_CAP_MW),
    min_load_pct=float(params.MIN_LOAD_PCT) / 100.0,
    max_load_pct=float(params.MAX_LOAD_PCT) / 100.0,
    break_even_eur_per_mwh=float(break_even),
    ramp_limit_mw_per_step=(float(params.RAMP_LIMIT_MW) if float(params.RAMP_LIMIT_MW) > 0 else None),
    always_on=bool(params.ALWAYS_ON),
    dispatch_threshold_eur_per_mwh=float(price_cap),
    mwh_per_ton=float(params.MWH_PER_TON),
    methanol_price_eur_per_ton=float(params.MEOH_PRICE),
    co2_price_eur_per_ton=float(params.CO2_PRICE),
    co2_t_per_ton_meoh=float(params.CO2_INTENSITY),
    maintenance_pct_of_revenue=float(params.MAINT_PCT),
    sga_pct_of_revenue=float(params.SGA_PCT),
    insurance_pct_of_revenue=float(params.INS_PCT),
    target_margin_fraction=float(params.TARGET_MARGIN_PCT) / 100.0,
    margin_method=str(method_tag),
)

st.success("Optimization complete.")

# KPIs table (overview)
st.subheader("KPIs (project overview)")
show_cols = [
    "dispatch_threshold_eur_per_mwh",
    "target_margin_fraction",
    "margin_method",
    "total_energy_mwh",
    "weighted_avg_price_eur_per_mwh",
    "total_power_cost_eur",
    "total_tons",
    "total_methanol_revenue_eur",
    "total_co2_cost_eur",
    "total_opex_misc_eur",
    "total_true_profit_eur",
    "total_profit_proxy_eur",
]
kpis_view = {k: kpis.get(k, None) for k in show_cols}
st.dataframe(pd.DataFrame([kpis_view]))

if "total_tons" in kpis and kpis.get("total_tons") is not None:
    st.metric("Total production (t)", f"{kpis['total_tons']}")

# ---- Optional: Battery simulation ----
batt_results = None
batt_kpis = {}
if getattr(params, "BATTERY_ENABLED", False):
    bp = BatteryParams(
        dt_hours=0.25,
        cap_mwh=float(params.BATT_CAP_MWH),
        p_charge_mw=float(params.BATT_P_CHARGE_MW),
        p_discharge_mw=float(params.BATT_P_DISCHARGE_MW),
        eta_charge=float(params.BATT_ETA_CHARGE),
        eta_discharge=float(params.BATT_ETA_DISCHARGE),
        soc_init_frac=float(params.BATT_SOC_INIT_PCT) / 100.0,
        soc_min_frac=float(params.BATT_SOC_MIN_PCT) / 100.0,
        soc_max_frac=float(params.BATT_SOC_MAX_PCT) / 100.0,
        low_price_eur_per_mwh=float(params.BATT_LOW_PRICE),
        high_price_eur_per_mwh=float(params.BATT_HIGH_PRICE),
        degr_cost_eur_per_mwh=float(params.BATT_DEGR_EUR_PER_MWH),
        enforce_final_soc=bool(params.BATT_ENFORCE_FINAL_SOC),
    )
    batt_results, batt_kpis = simulate_price_band(df, bp)
    st.success(f"Battery arbitrage profit: **€{batt_kpis['batt_total_profit_eur']:,.0f}**")

    st.subheader("Battery KPIs")
    st.dataframe(pd.DataFrame([batt_kpis]))

    st.subheader("Battery timeline (first 200 rows)")
    st.dataframe(batt_results.head(200))

# ---- Combined total project profit (plant + battery) ----
combined_profit = kpis.get("total_true_profit_eur")
if combined_profit is None:
    combined_profit = kpis.get("total_profit_proxy_eur", 0.0)
if batt_kpis:
    combined_profit = float(combined_profit or 0.0) + float(batt_kpis.get("batt_total_profit_eur", 0.0))

st.metric("Total project profit (plant + battery)", f"€{combined_profit:,.0f}")

# ---- Dispatch outputs ----
st.subheader("Dispatch (first 200 rows)")
st.dataframe(results.head(200))

st.download_button("Download Excel (full results)",
                   data=open(out_xlsx, "rb").read(),
                   file_name="dispatch_plan.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.download_button("Download CSV (full results)",
                   data=results.to_csv(index=False).encode("utf-8"),
                   file_name="dispatch_plan.csv",
                   mime="text/csv")

# ---- Battery CSV (if enabled) ----
if batt_results is not None:
    st.download_button("Download Battery CSV",
                       data=batt_results.to_csv(index=False).encode("utf-8"),
                       file_name="battery_schedule.csv",
                       mime="text/csv")
