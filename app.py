# app.py
import streamlit as st
import pandas as pd
import plotly.express as px

from core import ui, io, economics, optimizer, constants
from core.help import show_help_panel
from core.battery import BatteryParams, simulate_price_band
from core.battery import BatteryParams

st.set_page_config(page_title="Dispatch Optimizer", layout="wide")

# ---- Header ----
ui.display_logo("logo.png")
# Header
ui.display_logo(constants.UI.get("logo","logo.png"))
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
tabs = st.tabs(["Inputs & Run", "Results", "Charts", "Downloads", "Matrix & Portfolio"])

with tabs[0]:
    params = ui.sidebar()
    st.info("Upload your 15-min price file and click **Run Optimization**. CSV/Excel autodetected.")

    # Apply optional benchmark
    break_even = params.break_even
    if params.use_bench_as_break_even:
        break_even = economics.benchmark_power_price(
            p_methanol=params.methanol_price,
            p_co2=params.co2_price,
            water_cost_eur_per_t=params.water_cost_t,
            trader_margin_pct=params.trader_margin_pct_ui,
            power_mwh_per_t=float(params.mwh_per_ton),
            co2_t_per_t=float(params.co2_intensity),
        )

    # Compute price cap
    price_cap, method_tag, err = economics.compute_price_cap(
        margin_method=str(params.MARGIN_METHOD),
        target_margin_pct=float(params.TARGET_MARGIN_PCT),
        break_even_eur_per_mwh=float(break_even),
        maint_pct=float(params.maint_pct),
        sga_pct=float(params.sga_pct),
        ins_pct=float(params.ins_pct),
        mwh_per_ton=float(params.mwh_per_ton),
        methanol_price=float(params.methanol_price),
        co2_price=float(params.co2_price),
        co2_t_per_t=float(params.co2_intensity),
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
    if err:
        st.error(err)
        st.stop()

    # Prepare BatteryParams
    bat = BatteryParams(
        enabled=bool(params.bat_en),
        e_mwh=float(params.e_mwh),
        p_ch_mw=float(params.p_ch),
        p_dis_mw=float(params.p_dis),
        eff_ch=float(params.eff_ch),
        eff_dis=float(params.eff_dis),
        soc_min=float(params.soc_min),
        soc_max=float(params.soc_max),
        price_low=float(params.price_low),
        price_high=float(params.price_high),
        degradation_eur_per_mwh=float(params.degr),
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

    # Run
    if params.run:
        if params.uploaded is None:
            st.error("Please upload a CSV/Excel with timestamp and price.")
            st.stop()
        try:
            df = io.load_prices(params.uploaded)
        except Exception as e:
            st.exception(e)
            st.stop()

        plant_res, plant_kpis, bat_df, bat_kpis = optimizer.run_dispatch(
            df=df,
            plant_capacity_mw=params.plant_capacity_mw,
            min_load_pct=params.min_load_pct,
            max_load_pct=params.max_load_pct,
            break_even_eur_per_mwh=break_even,
            ramp_limit_mw_per_step=(params.ramp_limit if params.ramp_limit > 0 else None),
            always_on=params.always_on,
            dispatch_threshold_eur_per_mwh=price_cap,
            mwh_per_ton=params.mwh_per_ton,
            methanol_price_eur_per_ton=params.methanol_price,
            co2_price_eur_per_ton=params.co2_price,
            co2_t_per_ton_meoh=params.co2_intensity,
            maintenance_pct_of_revenue=params.maint_pct,
            sga_pct_of_revenue=params.sga_pct,
            insurance_pct_of_revenue=params.ins_pct,
            target_margin_fraction=float(params.TARGET_MARGIN_PCT)/100.0,
            margin_method=method_tag,
            battery_params=bat
        )

        st.session_state["last_results"] = plant_res
        st.session_state["last_kpis"] = plant_kpis
        st.session_state["last_bat_df"] = bat_df
        st.session_state["last_bat_kpis"] = bat_kpis
        st.success("Optimization complete. See Results / Charts / Downloads tabs.")

with tabs[1]:
    res = st.session_state.get("last_results")
    kpis = st.session_state.get("last_kpis", {})
    bat_df = st.session_state.get("last_bat_df", pd.DataFrame())
    bat_kpis = st.session_state.get("last_bat_kpis", {})

    if res is None:
        st.info("No results yet. Run an optimization first.")
    else:
        st.subheader("KPIs — Plant")
        st.dataframe(pd.DataFrame([kpis]))
        if bat_kpis.get("battery_enabled"):
            st.subheader("KPIs — Battery")
            st.dataframe(pd.DataFrame([bat_kpis]))
            st.metric("Total Project Profit (EUR)", f"{(kpis.get('total_true_profit_eur',0.0) + bat_kpis.get('battery_profit_eur',0.0)):.0f}")

        st.subheader("Dispatch (first 200 rows)")
        st.dataframe(res.head(200))

with tabs[2]:
    res = st.session_state.get("last_results")
    bat_df = st.session_state.get("last_bat_df", pd.DataFrame())
    if res is None:
        st.info("Run an optimization to populate charts.")
    else:
        tmp = res.copy()
        if "timestamp" in tmp.columns:
            tmp["timestamp"] = pd.to_datetime(tmp["timestamp"])
        cols = [c for c in tmp.columns if c.lower() in ("price","price_eur_per_mwh")]
        price_col = cols[0] if cols else "price_eur_per_mwh"
        if price_col not in tmp.columns and "price_eur_per_mwh" in tmp.columns:
            price_col = "price_eur_per_mwh"

        if "mw" in tmp.columns:
            st.plotly_chart(px.line(tmp, x="timestamp", y=[price_col, "mw"], title="Price vs Dispatch (MW)"), use_container_width=True)

        if "profit" in tmp.columns:
            daily = tmp.groupby(tmp["timestamp"].dt.date)["profit"].sum().reset_index(name="profit")
            st.plotly_chart(px.bar(daily, x="timestamp", y="profit", title="Daily Profit"), use_container_width=True)

        if not bat_df.empty:
            st.plotly_chart(px.line(bat_df, x="timestamp", y="bat_soc", title="Battery SoC"), use_container_width=True)

with tabs[3]:
    res = st.session_state.get("last_results")
    bat_df = st.session_state.get("last_bat_df", pd.DataFrame())
    if res is None:
        st.info("Run an optimization first.")
    else:
        st.download_button("⬇️ Download dispatch CSV", data=res.to_csv(index=False).encode("utf-8"), file_name="dispatch_plan.csv", mime="text/csv", use_container_width=True)
        if not bat_df.empty:
            st.download_button("⬇️ Download battery CSV", data=bat_df.to_csv(index=False).encode("utf-8"), file_name="battery_schedule.csv", mime="text/csv", use_container_width=True)

with tabs[4]:
    st.subheader("Scenario matrix (sensitivity)")
    st.caption("Runs multiple cases across Methanol price and Target margin.")
    col1, col2 = st.columns(2)
    with col1:
        meoh_min = st.number_input("MeOH min (€/t)", value=800.0)
        meoh_max = st.number_input("MeOH max (€/t)", value=1400.0)
        meoh_step = st.number_input("MeOH step", value=200.0)
    with col2:
        margin_min = st.number_input("Margin min (%)", value=10.0)
        margin_max = st.number_input("Margin max (%)", value=50.0)
        margin_step = st.number_input("Margin step", value=10.0)

    df_last = st.session_state.get("last_results")
    base_kpis = st.session_state.get("last_kpis", {})
    if st.button("Run matrix"):
        st.warning("Matrix needs the last uploaded price file & inputs; re-run base case if needed.")
        # We reuse the last uploaded file by asking the user to upload again in Inputs tab when needed.
        st.info("Matrix runner is a stub scaffold. Hook to your own batch-runner if desired.")

        st.stop()
